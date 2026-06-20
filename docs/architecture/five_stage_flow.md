# ThesisMiner v8.0 五阶段闭环导航流

> **版本**：v8.0
> **日期**：2026-06-19
> **适用范围**：`backend/orchestration/`、`backend/agents/`、`config/agents/orchestrator.yaml`
> **关联模块**：信息确权 → 谱系解析 → 重复度评估 → 多粒度生成 → 深度辅助

---

## 目录

1. [五阶段流程总览](#1-五阶段流程总览)
2. [阶段一：信息确权](#2-阶段一信息确权)
3. [阶段二：谱系解析与四维创意](#3-阶段二谱系解析与四维创意)
4. [阶段三：重复度评估与硬约束修复](#4-阶段三重复度评估与硬约束修复)
5. [阶段四：多粒度生成与降重脱敏](#5-阶段四多粒度生成与降重脱敏)
6. [阶段五：深度辅助闭环](#6-阶段五深度辅助闭环)
7. [阶段切换规则与门禁](#7-阶段切换规则与门禁)
8. [重试与兜底逻辑](#8-重试与兜底逻辑)
9. [ASCII 流程图](#9-ascii-流程图)
10. [阻断性规则（Rule 7-10）](#10-阻断性规则rule-7-10)
11. [状态持久化与恢复](#11-状态持久化与恢复)
12. [多对话场景下的阶段管理](#12-多对话场景下的阶段管理)
13. [性能与成本考量](#13-性能与成本考量)
14. [附录](#14-附录)

---

## 1. 五阶段流程总览

### 1.1 设计理念

ThesisMiner v8.0 将研究生开题全生命周期拆解为五个闭环阶段，每个阶段有明确的输入、输出、门禁规则与兜底策略。设计理念如下：

1. **闭环导航**：五阶段不是线性流水线，而是闭环导航流，支持回退、重试、跳转。
2. **门禁驱动**：每个阶段切换需通过门禁规则，不通过则回退或重试，确保质量。
3. **用户主导**：关键节点（如信息确权）需用户确认，避免 AI 自主跳过。
4. **降重优先**：报告生成后强制执行降重脱敏，确保 AI 痕迹最小化。
5. **深度陪跑**：报告输出后不结束对话，进入深度辅助闭环，提供文献精读、实验预研、答辩模拟。

### 1.2 五阶段一览

| 阶段 | 名称 | 主 Agent | 核心任务 | 门禁规则 |
|------|------|----------|----------|----------|
| 1 | 信息确权 | Searcher | 联网检索近 2 年文献，展示摘要，等待用户确认 | 用户确认 |
| 2 | 谱系解析与四维创意 | Reasoner | 解析谱系，四维创意生成，自评分过滤 | ≥3 候选且 score ≥6 |
| 3 | 重复度评估与硬约束修复 | Critic | 联网检索近 5 年文献，新颖性评估，硬约束修复 | 硬约束通过 |
| 4 | 多粒度生成与降重脱敏 | Writer | 多粒度报告生成，style_normalizer 降重 | 报告生成且降重执行 |
| 5 | 深度辅助闭环 | Mentor | 文献精读、实验预研、答辩模拟三件套 | 用户主动结束 |

### 1.3 与 v7 的差异

| 维度 | v7 | v8 |
|------|-----|-----|
| 流程模型 | 线性六步（init → inspiring → reasoning → validating → completed/failed） | 五阶段闭环（信息确权 → 谱系解析 → 重复度评估 → 多粒度生成 → 深度辅助） |
| 阶段门禁 | 无显式门禁 | 每阶段有门禁规则，不通过则回退 |
| 用户确认 | 无强制确认 | 阶段一强制用户确认（Rule 7） |
| 重复度评估 | 无 | 阶段三新增重复度评估（Rule 8） |
| 降重脱敏 | 无 | 阶段四强制降重（Rule 9） |
| 深度辅助 | 无 | 阶段五深度辅助闭环（Rule 10） |

---

## 2. 阶段一：信息确权

### 2.1 阶段目标

在生成论题前，先联网检索近 2 年文献，展示摘要，**强制等待用户确认**后解锁阶段二。目标：

1. **避免凭空生成**：基于真实文献热点生成论题，提升时效性。
2. **用户主导**：用户确认检索方向后再生成，避免 AI 自主跳过。
3. **信息透明**：展示文献摘要，让用户了解当前研究热点。

### 2.2 输入

```json
{
  "degree": "master",
  "discipline": "计算机科学",
  "mentor_info": "导师项目：医疗大模型\n同门论文：英文问诊微调",
  "user_input": "我是硕士生，导师在做医疗大模型，帮我生成3个论题"
}
```

### 2.3 处理流程

```text
1. 解析用户输入，提取学位、学科、导师信息
2. 按 search_strategies.json 生成检索式：
   - inspiration_window: 近 2 年（默认 2024-2026）
   - 学科关键词 + 同义词
3. 调用 Searcher 联网检索（arXiv + Semantic Scholar）
4. 展示文献摘要（Top 10）：
   - 标题、作者、年份、摘要、URL
5. 强制中断，等待用户确认：
   - "继续" → 进入阶段二
   - "调整检索式" → 重新检索
   - "换方向" → 重新解析输入
```

### 2.4 输出

```json
{
  "stage": "info_confirm",
  "status": "awaiting_confirmation",
  "data": {
    "query": "(\"large language model\" OR \"LLM\") AND (2024 OR 2025 OR 2026)",
    "time_window": "2024-2026",
    "total_results": 42,
    "results": [
      {
        "title": "论文标题",
        "authors": ["作者1"],
        "year": 2025,
        "abstract": "摘要...",
        "url": "https://..."
      }
    ]
  },
  "next_action": "请确认是否继续，或调整检索式/换方向"
}
```

### 2.5 门禁规则

| 门禁 | 规则 | 不通过处理 |
|------|------|-----------|
| 检索执行 | 必须执行联网检索 | 回退到检索步骤 |
| 摘要展示 | 必须展示文献摘要 | 回退到展示步骤 |
| 用户确认 | 必须等待用户确认 | 阻断阶段二执行 |

### 2.6 兜底策略

| 失败场景 | 兜底策略 |
|----------|----------|
| 联网检索超时（>5s） | 降级为 MockSearcher，返回模拟文献 |
| 检索结果为空 | 提示用户调整检索式或换方向 |
| 用户跳过确认 | 按 Rule 8 时间窗口交互兜底，回放摘要并提示 |

---

## 3. 阶段二：谱系解析与四维创意

### 3.1 阶段目标

基于阶段一确认的检索结果与用户输入的谱系信息，调用 Reasoner 执行四维创意生成，输出 ≥3 个候选论题（每个 score ≥6）。目标：

1. **谱系延续**：基于导师项目与同门论文生成候选，确保学术谱系延续性。
2. **四维发散**：并行执行四个策略，覆盖导师延伸、同门继承、跨域联想、矛盾驱动。
3. **自评分过滤**：按可行性 + 创新度 + 谱系贴合度打分，过滤低分候选。

### 3.2 输入

```json
{
  "stage": "creativity",
  "input": {
    "degree": "master",
    "lineage_text": "导师项目：医疗大模型\n同门论文：英文问诊微调",
    "search_feeds": [
      { "title": "文献1", "abstract": "摘要1" },
      { "title": "文献2", "abstract": "摘要2" }
    ],
    "strategy": "all"
  }
}
```

### 3.3 处理流程

```text
1. 调用 lineage_parser.parse_lineage(text) 解析谱系：
   - 抽取导师项目（advisor_projects）
   - 抽取同门论文（peer_papers）
   - 边缘探测（edge_opportunities）
2. 将阶段一检索结果封装为 search_feeds
3. 调用 idea_generator.generate_ideas(lineage_graph, strategy, degree, search_feeds)：
   - 并行执行四策略：
     a. 导师项目延伸（advisor_extension）
     b. 同门成果继承（peer_inheritance）
     c. 跨域联想（cross_domain）
     d. 矛盾驱动挖掘（contradiction_driven）
   - 每个候选自评分：可行性 × 0.4 + 创新度 × 0.3 + 谱系贴合度 × 0.3
   - 过滤 score < 6 的候选
4. 保留 Top 3-5 个候选
5. 输出候选列表
```

### 3.4 输出

```json
{
  "stage": "creativity",
  "status": "success",
  "data": {
    "lineage_graph": {
      "advisor_projects": [...],
      "peer_papers": [...],
      "edge_opportunities": [...]
    },
    "candidates": [
      {
        "title": "中文医疗问诊的小样本微调",
        "strategy": "peer_inheritance",
        "score": 8.5,
        "score_breakdown": {
          "feasibility": 9,
          "novelty": 8,
          "lineage_fit": 8.5
        },
        "inspiration_source": "同门论文：英文问诊微调",
        "research_significance": "...",
        "research_content": [...]
      }
    ]
  }
}
```

### 3.5 门禁规则

| 门禁 | 规则 | 不通过处理 |
|------|------|-----------|
| 候选数量 | ≥3 个 | 重试生成（最多 3 次） |
| 候选评分 | 每个 score ≥6 | 过滤低分，重试生成 |
| 谱系解析 | 必须成功解析 | 提示用户补充谱系信息 |

### 3.6 兜底策略

| 失败场景 | 兜底策略 |
|----------|----------|
| 谱系解析失败 | 提示用户补充导师项目与同门论文信息 |
| 四维创意生成失败 | 回退到 fallback_proposal()，生成简化提案（score=0.4） |
| 候选数量不足 | 重试生成（最多 3 次），仍不足则降低阈值至 5 分 |

---

## 4. 阶段三：重复度评估与硬约束修复

### 4.1 阶段目标

对阶段二生成的候选论题，执行重复度评估与硬约束修复。目标：

1. **重复度评估**：基于候选标题联网检索近 5 年硕博论文与期刊，输出新颖性风险评级。
2. **硬约束修复**：对标题格式、学术日历、文献基线、逻辑自洽执行确定性修复。
3. **质量保障**：确保候选论题合规且具有足够新颖性。

### 4.2 输入

```json
{
  "stage": "validation",
  "input": {
    "candidate": {
      "title": "中文医疗问诊的小样本微调",
      "strategy": "peer_inheritance",
      "score": 8.5,
      "research_content": [...]
    },
    "degree": "master"
  }
}
```

### 4.3 处理流程

```text
1. 调用 Searcher.check_novelty(candidate_title, time_window="5y")：
   - 联网检索近 5 年硕博论文与期刊
   - 计算候选标题与检索结果的语义相似度
   - 输出 novelty_risk（low/medium/high）与 differentiation_gaps
2. 调用 Critic.check_and_repair(proposal)：
   a. 标题格式校验：
      - 长度（硕士 ≤25 字，博士 ≤30 字）
      - 无主动动词开头
      - 不匹配「基于 X 的 Y 研究」模式
   b. 学术日历校验：
      - 硕士 ≤12 月，博士 ≤24 月
   c. 文献基线校验：
      - 硕士 ≥30 篇，博士 ≥50 篇
   d. 逻辑自洽校验：
      - 研究内容与研究目标重合度 ≤70%
3. 对不合规的提案执行自动修复
4. 输出修复后提案 + 校验结果 + 新颖性评估
```

### 4.4 输出

```json
{
  "stage": "validation",
  "status": "success",
  "data": {
    "proposal": {
      "title": "中文医疗问诊的小样本微调",
      "auto_rewritten": false,
      "research_content": [...]
    },
    "validation_results": {
      "title_format": "pass",
      "academic_calendar": "pass",
      "literature_baseline": "warning",
      "logic_consistency": "pass"
    },
    "novelty_assessment": {
      "risk_level": "low",
      "max_similarity": 0.42,
      "differentiation_gaps": ["差异点1", "差异点2"]
    },
    "warnings": ["文献基线不足，已补充检索建议"]
  }
}
```

### 4.5 门禁规则

| 门禁 | 规则 | 不通过处理 |
|------|------|-----------|
| 标题格式 | 长度、动词、模式校验通过 | 自动修复，修复失败则回退到阶段二 |
| 学术日历 | 周期 ≤ 学位上限 | 注入降级策略，标记 WARNING |
| 文献基线 | 数量 ≥ 基线 | 补充检索建议，标记 WARNING |
| 逻辑自洽 | 重合度 ≤70% | 标记 WARNING，提示用户区分 |
| 新颖性 | risk_level ≠ high | high 风险降权或要求用户确认 |

### 4.6 兜底策略

| 失败场景 | 兜底策略 |
|----------|----------|
| 重复度评估超时 | 跳过评估，标记 novelty_unknown |
| 硬约束修复失败 | 标记 WARNING 但不阻塞，传递给阶段四 |
| 新颖性高风险 | 降权处理，要求用户确认后保留 |

---

## 5. 阶段四：多粒度生成与降重脱敏

### 5.1 阶段目标

基于阶段三修复后的提案，调用 Writer 生成多粒度开题报告，并强制执行降重脱敏。目标：

1. **多粒度生成**：按 concise/standard/detailed 三级颗粒度渲染 Markdown。
2. **降重脱敏**：调用 style_normalizer 执行 200+ 禁用词替换、句首过滤、语态互换。
3. **质量保障**：确保报告结构完整、AI 痕迹最小化。

### 5.2 输入

```json
{
  "stage": "generation",
  "input": {
    "proposal": {
      "title": "中文医疗问诊的小样本微调",
      "research_significance": "...",
      "research_content": [...]
    },
    "granularity": "standard",
    "style_neutral": true
  }
}
```

### 5.3 处理流程

```text
1. 调用 Writer.generate_report(proposal, granularity, style_neutral)：
   a. 按 output_granularity.yaml 渲染 Markdown：
      - concise: markdown_depth=2, 3000-5000 字
      - standard: markdown_depth=3, 6000-10000 字
      - detailed: markdown_depth=4, 12000-20000 字
   b. 按 6 章节标准结构生成：
      - 基本信息
      - 选题依据
      - 国内外研究现状
      - 研究内容
      - 技术路线与可行性分析
      - 进度安排
2. 调用 style_normalizer.remove_ai_traces(text)：
   a. 禁用词替换（200+ 条）：
      - "首先" → ""（删除）
      - "其次" → "接着"
      - "最后" → "最终"
      - "综上所述" → "总的来看"
   b. 句首过滤：删除以"首先/其次/再次/最后"开头的句子
   c. 语态互换：被动语态转主动语态
   d. 句长分布：目标均值 15-25 字，标准差 8-12
   e. 并列结构检测：连续 ≥3 个并列结构打破
3. 输出报告 + 降重统计
```

### 5.4 输出

```json
{
  "stage": "generation",
  "status": "success",
  "data": {
    "report": "# 开题报告\n\n## 一、基本信息\n...",
    "mode": "ai",
    "granularity": "standard",
    "word_count": 8542,
    "style_normalizer_applied": true,
    "replacements_count": 47,
    "high_risk_sections": ["国内外研究现状"],
    "file_path": "output/draft_20260619_143022.md"
  }
}
```

### 5.5 门禁规则

| 门禁 | 规则 | 不通过处理 |
|------|------|-----------|
| 报告生成 | 必须成功生成 | 回退到模板兜底模式 |
| 降重执行 | style_normalizer 必须执行 | 阻断输出，强制执行降重 |
| 章节完整 | 6 章节必须完整 | 补充缺失章节 |
| 字数达标 | 字数在颗粒度阈值内 | 调整生成参数重试 |

### 5.6 兜底策略

| 失败场景 | 兜底策略 |
|----------|----------|
| AI 增强模式失败 | 回退到模板兜底模式（mode=template） |
| style_normalizer 失败 | 阻断输出，记录错误，提示用户 |
| 字数不达标 | 调整生成参数重试 |

---

## 6. 阶段五：深度辅助闭环

### 6.1 阶段目标

报告输出后，进入深度辅助闭环，提供文献精读、实验预研、答辩模拟三件套。目标：

1. **深度陪跑**：报告输出后不结束对话，进入后置交互循环。
2. **三件套支持**：提供文献精读工作簿、实验预研映射、答辩模拟轮次。
3. **用户主导**：用户可反复调用任一入口或返回上一阶段，直至主动结束。

### 6.2 输入

```json
{
  "stage": "deep_assist",
  "input": {
    "report": "...",
    "proposal": {...},
    "action": "literature_deep_reader | experiment_designer | thesis_defense_simulator | end"
  }
}
```

### 6.3 处理流程

```text
1. 渲染导航菜单：
   "报告已生成，请选择深度辅助入口：
    1. 文献精读工作簿
    2. 实验预研映射
    3. 答辩模拟
    4. 结束对话"
2. 等待用户选择
3. 根据选择调用对应函数：
   a. literature_deep_reader(research_status, count)：
      - 生成文献精读工作簿
      - 含阅读顺序、关键问题、对比矩阵
   b. experiment_designer(research_content, discipline)：
      - 生成实验预研映射
      - 含变量、对照组、数据集建议
   c. thesis_defense_simulator(key_problems, rounds)：
      - 生成答辩模拟轮次
      - 含评委视角提问、参考回答、追问预案
4. 输出结果后返回步骤 1，继续循环
5. 用户选择"结束对话"时退出
```

### 6.4 输出

```json
{
  "stage": "deep_assist",
  "status": "success",
  "data": {
    "action": "literature_deep_reader",
    "result": {
      "reading_order": [...],
      "key_questions": [...],
      "comparison_matrix": [...]
    }
  },
  "next_action": "请选择下一个深度辅助入口，或结束对话"
}
```

### 6.5 门禁规则

| 门禁 | 规则 | 不通过处理 |
|------|------|-----------|
| 菜单渲染 | 必须渲染导航菜单 | 阻断对话结束，强制渲染 |
| 循环执行 | 不主动结束对话 | 阻断对话结束 |
| 用户结束 | 仅用户主动结束时退出 | 否 |

### 6.6 兜底策略

| 失败场景 | 兜底策略 |
|----------|----------|
| 深度辅助函数失败 | 提示用户重试或选择其他入口 |
| 用户输入无效 | 提示用户选择有效入口 |

---

## 7. 阶段切换规则与门禁

### 7.1 阶段切换矩阵

| 当前阶段 | 下一阶段 | 切换条件 | 不通过处理 |
|----------|----------|----------|-----------|
| 1 信息确权 | 2 谱系解析 | 用户确认 | 阻断，等待确认 |
| 2 谱系解析 | 3 重复度评估 | ≥3 候选且 score ≥6 | 重试生成 |
| 3 重复度评估 | 4 多粒度生成 | 硬约束通过 | 修复重试 |
| 4 多粒度生成 | 5 深度辅助 | 报告生成且降重执行 | 阻断，强制降重 |
| 5 深度辅助 | 结束 | 用户主动结束 | 阻断，继续循环 |

### 7.2 回退规则

| 回退场景 | 触发条件 | 回退目标 |
|----------|----------|----------|
| 阶段二候选不足 | 重试 3 次仍不足 | 回退到阶段一，重新检索 |
| 阶段三硬约束失败 | 修复失败 | 回退到阶段二，重新生成 |
| 阶段四生成失败 | 模板兜底也失败 | 回退到阶段三，重新修复 |
| 用户主动回退 | 用户请求 | 任意上一阶段 |

### 7.3 跳转规则

| 跳转场景 | 触发条件 | 跳转目标 |
|----------|----------|----------|
| 用户跳过确认 | 阶段一用户跳过 | 按 Rule 8 兜底，进入阶段二 |
| 用户要求重生成 | 阶段四用户不满意 | 回退到阶段二，重新生成 |
| 用户要求换方向 | 任意阶段 | 回退到阶段一，重新检索 |
| 用户要求答辩模拟 | 阶段四后 | 跳转到阶段五 |

---

## 8. 重试与兜底逻辑

### 8.1 重试策略

每个阶段的 Agent 调用失败时，采用指数退避重试：

```text
重试次数：最多 3 次
退避策略：指数退避（2s, 4s, 8s）
可重试错误：AGENT_TIMEOUT, AGENT_RATE_LIMIT, AGENT_JSON_PARSE, MODEL_UNAVAILABLE
不可重试错误：HARD_CONSTRAINT_FAIL, SANDBOX_WRITE_FAIL
```

### 8.2 兜底降级链

```text
阶段一兜底：
  Searcher 联网检索失败 → MockSearcher 模拟文献

阶段二兜底：
  Reasoner 生成失败 → fallback_proposal() 简化提案

阶段三兜底：
  Critic 校验失败 → 标记 WARNING 但不阻塞
  重复度评估失败 → 跳过评估，标记 novelty_unknown

阶段四兜底：
  Writer AI 增强失败 → 模板兜底模式
  style_normalizer 失败 → 阻断输出，记录错误

阶段五兜底：
  深度辅助函数失败 → 提示用户重试
```

### 8.3 全局兜底

当所有重试与兜底都失败时：

```text
1. 返回 HTTP 500 错误
2. 记录错误日志（含 session_id, stage, agent_id, error）
3. 提示用户重试或联系管理员
4. 保留已生成的中间结果（如候选列表、报告草稿）
```

---

## 9. ASCII 流程图

### 9.1 完整五阶段流程图

```text
┌─────────────────────────────────────────────────────────────────┐
│                      用户输入                                    │
│   学位 / 学科 / 导师信息 / 用户意图                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段一：信息确权（Searcher）                                    │
│  ─────────────────────────────────────────────────────────────  │
│  1. 解析输入，生成检索式                                         │
│  2. 联网检索近 2 年文献（arXiv + Semantic Scholar）              │
│  3. 展示文献摘要（Top 10）                                       │
│  4. 强制中断，等待用户确认                                       │
│                                                                 │
│  门禁：用户确认？                                                │
│    是 → 进入阶段二                                               │
│    否（调整检索式）→ 重新检索                                    │
│    否（换方向）→ 重新解析输入                                    │
│    否（跳过）→ Rule 8 兜底，进入阶段二                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │ 用户确认
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段二：谱系解析与四维创意（Reasoner）                          │
│  ─────────────────────────────────────────────────────────────  │
│  1. 调用 lineage_parser.parse_lineage(text) 解析谱系             │
│  2. 将阶段一检索结果封装为 search_feeds                          │
│  3. 调用 idea_generator.generate_ideas()：                      │
│     - 导师项目延伸                                               │
│     - 同门成果继承                                               │
│     - 跨域联想                                                   │
│     - 矛盾驱动挖掘                                               │
│  4. 自评分过滤（score < 6 丢弃）                                 │
│  5. 保留 Top 3-5 候选                                            │
│                                                                 │
│  门禁：≥3 候选且 score ≥6？                                      │
│    是 → 进入阶段三                                               │
│    否 → 重试生成（最多 3 次）                                    │
│    重试耗尽 → 回退到阶段一                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ 候选就绪
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段三：重复度评估与硬约束修复（Critic）                        │
│  ─────────────────────────────────────────────────────────────  │
│  1. 调用 Searcher.check_novelty(title, "5y")：                   │
│     - 联网检索近 5 年硕博论文与期刊                              │
│     - 计算语义相似度                                             │
│     - 输出 novelty_risk + differentiation_gaps                  │
│  2. 调用 Critic.check_and_repair(proposal)：                     │
│     - 标题格式校验与修复                                         │
│     - 学术日历校验                                               │
│     - 文献基线校验                                               │
│     - 逻辑自洽校验                                               │
│                                                                 │
│  门禁：硬约束通过？                                              │
│    是 → 进入阶段四                                               │
│    否 → 自动修复，修复失败则回退到阶段二                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │ 校验通过
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段四：多粒度生成与降重脱敏（Writer）                          │
│  ─────────────────────────────────────────────────────────────  │
│  1. 调用 Writer.generate_report(proposal, granularity)：         │
│     - 按 concise/standard/detailed 渲染 Markdown                 │
│     - 6 章节标准结构                                             │
│  2. 调用 style_normalizer.remove_ai_traces(text)：               │
│     - 200+ 禁用词替换                                            │
│     - 句首过滤                                                   │
│     - 语态互换                                                   │
│     - 句长分布调整                                               │
│     - 并列结构打破                                               │
│                                                                 │
│  门禁：报告生成且降重执行？                                      │
│    是 → 进入阶段五                                               │
│    否 → 阻断输出，强制降重                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ 报告就绪
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段五：深度辅助闭环（Mentor）                                  │
│  ─────────────────────────────────────────────────────────────  │
│  1. 渲染导航菜单：                                               │
│     - 文献精读工作簿                                             │
│     - 实验预研映射                                               │
│     - 答辩模拟                                                   │
│     - 结束对话                                                   │
│  2. 等待用户选择                                                 │
│  3. 调用对应函数：                                               │
│     - literature_deep_reader()                                   │
│     - experiment_designer()                                      │
│     - thesis_defense_simulator()                                 │
│  4. 输出结果后返回步骤 1                                         │
│                                                                 │
│  门禁：用户主动结束？                                            │
│    是 → 流程结束                                                 │
│    否 → 继续循环                                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │ 用户结束
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      流程结束                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 回退与跳转流程图

```text
                    ┌─────────────────┐
                    │   阶段一         │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │ 调整检索│    │ 换方向  │    │ 跳过确认│
        └────┬────┘    └────┬────┘    └────┬────┘
             │              │              │
             └──────────────┼──────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │   阶段二         │◄────┐
                    └────────┬────────┘     │
                             │              │
                             ▼              │
                    ┌─────────────────┐     │
                    │   阶段三         │─────┘ 硬约束失败
                    └────────┬────────┘     回退到阶段二
                             │
                             ▼
                    ┌─────────────────┐
                    │   阶段四         │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   阶段五         │◄────┐
                    └────────┬────────┘     │
                             │              │
                             ▼              │
                    ┌─────────────────┐     │
                    │   用户选择       │─────┘
                    │   继续循环       │     继续深度辅助
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   流程结束       │
                    └─────────────────┘
```

---

## 10. 阻断性规则（Rule 7-10）

### 10.1 Rule 7：信息确权门禁

| 项 | 内容 |
|----|------|
| 触发条件 | 解析输入后未执行联网检索、未展示文献摘要、未等待用户确认即进入创意生成 |
| 阻断行为 | 阻断阶段二执行，回退到阶段一补全检索与摘要展示，强制等待用户确认 |
| 实现位置 | Orchestrator 阶段一→阶段二门禁判定 |

### 10.2 Rule 8：时间窗口交互

| 项 | 内容 |
|----|------|
| 触发条件 | 用户跳过确认直接要求生成，或检索时间窗口未按配置（灵感 2 年/查重 5 年） |
| 阻断行为 | 不直接拒绝，先回放已检索摘要并提示"未确认将基于默认热点生成"，再按配置时间窗口补全检索 |
| 实现位置 | Orchestrator 阶段一用户跳过处理 |

### 10.3 Rule 9：降重去 AI 化优先级

| 项 | 内容 |
|----|------|
| 触发条件 | generate_report 输出后未调用 style_normalizer.remove_ai_traces，或 style_normalizer 优先级低于排版 |
| 阻断行为 | 阻断最终输出，强制在 Markdown 渲染后调用 remove_ai_traces，确保 200+ 禁用词替换、句首过滤、语态互换执行完毕 |
| 实现位置 | Writer 阶段四降重门禁 |

### 10.4 Rule 10：后置交互循环

| 项 | 内容 |
|----|------|
| 触发条件 | 报告输出后直接结束对话，未渲染深度辅助导航菜单 |
| 阻断行为 | 阻断对话结束，强制渲染文献精读/实验预研/答辩模拟三件套导航菜单，进入后置交互循环等待用户选择 |
| 实现位置 | Orchestrator 阶段五门禁判定 |

---

## 11. 状态持久化与恢复

### 11.1 状态持久化

每个阶段执行后，将当前状态持久化到 `conversations.context`：

```json
{
  "current_stage": "creativity",
  "active_agent": "reasoner",
  "stage_history": [
    { "stage": "info_confirm", "status": "completed", "timestamp": "..." },
    { "stage": "creativity", "status": "in_progress", "timestamp": "..." }
  ],
  "stage_data": {
    "info_confirm": {
      "search_results": [...],
      "user_confirmed": true
    },
    "creativity": {
      "candidates": [...]
    }
  },
  "dst_state": {...}
}
```

### 11.2 状态恢复

会话中断后恢复时，根据 `current_stage` 恢复到中断位置：

```python
def resume_conversation(conversation_id: str):
    """恢复对话到中断位置。"""
    conversation = get_conversation(conversation_id)
    context = json.loads(conversation["context"])

    current_stage = context["current_stage"]
    stage_data = context["stage_data"]

    if current_stage == "info_confirm":
        # 恢复到阶段一，重新展示摘要并等待确认
        return render_search_results(stage_data["info_confirm"]["search_results"])
    elif current_stage == "creativity":
        # 恢复到阶段二，继续生成候选
        return resume_creativity(stage_data)
    # ... 其他阶段
```

### 11.3 中断场景

| 中断场景 | 恢复方式 |
|----------|----------|
| 用户关闭浏览器 | 下次打开时恢复到中断位置 |
| 服务重启 | 从数据库恢复会话状态 |
| Agent 调用超时 | 重试当前阶段 |
| 用户主动中断 | 保留状态，用户可随时恢复 |

---

## 12. 多对话场景下的阶段管理

### 12.1 多对话隔离

同一会话下的多个对话线程，每个对话有独立的阶段状态：

```text
会话 A
  ├── 对话 1（阶段三：重复度评估）
  ├── 对话 2（阶段一：信息确权）
  └── 对话 3（阶段五：深度辅助）
```

### 12.2 跨对话共享

仅以下信息在会话级共享：

- 学位、学科、导师信息
- 候选论题列表（阶段二生成后）
- 谱系图

### 12.3 阶段独立性

每个对话的阶段状态独立，可同时处于不同阶段：

```python
def get_conversation_stage(conversation_id: str) -> str:
    """获取对话的当前阶段。"""
    conversation = get_conversation(conversation_id)
    context = json.loads(conversation["context"])
    return context.get("current_stage", "info_confirm")
```

---

## 13. 性能与成本考量

### 13.1 性能指标

| 阶段 | 目标延迟 | 主要耗时 |
|------|----------|----------|
| 阶段一 | < 10s | 联网检索 |
| 阶段二 | < 15s | 四维创意生成 |
| 阶段三 | < 10s | 重复度评估 + 硬约束 |
| 阶段四 | < 20s | 报告生成 + 降重 |
| 阶段五 | < 5s/次 | 深度辅助函数 |
| 总计 | < 60s | - |

### 13.2 成本指标

| 阶段 | 目标成本 | 主要成本 |
|------|----------|----------|
| 阶段一 | < 0.5 元 | Searcher 联网检索 |
| 阶段二 | < 1.5 元 | Reasoner 四维创意 |
| 阶段三 | < 0.8 元 | Critic 校验 + Searcher 重复度 |
| 阶段四 | < 2.0 元 | Writer 报告生成 |
| 阶段五 | < 0.2 元/次 | Mentor 深度辅助 |
| 总计 | < 5 元 | - |

### 13.3 优化建议

1. **并行化**：阶段三的 Critic 与 Mentor 可并行执行。
2. **缓存优化**：保持 Prompt 前缀稳定，提升缓存命中率。
3. **流式响应**：阶段四的 Writer 采用 SSE 流式推送。
4. **模型路由**：简单任务用低成本模型，复杂任务用高质量模型。

---

## 14. 附录

### 14.1 阶段配置示例

```yaml
# config/agents/orchestrator.yaml 中的 stages 配置
stages:
  - id: info_confirm
    name: 信息确权
    agent: searcher
    gate_rules:
      require_user_confirmation: true
      require_search_results: true
    retry:
      max_attempts: 3
    fallback:
      strategy: mock_searcher

  - id: creativity
    name: 谱系解析与四维创意
    agent: reasoner
    gate_rules:
      min_candidates: 3
      min_score: 6.0
    retry:
      max_attempts: 3
    fallback:
      strategy: fallback_proposal
      confidence_score: 0.4

  - id: validation
    name: 重复度评估与硬约束修复
    agent: critic
    gate_rules:
      hard_constraints_pass: true
    retry:
      max_attempts: 2
    fallback:
      strategy: mark_warning

  - id: generation
    name: 多粒度生成与降重脱敏
    agent: writer
    gate_rules:
      report_generated: true
      style_normalizer_applied: true
    retry:
      max_attempts: 2
    fallback:
      strategy: template_mode

  - id: deep_assist
    name: 深度辅助闭环
    agent: mentor
    gate_rules:
      require_menu_render: true
      require_user_end: true
    retry:
      max_attempts: 1
    fallback:
      strategy: prompt_retry
```

### 14.2 阶段状态枚举

```python
class StageStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class Stage(str, Enum):
    INFO_CONFIRM = "info_confirm"
    CREATIVITY = "creativity"
    VALIDATION = "validation"
    GENERATION = "generation"
    DEEP_ASSIST = "deep_assist"
```

### 14.3 术语表

| 术语 | 定义 |
|------|------|
| 五阶段闭环 | 信息确权 → 谱系解析 → 重复度评估 → 多粒度生成 → 深度辅助 |
| 门禁 | 阶段切换的判定规则 |
| 回退 | 阶段失败时返回上一阶段 |
| 跳转 | 用户主动切换阶段 |
| 兜底降级 | Agent 失败时的备用方案 |
| Rule 7 | 信息确权门禁 |
| Rule 8 | 时间窗口交互 |
| Rule 9 | 降重去 AI 化优先级 |
| Rule 10 | 后置交互循环 |
| search_feeds | 阶段一检索结果，注入阶段二 |
| novelty_risk | 新颖性风险评级（low/medium/high） |
| differentiation_gaps | 差异化空档 |
| style_normalizer | 降重脱敏工具 |

### 14.4 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v8.0 | 2026-06-19 | 初始版本，定义五阶段闭环导航流 |
| v8.1 | （规划中） | 新增阶段并行执行 |
| v8.2 | （规划中） | 新增用户自定义阶段 |

---

> 文档版本 v8.0 · 最后更新 2026-06-19 · 维护者：ThesisMiner 团队
