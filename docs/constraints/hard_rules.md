# ThesisMiner v8.0 硬约束规则库

> **版本**：v8.0
> **日期**：2026-06-19
> **适用范围**：`backend/constraints/`、`backend/orchestration/hooks/hard_rule_interceptor.py`
> **关联配置**：`config/constraints/hard_rules.yaml`

---

## 目录

1. [硬约束总览](#1-硬约束总览)
2. [标题长度约束](#2-标题长度约束)
3. [标题动词约束](#3-标题动词约束)
4. [标题模式约束](#4-标题模式约束)
5. [学科匹配规则](#5-学科匹配规则)
6. [导师方向对齐规则](#6-导师方向对齐规则)
7. [时间可行性约束](#7-时间可行性约束)
8. [文献基线约束](#8-文献基线约束)
9. [重复度阈值约束](#9-重复度阈值约束)
10. [逻辑自洽约束](#10-逻辑自洽约束)
11. [约束严重级别](#11-约束严重级别)
12. [约束校验流程](#12-约束校验流程)
13. [自动修复策略](#13-自动修复策略)
14. [附录](#14-附录)

---

## 1. 硬约束总览

### 1.1 设计目标

硬约束规则库是 ThesisMiner v8.0 质量保障体系的核心，确保生成的论题与开题报告符合学术规范。设计目标：

1. **学术合规**：确保论题符合学位论文规范（标题长度、研究周期、文献基线等）。
2. **可行性**：确保论题在学制内可完成，避免不切实际的研究范围。
3. **新颖性**：确保论题与已有研究有足够差异，避免重复。
4. **可执行**：每条规则有明确的校验逻辑与错误信息，便于自动化执行。
5. **可修复**：对不合规的论题提供自动修复策略，减少人工干预。

### 1.2 约束分类

| 类别 | 约束项 | 严重级别 |
|------|--------|----------|
| 标题格式 | 长度、动词、模式 | error |
| 学科匹配 | 学科一致性 | error |
| 导师对齐 | 方向一致性 | warning |
| 时间可行性 | 研究周期 | error/warning |
| 文献基线 | 文献数量 | warning |
| 重复度 | 相似度阈值 | error/warning |
| 逻辑自洽 | 内容与目标重合度 | warning |

### 1.3 约束规则模板

每条约束规则包含以下字段：

```yaml
- id: "约束唯一标识"
  name: "约束名称"
  category: "约束类别"
  description: "约束描述"
  validation_logic: "校验逻辑（伪代码或正则）"
  error_message: "错误信息模板"
  severity: "error | warning"
  auto_repair: "自动修复策略"
  enabled: true
```

---

## 2. 标题长度约束

### 2.1 规则定义

```yaml
- id: "title_length"
  name: "标题长度约束"
  category: "标题格式"
  description: "论题标题长度必须在规定范围内，硕士 ≤25 字，博士 ≤30 字，最小 8 字"
  validation_logic: |
    if degree == "master":
        return 8 <= len(title) <= 25
    elif degree == "doctor":
        return 8 <= len(title) <= 30
  error_message: "标题长度不合规：当前 {actual} 字，{degree} 要求 {min}-{max} 字"
  severity: "error"
  auto_repair: "依存句法截取核心名词短语"
  enabled: true
```

### 2.2 校验逻辑

```python
def validate_title_length(title: str, degree: str) -> dict:
    """校验标题长度。"""
    if degree == "master":
        min_len, max_len = 8, 25
    elif degree == "doctor":
        min_len, max_len = 8, 30
    else:
        return {"valid": False, "reason": "未知学位类型"}

    actual_len = len(title)
    if actual_len < min_len:
        return {
            "valid": False,
            "reason": f"标题过短：当前 {actual_len} 字，最少 {min_len} 字",
            "auto_repair": "expand_title"  # 扩展标题
        }
    elif actual_len > max_len:
        return {
            "valid": False,
            "reason": f"标题过长：当前 {actual_len} 字，最多 {max_len} 字",
            "auto_repair": "truncate_title"  # 截取核心名词短语
        }
    return {"valid": True}
```

### 2.3 自动修复

```python
def repair_title_length(title: str, degree: str) -> str:
    """修复标题长度。"""
    if degree == "master":
        max_len = 25
    else:
        max_len = 30

    if len(title) > max_len:
        # 依存句法截取核心名词短语
        return extract_core_noun_phrase(title, max_len)
    elif len(title) < 8:
        # 扩展标题（添加修饰语）
        return expand_title_with_modifiers(title)
    return title
```

---

## 3. 标题动词约束

### 3.1 规则定义

```yaml
- id: "title_verb_prefix"
  name: "标题动词前置约束"
  category: "标题格式"
  description: "标题不以主动动词开头（研究/分析/探讨/调查/实现/构建/设计/开发/优化/改进/评估/验证）"
  validation_logic: |
    forbidden_verbs = ["研究", "分析", "探讨", "调查", "实现", "构建",
                       "设计", "开发", "优化", "改进", "评估", "验证"]
    first_word = extract_first_word(title)
    return first_word not in forbidden_verbs
  error_message: "标题以主动动词「{verb}」开头，应转换为名词性短语"
  severity: "error"
  auto_repair: "动词前置转名词性短语（研究 X → X 的研究）"
  enabled: true
```

### 3.2 校验逻辑

```python
FORBIDDEN_VERBS = [
    "研究", "分析", "探讨", "调查", "实现", "构建",
    "设计", "开发", "优化", "改进", "评估", "验证"
]

def validate_title_verb(title: str) -> dict:
    """校验标题动词前置。"""
    for verb in FORBIDDEN_VERBS:
        if title.startswith(verb):
            return {
                "valid": False,
                "reason": f"标题以主动动词「{verb}」开头",
                "auto_repair": "convert_to_noun_phrase"
            }
    return {"valid": True}
```

### 3.3 自动修复

```python
def repair_title_verb(title: str) -> str:
    """修复标题动词前置。"""
    for verb in FORBIDDEN_VERBS:
        if title.startswith(verb):
            # "研究 X" → "X 的研究"
            rest = title[len(verb):].strip()
            return f"{rest}的{verb}"
    return title
```

---

## 4. 标题模式约束

### 4.1 规则定义

```yaml
- id: "title_pattern"
  name: "标题模式约束"
  category: "标题格式"
  description: "标题不匹配「基于 X 的 Y 研究」套路模式"
  validation_logic: |
    import re
    pattern = r"基于.+的.+研究"
    return not re.match(pattern, title)
  error_message: "标题匹配「基于 X 的 Y 研究」套路模式，应重组为突出核心贡献的名词短语"
  severity: "error"
  auto_repair: "重组为突出核心贡献的名词短语"
  enabled: true
```

### 4.2 校验逻辑

```python
import re

FORBIDDEN_PATTERNS = [
    r"基于.+的.+研究",
    r"基于.+的.+分析",
    r"基于.+的.+探讨",
    r"基于.+的.+应用",
    r"基于.+的.+设计",
    r"基于.+的.+实现",
]

def validate_title_pattern(title: str) -> dict:
    """校验标题模式。"""
    for pattern in FORBIDDEN_PATTERNS:
        if re.match(pattern, title):
            return {
                "valid": False,
                "reason": f"标题匹配套路模式「{pattern}」",
                "auto_repair": "reconstruct_noun_phrase"
            }
    return {"valid": True}
```

### 4.3 自动修复

```python
def repair_title_pattern(title: str) -> str:
    """修复标题模式。"""
    # "基于 X 的 Y 研究" → "面向 X 的 Y" 或 "X 驱动的 Y"
    match = re.match(r"基于(.+)的(.+?)研究", title)
    if match:
        x, y = match.groups()
        return f"面向{x}的{y}"
    return title
```

---

## 5. 学科匹配规则

### 5.1 规则定义

```yaml
- id: "discipline_match"
  name: "学科匹配约束"
  category: "学科匹配"
  description: "论题学科必须与会话学科一致，或属于相关学科领域"
  validation_logic: |
    if discipline is None:
        return True  # 未指定学科时不校验
    related_disciplines = get_related_disciplines(discipline)
    return proposal_discipline in related_disciplines
  error_message: "论题学科「{actual}」与会话学科「{expected}」不匹配"
  severity: "error"
  auto_repair: "调整论题学科描述"
  enabled: true
```

### 5.2 学科关系映射

```python
DISCIPLINE_RELATIONS = {
    "计算机科学": ["计算机科学", "人工智能", "软件工程", "数据科学", "信息工程"],
    "人工智能": ["人工智能", "计算机科学", "机器学习", "深度学习"],
    "医学": ["医学", "临床医学", "生物医学", "医疗信息学"],
    "教育学": ["教育学", "教育技术", "心理学", "课程与教学论"],
    # ... 更多学科关系
}

def get_related_disciplines(discipline: str) -> list:
    """获取相关学科列表。"""
    return DISCIPLINE_RELATIONS.get(discipline, [discipline])
```

### 5.3 校验逻辑

```python
def validate_discipline_match(proposal_discipline: str, session_discipline: str) -> dict:
    """校验学科匹配。"""
    if session_discipline is None:
        return {"valid": True}

    related = get_related_disciplines(session_discipline)
    if proposal_discipline not in related:
        return {
            "valid": False,
            "reason": f"论题学科「{proposal_discipline}」与会话学科「{session_discipline}」不匹配",
            "auto_repair": "adjust_discipline"
        }
    return {"valid": True}
```

---

## 6. 导师方向对齐规则

### 6.1 规则定义

```yaml
- id: "advisor_alignment"
  name: "导师方向对齐约束"
  category: "导师对齐"
  description: "论题应与导师项目方向对齐，或与同门论文有继承关系"
  validation_logic: |
    advisor_projects = parse_advisor_projects(mentor_info)
    alignment_score = compute_alignment(proposal_title, advisor_projects)
    return alignment_score >= 0.3
  error_message: "论题与导师项目方向对齐度低（{score} < 0.3）"
  severity: "warning"
  auto_repair: "提示用户确认论题与导师方向的关系"
  enabled: true
```

### 6.2 对齐度计算

```python
def compute_alignment(proposal_title: str, advisor_projects: list) -> float:
    """计算论题与导师项目的对齐度。"""
    if not advisor_projects:
        return 0.5  # 无导师项目信息时默认中等对齐

    max_score = 0
    for project in advisor_projects:
        # 基于关键词重叠计算对齐度
        proposal_keywords = extract_keywords(proposal_title)
        project_keywords = extract_keywords(project)
        overlap = len(set(proposal_keywords) & set(project_keywords))
        score = overlap / max(len(proposal_keywords), 1)
        max_score = max(max_score, score)

    return max_score
```

---

## 7. 时间可行性约束

### 7.1 规则定义

```yaml
- id: "time_feasibility"
  name: "时间可行性约束"
  category: "时间可行性"
  description: "研究周期必须在学制内，硕士 ≤12 个月，博士 ≤24 个月"
  validation_logic: |
    if degree == "master":
        return timeframe_months <= 12
    elif degree == "doctor":
        return timeframe_months <= 24
  error_message: "研究周期超期：当前 {actual} 个月，{degree} 要求 ≤ {max} 个月"
  severity: "error"
  auto_repair: "注入分阶段并行执行降级策略"
  enabled: true
```

### 7.2 校验逻辑

```python
def validate_time_feasibility(timeframe_months: int, degree: str) -> dict:
    """校验时间可行性。"""
    if degree == "master":
        max_months = 12
    elif degree == "doctor":
        max_months = 24
    else:
        return {"valid": False, "reason": "未知学位类型"}

    if timeframe_months > max_months:
        return {
            "valid": False,
            "reason": f"研究周期超期：当前 {timeframe_months} 个月，{degree} 要求 ≤ {max_months} 个月",
            "auto_repair": "inject_parallel_strategy"
        }
    return {"valid": True}
```

### 7.3 自动修复

```python
def repair_time_feasibility(research_content: list, degree: str) -> list:
    """修复时间可行性。"""
    # 注入"分阶段并行执行"降级策略
    parallel_note = {
        "phase": "并行执行策略",
        "description": "由于研究周期较长，建议采用分阶段并行执行策略，"
                      "将独立子任务并行推进，缩短总周期。"
    }
    research_content.append(parallel_note)
    return research_content
```

---

## 8. 文献基线约束

### 8.1 规则定义

```yaml
- id: "literature_baseline"
  name: "文献基线约束"
  category: "文献基线"
  description: "综述大纲至少规划硕士 30 篇 / 博士 50 篇文献的检索方向"
  validation_logic: |
    if degree == "master":
        return literature_count >= 30
    elif degree == "doctor":
        return literature_count >= 50
  error_message: "文献基线不足：当前 {actual} 篇，{degree} 要求 ≥ {min} 篇"
  severity: "warning"
  auto_repair: "补充子方向检索词与数据库建议"
  enabled: true
```

### 8.2 校验逻辑

```python
def validate_literature_baseline(literature_count: int, degree: str) -> dict:
    """校验文献基线。"""
    if degree == "master":
        min_count = 30
    elif degree == "doctor":
        min_count = 50
    else:
        return {"valid": False, "reason": "未知学位类型"}

    if literature_count < min_count:
        return {
            "valid": False,
            "reason": f"文献基线不足：当前 {literature_count} 篇，{degree} 要求 ≥ {min_count} 篇",
            "auto_repair": "supplement_search_suggestions"
        }
    return {"valid": True}
```

---

## 9. 重复度阈值约束

### 9.1 规则定义

```yaml
- id: "duplication_threshold"
  name: "重复度阈值约束"
  category: "重复度"
  description: "论题与已有研究的相似度必须 < 30%，新颖性评分 ≥60"
  validation_logic: |
    return max_similarity < 0.3 and novelty_score >= 60
  error_message: "重复度过高：相似度 {similarity} ≥ 0.3，或新颖性评分 {score} < 60"
  severity: "error"
  auto_repair: "调整论题差异化方向"
  enabled: true
```

### 9.2 校验逻辑

```python
def validate_duplication(max_similarity: float, novelty_score: int) -> dict:
    """校验重复度。"""
    if max_similarity >= 0.3:
        return {
            "valid": False,
            "reason": f"重复度过高：相似度 {max_similarity:.2f} ≥ 0.3",
            "auto_repair": "adjust_differentiation"
        }
    if novelty_score < 60:
        return {
            "valid": False,
            "reason": f"新颖性评分不足：{novelty_score} < 60",
            "auto_repair": "adjust_differentiation"
        }
    return {"valid": True}
```

### 9.3 风险评级

```python
def assess_novelty_risk(max_similarity: float) -> str:
    """评估新颖性风险。"""
    if max_similarity < 0.5:
        return "low"
    elif max_similarity < 0.7:
        return "medium"
    else:
        return "high"
```

---

## 10. 逻辑自洽约束

### 10.1 规则定义

```yaml
- id: "logic_consistency"
  name: "逻辑自洽约束"
  category: "逻辑自洽"
  description: "研究内容与研究目标的语义重合度 ≤70%"
  validation_logic: |
    overlap = compute_semantic_overlap(research_content, research_objective)
    return overlap <= 0.7
  error_message: "研究内容与研究目标重合度过高：{overlap} > 0.7"
  severity: "warning"
  auto_repair: "标记 WARNING，提示用户区分「做什么」与「达成什么」"
  enabled: true
```

### 10.2 重合度计算

```python
def compute_semantic_overlap(content: str, objective: str) -> float:
    """计算语义重合度。"""
    content_keywords = set(extract_keywords(content))
    objective_keywords = set(extract_keywords(objective))

    if not content_keywords or not objective_keywords:
        return 0.0

    intersection = content_keywords & objective_keywords
    union = content_keywords | objective_keywords
    return len(intersection) / len(union)  # Jaccard 相似度
```

---

## 11. 约束严重级别

### 11.1 严重级别定义

| 级别 | 含义 | 处理方式 |
|------|------|----------|
| error | 严重错误，必须修复 | 阻断流程，自动修复或回退 |
| warning | 警告，建议修复 | 标记 WARNING，继续流程 |

### 11.2 约束严重级别映射

| 约束 ID | 严重级别 | 阻断流程 |
|---------|----------|----------|
| title_length | error | 是 |
| title_verb_prefix | error | 是 |
| title_pattern | error | 是 |
| discipline_match | error | 是 |
| advisor_alignment | warning | 否 |
| time_feasibility | error | 是（超期） |
| literature_baseline | warning | 否 |
| duplication_threshold | error | 是（高重复） |
| logic_consistency | warning | 否 |

---

## 12. 约束校验流程

### 12.1 校验顺序

```text
1. 标题格式校验（length → verb → pattern）
2. 学科匹配校验
3. 导师方向对齐校验
4. 时间可行性校验
5. 文献基线校验
6. 重复度校验
7. 逻辑自洽校验
```

### 12.2 校验流程图

```text
┌─────────────────┐
│  开始校验        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 标题长度校验     │──error──► 自动修复 ──修复失败──► 阻断
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ 标题动词校验     │──error──► 自动修复 ──修复失败──► 阻断
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ 标题模式校验     │──error──► 自动修复 ──修复失败──► 阻断
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ 学科匹配校验     │──error──► 阻断
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ 导师对齐校验     │──warning──► 标记 WARNING
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ 时间可行性校验   │──error──► 自动修复 ──修复失败──► 阻断
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ 文献基线校验     │──warning──► 标记 WARNING
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ 重复度校验       │──error──► 阻断
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ 逻辑自洽校验     │──warning──► 标记 WARNING
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│  校验通过        │
└─────────────────┘
```

---

## 13. 自动修复策略

### 13.1 修复策略清单

| 约束 | 修复策略 | 修复示例 |
|------|----------|----------|
| 标题长度（过长） | 依存句法截取核心名词短语 | "基于深度学习的医疗大模型在中文问诊中的小样本微调研究" → "医疗大模型中文问诊微调" |
| 标题长度（过短） | 添加修饰语扩展 | "问诊微调" → "医疗大模型中文问诊的小样本微调" |
| 标题动词 | 动词前置转名词性短语 | "研究 X" → "X 的研究" |
| 标题模式 | 重组为突出核心贡献的名词短语 | "基于 X 的 Y 研究" → "面向 X 的 Y" |
| 时间可行性 | 注入分阶段并行执行策略 | 添加"分阶段并行执行"提示 |
| 文献基线 | 补充子方向检索词与数据库建议 | 添加检索词与数据库建议 |
| 重复度 | 调整论题差异化方向 | 提示用户调整差异化方向 |
| 逻辑自洽 | 标记 WARNING，提示用户区分 | 添加 WARNING 标记 |

### 13.2 修复失败处理

当自动修复失败时：

1. 记录修复失败日志
2. 返回原始提案 + WARNING 标记
3. 阻断流程，提示用户手动修复

---

## 14. 附录

### 14.1 约束规则完整列表

```yaml
constraints:
  - id: title_length
    name: 标题长度约束
    category: 标题格式
    severity: error
    enabled: true

  - id: title_verb_prefix
    name: 标题动词前置约束
    category: 标题格式
    severity: error
    enabled: true

  - id: title_pattern
    name: 标题模式约束
    category: 标题格式
    severity: error
    enabled: true

  - id: discipline_match
    name: 学科匹配约束
    category: 学科匹配
    severity: error
    enabled: true

  - id: advisor_alignment
    name: 导师方向对齐约束
    category: 导师对齐
    severity: warning
    enabled: true

  - id: time_feasibility
    name: 时间可行性约束
    category: 时间可行性
    severity: error
    enabled: true

  - id: literature_baseline
    name: 文献基线约束
    category: 文献基线
    severity: warning
    enabled: true

  - id: duplication_threshold
    name: 重复度阈值约束
    category: 重复度
    severity: error
    enabled: true

  - id: logic_consistency
    name: 逻辑自洽约束
    category: 逻辑自洽
    severity: warning
    enabled: true
```

### 14.2 术语表

| 术语 | 定义 |
|------|------|
| 硬约束 | 必须满足的约束，违反时阻断流程 |
| 软约束 | 建议满足的约束，违反时标记 WARNING |
| 自动修复 | 对不合规的论题自动执行修复策略 |
| 严重级别 | error（阻断）或 warning（标记） |
| 重复度 | 论题与已有研究的相似度 |
| 新颖性评分 | 基于四维创意的评分（0-100） |
| 文献基线 | 综述大纲规划的文献数量下限 |
| 学术日历 | 学位对应的研究周期上限 |

### 14.3 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v8.0 | 2026-06-19 | 初始版本，定义 9 条硬约束 |
| v8.1 | （规划中） | 新增伦理审查约束 |
| v8.2 | （规划中） | 新增数据合规约束 |

---

> 文档版本 v8.0 · 最后更新 2026-06-19 · 维护者：ThesisMiner 团队
