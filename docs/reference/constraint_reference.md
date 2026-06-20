# ThesisMiner v8.0 约束规则参考文档

> **版本**：v8.0.0
> **最后更新**：2026-06-20
> **适用范围**：`backend/constraints/`、`config/constraints/`、`backend/agents/`
> **文档状态**：正式发布（Stable）

---

## 目录

- [1. 文档概述](#1-文档概述)
- [2. 约束系统架构](#2-约束系统架构)
- [3. 硬约束规则](#3-硬约束规则)
- [4. 新颖性评分系统](#4-新颖性评分系统)
- [5. AI 痕迹去除规则](#5-ai-痕迹去除规则)
- [6. 多粒度生成规则](#6-多粒度生成规则)
- [7. 五阶段门控](#7-五阶段门控)
- [8. 规则引擎](#8-规则引擎)
- [9. 样式规范化规则](#9-样式规范化规则)
- [10. Prompt 模板](#10-prompt-模板)
- [11. 评估标准](#11-评估标准)
- [12. 规则目录](#12-规则目录)
- [13. 配置参考](#13-配置参考)
- [14. 附录](#14-附录)

---

## 1. 文档概述

### 1.1 文档目的

本文档是 ThesisMiner v8.0 约束规则的完整参考手册，涵盖：

- 硬约束规则（标题、时间线、文献基线、查重等）
- 新颖性评分系统（四维权重、阈值、风险等级）
- AI 痕迹去除规则
- 多粒度生成规则
- 五阶段门控机制
- 规则引擎（RuleChain、ConflictResolver、PREDEFINED_RULES）

### 1.2 面向读者

- **后端开发者**：需要修改或扩展约束规则的开发人员
- **架构师**：需要理解约束系统设计的系统设计人员
- **运维工程师**：需要排查约束相关故障的运维人员
- **研究者**：希望了解约束系统设计的学术研究人员

### 1.3 约束系统设计理念

ThesisMiner v8.0 的约束系统遵循以下设计理念：

```
┌─────────────────────────────────────────────────────────────────┐
│                    约束系统设计理念                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 硬约束（Hard Rules）                                         │
│     - 必须满足的规则，违反则拒绝                                  │
│     - 如：标题长度、禁用词、时间线                                │
│                                                                 │
│  2. 软约束（Soft Rules）                                         │
│     - 建议遵守的规则，违反则警告                                  │
│     - 如：文献数量、引用格式                                      │
│                                                                 │
│  3. 评分约束（Score Constraints）                                │
│     - 基于评分的约束，低于阈值则不通过                            │
│     - 如：新颖性分数、Critic 评分                                │
│                                                                 │
│  4. 门控约束（Gate Constraints）                                 │
│     - 阶段流转的控制约束                                          │
│     - 如：score ≥ 60 才能进入下一阶段                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 硬约束 | Hard Rule | 必须满足的规则 |
| 软约束 | Soft Rule | 建议遵守的规则 |
| 新颖性 | Novelty | 选题与已有文献的差异程度 |
| 门控 | Gate | 控制阶段流转的机制 |
| 规则链 | Rule Chain | 按顺序执行的规则集合 |
| 冲突解决 | Conflict Resolution | 多规则冲突时的解决策略 |
| 严重级别 | Severity | 规则违反的严重程度 |
| 规则类型 | Rule Type | 规则的分类 |

---

## 2. 约束系统架构

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      约束系统架构                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    规则引擎 (Rule Engine)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - RuleChain: 按顺序执行规则链                           │   │
│  │  - ConflictResolver: 解决规则冲突                        │   │
│  │  - PREDEFINED_RULES: 50+ 预定义规则                      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │ 硬约束  │ │ 新颖性  │ │ AI痕迹 │ │ 多粒度 │ │ 阶段门控│
   │  规则  │ │  评分  │ │  去除  │ │  生成  │ │        │
   └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    配置文件 (YAML)                               │
│  - hard_rules.yaml                                              │
│  - novelty_weights.yaml                                         │
│  - style_normalizer_rules.yaml                                  │
│  - evaluation_rubric.yaml                                       │
│  - rule_catalog.yaml                                            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块

```python
# backend/constraints/ 模块结构
backend/constraints/
├── __init__.py
├── hard_rules.py           # 硬约束规则
├── rule_engine.py          # 规则引擎
├── stage_gate.py           # 阶段门控
├── novelty_scorer.py       # 新颖性评分
├── style_normalizer.py     # 样式规范化
├── ai_trace_remover.py     # AI 痕迹去除
└── evaluator.py            # 评估器
```

### 2.3 规则执行流程

```
[输入: 选题/报告]
       │
       ▼
[1. 硬约束检查]
       │
       ├── 通过 ──▶ [2. 新颖性评分]
       │                │
       │                ├── 通过 ──▶ [3. AI痕迹去除]
       │                │                │
       │                │                ├── 通过 ──▶ [4. 多粒度生成]
       │                │                │                │
       │                │                │                ├── 通过 ──▶ [5. 阶段门控]
       │                │                │                │                │
       │                │                │                │                ├── 通过 ──▶ [成功]
       │                │                │                │                │
       │                │                │                │                └── 失败 ──▶ [重试/兜底]
       │                │                │                │
       │                │                │                └── 失败 ──▶ [修正]
       │                │                │
       │                │                └── 失败 ──▶ [修正]
       │                │
       │                └── 失败 ──▶ [重新生成]
       │
       └── 失败 ──▶ [拒绝]
```

---

## 3. 硬约束规则

### 3.1 硬约束概述

硬约束是必须满足的规则，违反则直接拒绝。ThesisMiner v8.0 定义了以下硬约束类别：

| 类别 | 规则数 | 严重级别 | 失败处理 |
|------|--------|----------|----------|
| 标题约束 | 8 | ERROR | 拒绝生成 |
| 时间线约束 | 5 | ERROR | 拒绝生成 |
| 文献基线 | 6 | WARNING | 标记警告 |
| 查重阈值 | 4 | ERROR | 拒绝生成 |
| 学科匹配 | 3 | WARNING | 标记警告 |
| 导师对齐 | 3 | WARNING | 标记警告 |

### 3.2 标题约束

#### 3.2.1 标题长度约束

```python
# backend/constraints/hard_rules.py
from dataclasses import dataclass
from typing import List

@dataclass
class HardRuleViolation:
    """硬约束违反"""
    rule_id: str
    rule_name: str
    severity: str  # ERROR / WARNING
    message: str
    actual_value: any
    expected_value: any

def validate_title(title: str, degree: str) -> List[HardRuleViolation]:
    """验证标题"""
    violations = []
    
    # 规则 1: 标题长度
    if degree == "硕士":
        max_length = 25
    elif degree == "博士":
        max_length = 30
    else:
        max_length = 25  # 默认
    
    if len(title) > max_length:
        violations.append(HardRuleViolation(
            rule_id="TITLE_LENGTH",
            rule_name="标题长度约束",
            severity="ERROR",
            message=f"标题长度 {len(title)} 超过 {degree}限制 {max_length} 字",
            actual_value=len(title),
            expected_value=max_length
        ))
    
    # 规则 2: 标题非空
    if not title.strip():
        violations.append(HardRuleViolation(
            rule_id="TITLE_EMPTY",
            rule_name="标题非空约束",
            severity="ERROR",
            message="标题不能为空",
            actual_value=title,
            expected_value="非空字符串"
        ))
    
    # 规则 3: 禁止"基于"开头
    if title.startswith("基于"):
        violations.append(HardRuleViolation(
            rule_id="TITLE_FORBIDDEN_PREFIX",
            rule_name="标题禁用前缀",
            severity="ERROR",
            message='标题不应以"基于"开头',
            actual_value=title[:10],
            expected_value="不以'基于'开头"
        ))
    
    # 规则 4: 禁用词检查
    forbidden_words = ["研究", "应用", "探讨", "浅析", "初探"]
    for word in forbidden_words:
        if title.endswith(word) and len(title) <= 10:
            violations.append(HardRuleViolation(
                rule_id="TITLE_FORBIDDEN_WORD",
                rule_name="标题禁用词",
                severity="WARNING",
                message=f'标题以空泛词"{word}"结尾',
                actual_value=title,
                expected_value="具体的研究内容"
            ))
    
    return violations
```

#### 3.2.2 标题约束配置

```yaml
# config/constraints/hard_rules.yaml
title:
  # 长度约束
  length:
    master: 25        # 硕士标题 ≤25 字
    doctor: 30        # 博士标题 ≤30 字
    default: 25
  
  # 禁用前缀
  forbidden_prefixes:
    - "基于"
    - "关于"
    - "浅谈"
    - "试论"
  
  # 禁用后缀（短标题时）
  forbidden_suffixes_short:
    - "研究"
    - "应用"
    - "探讨"
    - "浅析"
    - "初探"
  
  # 必须包含
  required_elements:
    - 研究对象
    - 研究方法或创新点
  
  # 字符约束
  char_constraints:
    allow_chinese: true
    allow_english: true
    allow_numbers: true
    allow_special: false  # 不允许特殊字符
    max_english_ratio: 0.3  # 英文字符占比 ≤30%
```

### 3.3 时间线约束

```python
def validate_timeline(timeline: dict, degree: str) -> List[HardRuleViolation]:
    """验证时间线"""
    violations = []
    
    start_date = timeline.get("start")
    end_date = timeline.get("end")
    
    # 规则 1: 必需日期
    if not start_date or not end_date:
        violations.append(HardRuleViolation(
            rule_id="TIMELINE_MISSING",
            rule_name="时间线缺失",
            severity="ERROR",
            message="时间线必须包含开始和结束日期",
            actual_value=timeline,
            expected_value="{'start': '...', 'end': '...'}"
        ))
        return violations
    
    # 规则 2: 时间跨度
    from datetime import datetime
    start = datetime.strptime(start_date, "%Y-%m")
    end = datetime.strptime(end_date, "%Y-%m")
    duration_months = (end.year - start.year) * 12 + (end.month - start.month)
    
    if degree == "硕士":
        min_months, max_months = 6, 36
    elif degree == "博士":
        min_months, max_months = 12, 60
    else:
        min_months, max_months = 6, 36
    
    if duration_months < min_months:
        violations.append(HardRuleViolation(
            rule_id="TIMELINE_TOO_SHORT",
            rule_name="时间线过短",
            severity="WARNING",
            message=f"时间跨度 {duration_months} 个月少于 {degree}最低要求 {min_months} 个月",
            actual_value=duration_months,
            expected_value=min_months
        ))
    
    if duration_months > max_months:
        violations.append(HardRuleViolation(
            rule_id="TIMELINE_TOO_LONG",
            rule_name="时间线过长",
            severity="WARNING",
            message=f"时间跨度 {duration_months} 个月超过 {degree}最高要求 {max_months} 个月",
            actual_value=duration_months,
            expected_value=max_months
        ))
    
    # 规则 3: 开始日期不能晚于结束日期
    if start >= end:
        violations.append(HardRuleViolation(
            rule_id="TIMELINE_INVALID_ORDER",
            rule_name="时间线顺序错误",
            severity="ERROR",
            message="开始日期不能晚于或等于结束日期",
            actual_value=f"{start_date} -> {end_date}",
            expected_value="start < end"
        ))
    
    return violations
```

### 3.4 文献基线约束

```yaml
# config/constraints/hard_rules.yaml
literature:
  # 文献数量基线
  count_baseline:
    master: 30          # 硕士 ≥30 篇
    doctor: 80          # 博士 ≥80 篇
    default: 30
  
  # 近 5 年文献占比
  recent_ratio:
    min: 0.5            # 近 5 年文献 ≥50%
    target: 0.7         # 目标 70%
  
  # 中英文比例
  language_ratio:
    chinese_min: 0.3    # 中文文献 ≥30%
    english_min: 0.4    # 英文文献 ≥40%
  
  # 高质量文献
  quality:
    require_q1_q2: true  # 要求 Q1/Q2 期刊
    require_top_conf: true  # 要求顶会
    min_high_quality: 0.3  # 高质量文献 ≥30%
  
  # 引用格式
  citation_format: "GB/T 7714"
```

```python
def validate_literature(literature: list, degree: str) -> List[HardRuleViolation]:
    """验证文献基线"""
    violations = []
    
    # 规则 1: 文献数量
    if degree == "硕士":
        min_count = 30
    elif degree == "博士":
        min_count = 80
    else:
        min_count = 30
    
    if len(literature) < min_count:
        violations.append(HardRuleViolation(
            rule_id="LITERATURE_COUNT",
            rule_name="文献数量不足",
            severity="WARNING",
            message=f"文献数量 {len(literature)} 少于 {degree}最低要求 {min_count} 篇",
            actual_value=len(literature),
            expected_value=min_count
        ))
    
    # 规则 2: 近 5 年文献占比
    from datetime import datetime
    current_year = datetime.now().year
    recent_count = sum(1 for p in literature if p.get("year", 0) >= current_year - 5)
    recent_ratio = recent_count / len(literature) if literature else 0
    
    if recent_ratio < 0.5:
        violations.append(HardRuleViolation(
            rule_id="LITERATURE_RECENT_RATIO",
            rule_name="近 5 年文献占比不足",
            severity="WARNING",
            message=f"近 5 年文献占比 {recent_ratio:.1%} 低于 50%",
            actual_value=f"{recent_ratio:.1%}",
            expected_value="≥50%"
        ))
    
    return violations
```

### 3.5 查重阈值约束

```yaml
# config/constraints/hard_rules.yaml
duplication:
  # 查重阈值
  thresholds:
    overall_max: 0.30        # 总重复率 ≤30%
    single_source_max: 0.10  # 单源重复率 ≤10%
    self_duplication: 0.20   # 自我重复 ≤20%
  
  # 算法
  algorithm: levenshtein     # Levenshtein 距离
  
  # 检查范围
  scope:
    - title
    - abstract
    - outline
    - full_text
```

```python
def validate_duplication(content: str, references: list) -> List[HardRuleViolation]:
    """验证查重"""
    violations = []
    
    # 计算与每篇参考文献的相似度
    max_similarity = 0
    max_sim_source = ""
    
    for ref in references:
        similarity = _calculate_similarity(content, ref.get("content", ""))
        if similarity > max_similarity:
            max_similarity = similarity
            max_sim_source = ref.get("title", "")
    
    # 规则 1: 单源重复率
    if max_similarity > 0.10:
        violations.append(HardRuleViolation(
            rule_id="DUPLICATION_SINGLE_SOURCE",
            rule_name="单源重复率过高",
            severity="ERROR",
            message=f'与"{max_sim_source}"的重复率 {max_similarity:.1%} 超过 10%',
            actual_value=f"{max_similarity:.1%}",
            expected_value="≤10%"
        ))
    
    return violations

def _calculate_similarity(s1: str, s2: str) -> float:
    """基于 Levenshtein 距离计算相似度"""
    if not s1 or not s2:
        return 0.0
    
    distance = _levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    return 1.0 - (distance / max_len)
```

### 3.6 学科匹配约束

```python
def validate_discipline_match(topic: dict, discipline: str) -> List[HardRuleViolation]:
    """验证学科匹配"""
    violations = []
    
    # 学科关键词映射
    discipline_keywords = {
        "计算机科学": ["算法", "模型", "系统", "网络", "数据", "人工智能", "机器学习", "深度学习"],
        "教育学": ["教学", "学习", "课程", "教育", "学生", "教师", "课堂"],
        "管理学": ["管理", "组织", "企业", "战略", "运营", "决策"],
        "心理学": ["心理", "行为", "认知", "情绪", "人格"]
    }
    
    keywords = discipline_keywords.get(discipline, [])
    topic_text = topic.get("title", "") + topic.get("abstract", "")
    
    # 规则 1: 学科关键词匹配
    matched = sum(1 for kw in keywords if kw in topic_text)
    match_ratio = matched / len(keywords) if keywords else 0
    
    if match_ratio < 0.2:
        violations.append(HardRuleViolation(
            rule_id="DISCIPLINE_MISMATCH",
            rule_name="学科不匹配",
            severity="WARNING",
            message=f"选题与{discipline}学科关键词匹配率 {match_ratio:.1%} 过低",
            actual_value=f"{match_ratio:.1%}",
            expected_value="≥20%"
        ))
    
    return violations
```

### 3.7 导师对齐约束

```python
def validate_advisor_alignment(topic: dict, advisor_info: dict) -> List[HardRuleViolation]:
    """验证导师对齐"""
    violations = []
    
    advisor_directions = advisor_info.get("directions", [])
    topic_direction = topic.get("direction", "")
    
    # 规则 1: 研究方向对齐
    aligned = any(
        any(kw in topic_direction for kw in direction.split())
        for direction in advisor_directions
    )
    
    if not aligned:
        violations.append(HardRuleViolation(
            rule_id="ADVISOR_MISALIGNMENT",
            rule_name="导师方向不对齐",
            severity="WARNING",
            message=f"选题方向 '{topic_direction}' 与导师研究方向不匹配",
            actual_value=topic_direction,
            expected_value=f"匹配 {advisor_directions}"
        ))
    
    return violations
```

---

## 4. 新颖性评分系统

### 4.1 四维评分模型

ThesisMiner v8.0 采用四维新颖性评分模型：

```
┌─────────────────────────────────────────────────────────────────┐
│                    新颖性评分模型                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  总分 = Σ(维度分数 × 权重)                                      │
│                                                                 │
│  ┌─────────────────────┬────────┬──────────────────────────┐   │
│  │ 维度                │ 权重   │ 说明                     │   │
│  ├─────────────────────┼────────┼──────────────────────────┤   │
│  │ cross_discipline    │ 0.30   │ 跨学科融合               │   │
│  │ method_transfer     │ 0.25   │ 方法迁移                 │   │
│  │ pain_point_breakthru│ 0.25   │ 痛点突破                 │   │
│  │ trend_forecast      │ 0.20   │ 趋势预测                 │   │
│  └─────────────────────┴────────┴──────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 评分配置

```yaml
# config/constraints/novelty_weights.yaml
novelty:
  # 四维权重
  weights:
    cross_discipline: 0.30
    method_transfer: 0.25
    pain_point_breakthrough: 0.25
    trend_forecast: 0.20
  
  # 评分阈值
  thresholds:
    excellent: 85      # 优秀 ≥85
    good: 70           # 良好 ≥70
    pass: 60           # 通过 ≥60
    fail: 0            # 失败 <60
  
  # 风险等级
  risk_levels:
    low:
      max_score: 100
      min_score: 85
      label: "低风险"
      description: "新颖性高，与已有文献差异大"
    medium:
      max_score: 84
      min_score: 60
      label: "中风险"
      description: "新颖性中等，存在一定相似性"
    high:
      max_score: 59
      min_score: 0
      label: "高风险"
      description: "新颖性低，与已有文献高度相似"
  
  # 评分公式
  formula: "total = Σ(dimension_score × weight)"
  
  # 各维度评分标准
  dimension_rubrics:
    cross_discipline:
      excellent:
        score: 85-100
        criteria: "跨学科融合创新性强，融合点独特"
      good:
        score: 70-84
        criteria: "跨学科融合有一定创新性"
      pass:
        score: 60-69
        criteria: "跨学科融合创新性一般"
      fail:
        score: 0-59
        criteria: "跨学科融合创新性不足"
    
    method_transfer:
      excellent:
        score: 85-100
        criteria: "方法迁移巧妙，迁移后效果显著"
      good:
        score: 70-84
        criteria: "方法迁移合理，有一定效果"
      pass:
        score: 60-69
        criteria: "方法迁移可行，效果一般"
      fail:
        score: 0-59
        criteria: "方法迁移牵强，效果不明"
    
    pain_point_breakthrough:
      excellent:
        score: 85-100
        criteria: "痛点分析深入，突破方案创新"
      good:
        score: 70-84
        criteria: "痛点分析到位，方案合理"
      pass:
        score: 60-69
        criteria: "痛点分析一般，方案可行"
      fail:
        score: 0-59
        criteria: "痛点分析不足，方案缺乏创新"
    
    trend_forecast:
      excellent:
        score: 85-100
        criteria: "趋势预测前瞻性强，方向明确"
      good:
        score: 70-84
        criteria: "趋势预测合理，方向清晰"
      pass:
        score: 60-69
        criteria: "趋势预测一般，方向模糊"
      fail:
        score: 0-59
        criteria: "趋势预测不足，方向不明"
```

### 4.3 评分实现

```python
# backend/constraints/novelty_scorer.py
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class NoveltyScore:
    """新颖性评分结果"""
    total_score: float
    dimension_scores: Dict[str, float]
    risk_level: str
    risk_label: str
    description: str

class NoveltyScorer:
    """新颖性评分器"""
    
    WEIGHTS = {
        "cross_discipline": 0.30,
        "method_transfer": 0.25,
        "pain_point_breakthrough": 0.25,
        "trend_forecast": 0.20
    }
    
    THRESHOLDS = {
        "excellent": 85,
        "good": 70,
        "pass": 60,
        "fail": 0
    }
    
    def calculate(self, dimension_scores: Dict[str, float]) -> NoveltyScore:
        """计算新颖性总分"""
        # 1. 计算加权总分
        total = sum(
            dimension_scores.get(dim, 0) * weight
            for dim, weight in self.WEIGHTS.items()
        )
        
        # 2. 确定风险等级
        risk_level, risk_label, description = self._get_risk_level(total)
        
        return NoveltyScore(
            total_score=total,
            dimension_scores=dimension_scores,
            risk_level=risk_level,
            risk_label=risk_label,
            description=description
        )
    
    def _get_risk_level(self, score: float) -> tuple:
        """获取风险等级"""
        if score >= 85:
            return ("low", "低风险", "新颖性高，与已有文献差异大")
        elif score >= 60:
            return ("medium", "中风险", "新颖性中等，存在一定相似性")
        else:
            return ("high", "高风险", "新颖性低，与已有文献高度相似")
```

### 4.4 评分示例

```python
# 示例 1: 高新颖性选题
dimension_scores = {
    "cross_discipline": 90,        # 跨学科融合优秀
    "method_transfer": 85,         # 方法迁移良好
    "pain_point_breakthrough": 88, # 痛点突破优秀
    "trend_forecast": 82           # 趋势预测良好
}

scorer = NoveltyScorer()
result = scorer.calculate(dimension_scores)

# 计算过程:
# total = 90×0.30 + 85×0.25 + 88×0.25 + 82×0.20
#       = 27 + 21.25 + 22 + 16.4
#       = 86.65

print(f"总分: {result.total_score}")        # 86.65
print(f"风险: {result.risk_label}")         # 低风险
print(f"描述: {result.description}")        # 新颖性高，与已有文献差异大


# 示例 2: 低新颖性选题
dimension_scores = {
    "cross_discipline": 50,
    "method_transfer": 55,
    "pain_point_breakthrough": 45,
    "trend_forecast": 60
}

result = scorer.calculate(dimension_scores)

# total = 50×0.30 + 55×0.25 + 45×0.25 + 60×0.20
#       = 15 + 13.75 + 11.25 + 12
#       = 52.0

print(f"总分: {result.total_score}")        # 52.0
print(f"风险: {result.risk_label}")         # 高风险
```

---

## 5. AI 痕迹去除规则

### 5.1 AI 痕迹概述

AI 生成的文本常带有一些特征性词汇和句式，ThesisMiner v8.0 通过规则去除这些痕迹：

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI 痕迹去除流程                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. 词汇级去除                                                   │
│     - 空泛连接词（总之、综上所述）                                │
│     - AI 常用词（值得注意的是、需要指出的是）                     │
│     - 过度修饰词（显著、重要、极大）                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. 句式级调整                                                   │
│     - 被动转主动                                                 │
│     - 长句拆短                                                   │
│     - 第一人称去除                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. 段落级优化                                                   │
│     - 段落过渡自然化                                              │
│     - 逻辑衔接词多样化                                            │
│     - 段落长度均衡                                                │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 词汇级规则

```yaml
# config/constraints/style_normalizer_rules.yaml
ai_trace_removal:
  # 词汇级规则
  vocabulary:
    # 空泛连接词（直接删除）
    remove_phrases:
      - "总之"
      - "综上所述"
      - "总的来说"
      - "由此可见"
      - "值得注意的是"
      - "需要指出的是"
      - "不难看出"
      - "显而易见"
      - "众所周知"
      - "毫无疑问"
    
    # 过度修饰词（替换为更精确的表达）
    replace_words:
      - pattern: "显著的"
        replacement: ""  # 直接删除
      - pattern: "重要的"
        replacement: ""
      - pattern: "极大的"
        replacement: ""
      - pattern: "充分地"
        replacement: ""
      - pattern: "有效地"
        replacement: ""
      - pattern: "成功地"
        replacement: ""
    
    # AI 常用句式（替换）
    replace_patterns:
      - pattern: "本文提出了一种.*?方法"
        replacement: "提出的方法"
      - pattern: "本研究通过.*?实现了"
        replacement: "通过.*?实现"
      - pattern: "实验结果表明"
        replacement: "结果显示"
      - pattern: "本文的主要贡献"
        replacement: "贡献"
```

### 5.3 句式级规则

```python
# backend/constraints/ai_trace_remover.py
import re
from typing import List

class AITraceRemover:
    """AI 痕迹去除器"""
    
    def __init__(self):
        self.remove_phrases = self._load_remove_phrases()
        self.replace_patterns = self._load_replace_patterns()
    
    def remove_traces(self, content: str) -> str:
        """去除 AI 痕迹"""
        # 1. 词汇级去除
        content = self._remove_vocabulary(content)
        
        # 2. 句式级调整
        content = self._adjust_sentences(content)
        
        # 3. 段落级优化
        content = self._optimize_paragraphs(content)
        
        return content
    
    def _remove_vocabulary(self, content: str) -> str:
        """词汇级去除"""
        # 删除空泛连接词
        for phrase in self.remove_phrases:
            # 匹配短语 + 可选的逗号
            pattern = rf"{phrase}[，,。]?"
            content = re.sub(pattern, "", content)
        
        # 替换过度修饰词
        for pattern, replacement in self.replace_patterns:
            content = re.sub(pattern, replacement, content)
        
        return content
    
    def _adjust_sentences(self, content: str) -> str:
        """句式级调整"""
        # 1. 去除第一人称
        content = re.sub(r"本文", "", content)
        content = re.sub(r"本研究", "研究", content)
        content = re.sub(r"我们认为", "研究认为", content)
        
        # 2. 被动转主动（简单规则）
        content = re.sub(r"被.*?所", "由", content)
        
        # 3. 长句拆短（超过 100 字的句子）
        sentences = content.split("。")
        result = []
        for sent in sentences:
            if len(sent) > 100:
                # 在合适的位置拆分
                parts = self._split_long_sentence(sent)
                result.extend(parts)
            else:
                result.append(sent)
        
        return "。".join(result)
    
    def _split_long_sentence(self, sentence: str) -> List[str]:
        """拆分长句"""
        # 在分号、逗号处拆分
        if "；" in sentence:
            parts = sentence.split("；")
            return [p + "；" for p in parts[:-1]] + [parts[-1]]
        elif "，" in sentence:
            parts = sentence.split("，")
            mid = len(parts) // 2
            return ["，".join(parts[:mid]) + "，", "，".join(parts[mid:])]
        return [sentence]
```

### 5.4 段落级规则

```python
def _optimize_paragraphs(self, content: str) -> str:
    """段落级优化"""
    paragraphs = content.split("\n\n")
    optimized = []
    
    for i, para in enumerate(paragraphs):
        # 1. 段落过渡自然化
        if i > 0:
            para = self._naturalize_transition(para, i)
        
        # 2. 段落长度均衡
        if len(para) > 500:
            # 拆分过长段落
            para = self._split_paragraph(para)
        
        optimized.append(para)
    
    return "\n\n".join(optimized)

def _naturalize_transition(self, para: str, index: int) -> str:
    """段落过渡自然化"""
    # AI 常用过渡词
    ai_transitions = ["首先", "其次", "再次", "最后", "此外", "另外"]
    
    # 自然过渡词
    natural_transitions = [
        "在.*?方面", "从.*?角度", "就.*?而言",
        "进一步地", "在此基础上", "与此同时"
    ]
    
    first_word = para.split()[0] if para.split() else ""
    
    if first_word in ai_transitions:
        # 替换为更自然的过渡
        natural = natural_transitions[index % len(natural_transitions)]
        para = natural + para[len(first_word):]
    
    return para
```

---

## 6. 多粒度生成规则

### 6.1 四种粒度

ThesisMiner v8.0 支持四种生成粒度：

| 粒度 | 英文 | 字数/长度 | 用途 |
|------|------|-----------|------|
| 标题 | title | ≤25/30 字 | 快速预览 |
| 摘要 | abstract | 300-500 字 | 概要了解 |
| 大纲 | outline | 5-8 章 | 结构规划 |
| 完整 | full | 8000-15000 字 | 完整报告 |

### 6.2 标题生成规则

```yaml
# config/constraints/hard_rules.yaml
generation:
  title:
    # 数量
    count: 3-5  # 生成 3-5 个候选
    
    # 长度
    master_max_length: 25
    doctor_max_length: 30
    
    # 结构要求
    structure:
      must_include:
        - 研究对象
        - 研究方法或创新点
      should_avoid:
        - 空泛词（"研究"、"应用"单独出现）
        - "基于"开头
    
    # 示例
    good_examples:
      - "面向多模态文档的检索增强生成方法"
      - "基于知识图谱的大语言模型幻觉检测"
      - "对比学习在中文文本表示中的应用"
    
    bad_examples:
      - "基于深度学习的研究"  # 太空泛
      - "大语言模型应用"       # 缺少方法
      - "关于人工智能的探讨"   # 禁用前缀
```

### 6.3 摘要生成规则

```yaml
  abstract:
    # 字数
    min_words: 300
    max_words: 500
    
    # 结构（五要素）
    structure:
      - background      # 背景
      - problem         # 问题
      - method          # 方法
      - result          # 结果
      - contribution    # 贡献
    
    # 禁用
    forbidden:
      - 第一人称（"本文"、"本研究"）
      - 空泛修饰（"显著"、"重要"）
      - AI 痕迹词
    
    # 示例
    good_example: |
      随着大语言模型的广泛应用，幻觉问题日益突出。现有方法主要依赖
      外部知识库校验，存在延迟高、覆盖率低的问题。提出一种基于知识
      图谱的实时幻觉检测方法，通过实体关系匹配实现事实校验。在三个
      公开数据集上的实验显示，该方法将幻觉检测准确率提升至 92%，
      同时将延迟降低 40%。该方法为构建可信大语言模型提供了新的
      技术路径。
```

### 6.4 大纲生成规则

```yaml
  outline:
    # 章节数
    master_chapters: 5-6
    doctor_chapters: 6-8
    
    # 每章节
    sections_per_chapter: 3-5
    
    # 结构要求
    required_chapters:
      - 引言
      - 相关工作
      - 方法
      - 实验
      - 结论
    
    # 示例
    example:
      chapters:
        - title: "第一章 引言"
          sections:
            - "1.1 研究背景"
            - "1.2 研究问题"
            - "1.3 研究意义"
            - "1.4 论文结构"
        
        - title: "第二章 相关工作"
          sections:
            - "2.1 大语言模型"
            - "2.2 幻觉问题"
            - "2.3 知识图谱"
            - "2.4 现有方法分析"
```

### 6.5 完整报告生成规则

```yaml
  full:
    # 字数
    min_words: 8000
    max_words: 15000
    
    # 结构
    sections:
      - 引言（1000-2000 字）
      - 相关工作（1500-2500 字）
      - 研究内容（2000-3000 字）
      - 方法（2000-3000 字）
      - 实验计划（1000-2000 字）
      - 时间安排（500-1000 字）
      - 参考文献（不计入字数）
    
    # 格式
    format:
      citation: "GB/T 7714"
      heading_style: "学术风格"
      avoid: "口语化表达"
```

---

## 7. 五阶段门控

### 7.1 门控机制

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  info_confirm │────▶│  creativity  │────▶│  validation  │
│  门控: 信息完整│     │  门控: ≥3候选│     │  门控: ≥60分 │
└──────────────┘     └──────────────┘     └──────────────┘
                                                  │
                                                  ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ deep_assist  │◀────│  generation  │◀────│  通过验证    │
│  门控: 用户结束│     │  门控: 报告成功│     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

### 7.2 门控配置

```python
# backend/constraints/stage_gate.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List

class Stage(str, Enum):
    INFO_CONFIRM = "info_confirm"
    CREATIVITY = "creativity"
    VALIDATION = "validation"
    GENERATION = "generation"
    DEEP_ASSIST = "deep_assist"

@dataclass
class GateResult:
    """门控检查结果"""
    passed: bool
    stage: str
    score: Optional[float] = None
    reason: str = ""
    retry_allowed: bool = True
    missing_fields: List[str] = None

@dataclass
class StageGate:
    """阶段门控"""
    stage: str
    required_fields: List[str]
    min_score: float = 0.0
    max_retries: int = 3
    fallback_strategy: str = "skip"
    
    def check(self, result: dict) -> GateResult:
        """检查门控条件"""
        # 1. 检查必需字段
        missing = []
        for field in self.required_fields:
            if field not in result:
                missing.append(field)
        
        if missing:
            return GateResult(
                passed=False,
                stage=self.stage,
                reason=f"缺少必需字段: {missing}",
                missing_fields=missing
            )
        
        # 2. 检查分数阈值
        score = result.get("score", 0)
        if score < self.min_score:
            return GateResult(
                passed=False,
                stage=self.stage,
                score=score,
                reason=f"分数 {score} 低于阈值 {self.min_score}"
            )
        
        return GateResult(
            passed=True,
            stage=self.stage,
            score=score
        )

# 阶段门控配置
STAGE_GATES = {
    Stage.INFO_CONFIRM: StageGate(
        stage="info_confirm",
        required_fields=["discipline", "degree", "direction"],
        max_retries=5,
        fallback_strategy="ask_user"
    ),
    Stage.CREATIVITY: StageGate(
        stage="creativity",
        required_fields=["candidates"],
        max_retries=3,
        fallback_strategy="fallback_proposal"
    ),
    Stage.VALIDATION: StageGate(
        stage="validation",
        required_fields=["evaluations"],
        min_score=60.0,  # 关键阈值
        max_retries=2,
        fallback_strategy="mark_warning"
    ),
    Stage.GENERATION: StageGate(
        stage="generation",
        required_fields=["report"],
        max_retries=3,
        fallback_strategy="template_mode"
    ),
    Stage.DEEP_ASSIST: StageGate(
        stage="deep_assist",
        required_fields=[],
        max_retries=0,  # 无限循环
        fallback_strategy="loop"
    )
}
```

### 7.3 门控检查示例

```python
# 示例 1: info_confirm 门控
result = {
    "discipline": "计算机科学",
    "degree": "硕士",
    "direction": "大语言模型"
}

gate = STAGE_GATES[Stage.INFO_CONFIRM]
gate_result = gate.check(result)
# gate_result.passed = True


# 示例 2: info_confirm 门控失败
result = {
    "discipline": "计算机科学",
    # 缺少 degree 和 direction
}

gate_result = gate.check(result)
# gate_result.passed = False
# gate_result.missing_fields = ["degree", "direction"]


# 示例 3: validation 门控
result = {
    "evaluations": [...],
    "score": 75
}

gate = STAGE_GATES[Stage.VALIDATION]
gate_result = gate.check(result)
# gate_result.passed = True (75 >= 60)


# 示例 4: validation 门控失败
result = {
    "evaluations": [...],
    "score": 45
}

gate_result = gate.check(result)
# gate_result.passed = False (45 < 60)
# gate_result.reason = "分数 45 低于阈值 60.0"
```

---

## 8. 规则引擎

### 8.1 规则引擎架构

```python
# backend/constraints/rule_engine.py
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Callable, Dict, Any

class Severity(str, Enum):
    """严重级别"""
    ERROR = "ERROR"        # 错误（必须满足）
    WARNING = "WARNING"    # 警告（建议满足）
    INFO = "INFO"          # 信息（提示）

class RuleType(str, Enum):
    """规则类型"""
    HARD = "hard"          # 硬约束
    SOFT = "soft"          # 软约束
    SCORE = "score"        # 评分约束
    GATE = "gate"          # 门控约束

@dataclass
class Rule:
    """规则定义"""
    rule_id: str
    rule_name: str
    rule_type: RuleType
    severity: Severity
    description: str
    check_fn: Callable[[dict], List['RuleViolation']]
    enabled: bool = True

@dataclass
class RuleViolation:
    """规则违反"""
    rule_id: str
    rule_name: str
    severity: Severity
    message: str
    actual_value: Any
    expected_value: Any

class RuleChain:
    """规则链：按顺序执行规则"""
    
    def __init__(self):
        self.rules: List[Rule] = []
    
    def add_rule(self, rule: Rule) -> None:
        """添加规则"""
        self.rules.append(rule)
    
    def execute(self, input_data: dict) -> List[RuleViolation]:
        """执行规则链"""
        violations = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            rule_violations = rule.check_fn(input_data)
            violations.extend(rule_violations)
        
        return violations

class ConflictResolver:
    """冲突解决器"""
    
    def resolve(self, violations: List[RuleViolation]) -> List[RuleViolation]:
        """解决规则冲突"""
        # 1. 按严重级别排序（ERROR > WARNING > INFO）
        severity_order = {
            Severity.ERROR: 0,
            Severity.WARNING: 1,
            Severity.INFO: 2
        }
        
        violations.sort(key=lambda v: severity_order[v.severity])
        
        # 2. 去重（相同 rule_id 只保留一个）
        seen = set()
        unique = []
        for v in violations:
            if v.rule_id not in seen:
                seen.add(v.rule_id)
                unique.append(v)
        
        return unique

class RuleEngine:
    """规则引擎"""
    
    def __init__(self):
        self.rule_chain = RuleChain()
        self.conflict_resolver = ConflictResolver()
        self._load_predefined_rules()
    
    def _load_predefined_rules(self) -> None:
        """加载预定义规则"""
        for rule in PREDEFINED_RULES:
            self.rule_chain.add_rule(rule)
    
    def validate(self, input_data: dict) -> Dict:
        """验证输入"""
        violations = self.rule_chain.execute(input_data)
        violations = self.conflict_resolver.resolve(violations)
        
        # 分类
        errors = [v for v in violations if v.severity == Severity.ERROR]
        warnings = [v for v in violations if v.severity == Severity.WARNING]
        infos = [v for v in violations if v.severity == Severity.INFO]
        
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "total_violations": len(violations)
        }
```

### 8.2 预定义规则

```python
# PREDEFINED_RULES: 50+ 预定义规则
PREDEFINED_RULES = [
    # === 标题规则 ===
    Rule(
        rule_id="TITLE_LENGTH",
        rule_name="标题长度",
        rule_type=RuleType.HARD,
        severity=Severity.ERROR,
        description="硕士标题≤25字，博士标题≤30字",
        check_fn=lambda data: validate_title_length(data.get("title", ""), data.get("degree", ""))
    ),
    Rule(
        rule_id="TITLE_FORBIDDEN_PREFIX",
        rule_name="标题禁用前缀",
        rule_type=RuleType.HARD,
        severity=Severity.ERROR,
        description='标题不应以"基于"开头',
        check_fn=lambda data: validate_title_prefix(data.get("title", ""))
    ),
    Rule(
        rule_id="TITLE_EMPTY",
        rule_name="标题非空",
        rule_type=RuleType.HARD,
        severity=Severity.ERROR,
        description="标题不能为空",
        check_fn=lambda data: validate_title_empty(data.get("title", ""))
    ),
    
    # === 时间线规则 ===
    Rule(
        rule_id="TIMELINE_MISSING",
        rule_name="时间线缺失",
        rule_type=RuleType.HARD,
        severity=Severity.ERROR,
        description="时间线必须包含开始和结束日期",
        check_fn=lambda data: validate_timeline_missing(data.get("timeline", {}))
    ),
    Rule(
        rule_id="TIMELINE_ORDER",
        rule_name="时间线顺序",
        rule_type=RuleType.HARD,
        severity=Severity.ERROR,
        description="开始日期必须早于结束日期",
        check_fn=lambda data: validate_timeline_order(data.get("timeline", {}))
    ),
    
    # === 文献规则 ===
    Rule(
        rule_id="LITERATURE_COUNT",
        rule_name="文献数量",
        rule_type=RuleType.SOFT,
        severity=Severity.WARNING,
        description="硕士≥30篇，博士≥80篇",
        check_fn=lambda data: validate_literature_count(data.get("literature", []), data.get("degree", ""))
    ),
    Rule(
        rule_id="LITERATURE_RECENT_RATIO",
        rule_name="近5年文献占比",
        rule_type=RuleType.SOFT,
        severity=Severity.WARNING,
        description="近5年文献≥50%",
        check_fn=lambda data: validate_literature_recent(data.get("literature", []))
    ),
    
    # === 查重规则 ===
    Rule(
        rule_id="DUPLICATION_SINGLE_SOURCE",
        rule_name="单源查重",
        rule_type=RuleType.HARD,
        severity=Severity.ERROR,
        description="单源重复率≤10%",
        check_fn=lambda data: validate_duplication_single(data.get("content", ""), data.get("references", []))
    ),
    
    # ... 更多规则（共 50+ 条）
]
```

### 8.3 规则使用示例

```python
from backend.constraints.rule_engine import RuleEngine

# 创建规则引擎
engine = RuleEngine()

# 验证选题
input_data = {
    "title": "基于深度学习的图像识别研究",
    "degree": "硕士",
    "timeline": {"start": "2026-09", "end": "2027-06"},
    "literature": [{"title": "Paper 1", "year": 2025}],
    "content": "..."
}

result = engine.validate(input_data)

print(f"通过: {result['passed']}")
print(f"错误数: {len(result['errors'])}")
print(f"警告数: {len(result['warnings'])}")

for error in result["errors"]:
    print(f"[ERROR] {error.rule_name}: {error.message}")

for warning in result["warnings"]:
    print(f"[WARNING] {warning.rule_name}: {warning.message}")
```

---

## 9. 样式规范化规则

### 9.1 样式规范化流程

```
[原始内容]
     │
     ▼
[1. 术语统一]
     │
     ▼
[2. 引用格式统一]
     │
     ▼
[3. 标点符号规范化]
     │
     ▼
[4. 数字格式统一]
     │
     ▼
[5. 段落格式调整]
     │
     ▼
[规范化内容]
```

### 9.2 术语统一规则

```yaml
# config/constraints/style_normalizer_rules.yaml
terminology:
  # 术语映射表
  mapping:
    # 中文术语统一
    "大语言模型": ["大语言模型", "大型语言模型", "LLM", "Large Language Model"]
    "人工智能": ["人工智能", "AI", "Artificial Intelligence"]
    "机器学习": ["机器学习", "ML", "Machine Learning"]
    "深度学习": ["深度学习", "DL", "Deep Learning"]
    "自然语言处理": ["自然语言处理", "NLP", "Natural Language Processing"]
    
    # 英文术语统一
    "Transformer": ["Transformer", "transformer", "TRANSFORMER"]
    "BERT": ["BERT", "bert", "Bert"]
    "GPT": ["GPT", "gpt", "Gpt"]
  
  # 统一为第一个
  prefer_first: true
```

### 9.3 引用格式规则

```python
# backend/constraints/style_normalizer.py
import re

class StyleNormalizer:
    """样式规范化器"""
    
    def normalize(self, content: str) -> str:
        """规范化样式"""
        content = self._normalize_terminology(content)
        content = self._normalize_citations(content)
        content = self._normalize_punctuation(content)
        content = self._normalize_numbers(content)
        return content
    
    def _normalize_terminology(self, content: str) -> str:
        """术语统一"""
        mapping = {
            "大型语言模型": "大语言模型",
            "LLM": "大语言模型",
            "AI": "人工智能",
            "ML": "机器学习",
            "DL": "深度学习",
            "NLP": "自然语言处理"
        }
        
        for variant, standard in mapping.items():
            content = content.replace(variant, standard)
        
        return content
    
    def _normalize_citations(self, content: str) -> str:
        """引用格式统一（GB/T 7714）"""
        # [1] → [1]
        # (Author, 2020) → [Author, 2020]
        
        # 统一为 [数字] 格式
        content = re.sub(r"【(\d+)】", r"[\1]", content)
        content = re.sub(r"\((\d+)\)", r"[\1]", content)
        
        return content
    
    def _normalize_punctuation(self, content: str) -> str:
        """标点符号规范化"""
        # 英文标点转中文（在中文上下文中）
        content = content.replace(",", "，")
        content = content.replace(".", "。")
        content = content.replace(":", "：")
        content = content.replace(";", "；")
        content = content.replace("?", "？")
        content = content.replace("!", "！")
        
        # 去除多余空格
        content = re.sub(r"\s+", " ", content)
        
        return content
    
    def _normalize_numbers(self, content: str) -> str:
        """数字格式统一"""
        # 阿拉伯数字统一（年份保持不变）
        # 中文数字转阿拉伯数字（小数字）
        chinese_to_arabic = {
            "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
            "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"
        }
        
        for cn, ar in chinese_to_arabic.items():
            content = re.sub(rf"(?<!\d){cn}(?!\d)", ar, content)
        
        return content
```

---

## 10. Prompt 模板

### 10.1 Prompt 模板架构

```
docs/constraints/prompt_templates/
├── orchestrator_system.md    # Orchestrator 系统提示词
├── searcher_system.md        # Searcher 系统提示词
├── reasoner_system.md        # Reasoner 系统提示词
├── critic_system.md          # Critic 系统提示词
├── mentor_system.md          # Mentor 系统提示词
└── writer_system.md          # Writer 系统提示词
```

### 10.2 Orchestrator 系统提示词

```markdown
# docs/constraints/prompt_templates/orchestrator_system.md

你是 ThesisMiner 的 Orchestrator 主管理 Agent，负责调度五阶段闭环流程。

## 你的职责

1. **信息确认阶段**：解析用户输入，提取学科、学位、研究方向等关键信息
2. **创意生成阶段**：调度 Reasoner 生成 ≥3 个候选选题
3. **验证评估阶段**：调度 Critic 评估候选，分数 ≥60 才通过
4. **报告生成阶段**：调度 Writer 生成多粒度报告
5. **深度辅助阶段**：与用户交互，提供深度修改建议

## 调度原则

- 严格按阶段顺序执行，不跳过门控
- 失败时优先重试，超过 max_attempts 后兜底降级
- 上下文超过阈值时自动压缩
- 每个阶段结果缓存到 stage_results，避免重复计算

## 输出格式

每个阶段完成后，输出 JSON：
```json
{
  "stage": "creativity",
  "status": "complete",
  "result": {...},
  "next_stage": "validation"
}
```
```

### 10.3 Searcher 系统提示词

```markdown
# docs/constraints/prompt_templates/searcher_system.md

你是 ThesisMiner 的 Searcher 文献检索 Agent。

## 你的职责

1. 调用 arXiv 和 Semantic Scholar API 检索文献
2. 计算查询与已有论文的新颖性
3. 返回结构化的检索结果

## 检索原则

- 并行调用多个数据源（asyncio.gather）
- 单个数据源失败不影响整体
- 去重后按相关性排序
- 新颖性分数 = 1 - 相似度（Levenshtein）

## 输出格式

```json
{
  "papers": [
    {
      "title": "...",
      "authors": ["..."],
      "year": 2025,
      "abstract": "...",
      "url": "...",
      "citation_count": 100
    }
  ],
  "novelty_scores": [
    {
      "paper_title": "...",
      "similarity": 0.3,
      "novelty_score": 0.7,
      "risk_level": "low"
    }
  ]
}
```
```

### 10.4 Reasoner 系统提示词

```markdown
# docs/constraints/prompt_templates/reasoner_system.md

你是 ThesisMiner 的 Reasoner 四维创意引擎 Agent。

## 四维创意维度

1. **跨学科融合（cross_discipline）**：将其他学科的方法/理论引入本学科
2. **方法迁移（method_transfer）**：将某领域的方法迁移到另一领域
3. **痛点突破（pain_point_breakthrough）**：针对现有问题提出突破方案
4. **趋势预测（trend_forecast）**：基于技术演进预测未来方向

## 生成要求

- 每个维度至少生成 1 个候选
- 总候选数 3-5 个
- 每个候选包含：标题、维度、创新点、简述
- 标题符合硬约束（长度、禁用词）

## 输出格式

```json
[
  {
    "title": "面向多模态文档的检索增强生成方法",
    "dimension": "pain_point_breakthrough",
    "innovation": "引入多模态对齐机制",
    "description": "针对现有 RAG 系统仅支持文本的问题..."
  }
]
```
```

### 10.5 Critic 系统提示词

```markdown
# docs/constraints/prompt_templates/critic_system.md

你是 ThesisMiner 的 Critic 候选评估 Agent。

## 评估维度

1. **创新性（30%）**：选题是否具有新颖性
2. **可行性（25%）**：是否可在学位论文周期内完成
3. **学术价值（25%）**：对学科发展的贡献
4. **方法论严谨性（20%）**：研究方法是否科学

## 评分标准

- 90-100：优秀，强烈推荐
- 80-89：良好，推荐
- 70-79：一般，可接受
- 60-69：及格，需修改
- 0-59：不及格，拒绝

## 输出格式

```json
[
  {
    "title": "...",
    "score": 85,
    "reasons": {
      "innovation": "创新性强",
      "feasibility": "可行",
      "academic_value": "价值高",
      "methodology": "方法严谨"
    },
    "suggestions": "建议进一步明确实验设计"
  }
]
```
```

---

## 11. 评估标准

### 11.1 评估维度

```yaml
# config/constraints/evaluation_rubric.yaml
evaluation:
  # 评估维度
  dimensions:
    - name: innovation
      label: "创新性"
      weight: 0.30
      criteria:
        excellent: "选题具有显著创新性，方法/视角独特"
        good: "选题有一定创新性，方法/视角较新"
        pass: "选题创新性一般，方法/视角常见"
        fail: "选题缺乏创新性，方法/视角陈旧"
    
    - name: feasibility
      label: "可行性"
      weight: 0.25
      criteria:
        excellent: "完全可行，资源/时间充足"
        good: "基本可行，资源/时间足够"
        pass: "可行但有一定挑战"
        fail: "不可行，资源/时间不足"
    
    - name: academic_value
      label: "学术价值"
      weight: 0.25
      criteria:
        excellent: "学术价值高，对学科发展有重要贡献"
        good: "学术价值较高，有一定贡献"
        pass: "学术价值一般"
        fail: "学术价值低"
    
    - name: methodology
      label: "方法论严谨性"
      weight: 0.20
      criteria:
        excellent: "方法论严谨，设计科学"
        good: "方法论较严谨，设计合理"
        pass: "方法论一般，设计基本合理"
        fail: "方法论不严谨，设计有问题"
```

### 11.2 评分等级

```yaml
  # 评分等级
  grades:
    - grade: "A"
      label: "优秀"
      score_range: [90, 100]
      recommendation: "强烈推荐"
    
    - grade: "B"
      label: "良好"
      score_range: [80, 89]
      recommendation: "推荐"
    
    - grade: "C"
      label: "一般"
      score_range: [70, 79]
      recommendation: "可接受"
    
    - grade: "D"
      label: "及格"
      score_range: [60, 69]
      recommendation: "需修改"
    
    - grade: "F"
      label: "不及格"
      score_range: [0, 59]
      recommendation: "拒绝"
```

---

## 12. 规则目录

### 12.1 完整规则列表

| 规则 ID | 规则名称 | 类型 | 严重级别 | 描述 |
|---------|----------|------|----------|------|
| TITLE_LENGTH | 标题长度 | HARD | ERROR | 硕士≤25字，博士≤30字 |
| TITLE_FORBIDDEN_PREFIX | 标题禁用前缀 | HARD | ERROR | 不以"基于"开头 |
| TITLE_EMPTY | 标题非空 | HARD | ERROR | 标题不能为空 |
| TITLE_FORBIDDEN_WORD | 标题禁用词 | HARD | WARNING | 避免空泛词 |
| TIMELINE_MISSING | 时间线缺失 | HARD | ERROR | 必须有开始和结束日期 |
| TIMELINE_ORDER | 时间线顺序 | HARD | ERROR | 开始<结束 |
| TIMELINE_TOO_SHORT | 时间线过短 | SOFT | WARNING | 硕士≥6月，博士≥12月 |
| TIMELINE_TOO_LONG | 时间线过长 | SOFT | WARNING | 硕士≤36月，博士≤60月 |
| LITERATURE_COUNT | 文献数量 | SOFT | WARNING | 硕士≥30篇，博士≥80篇 |
| LITERATURE_RECENT_RATIO | 近5年文献占比 | SOFT | WARNING | ≥50% |
| DUPLICATION_SINGLE_SOURCE | 单源查重 | HARD | ERROR | ≤10% |
| DUPLICATION_OVERALL | 总查重率 | HARD | ERROR | ≤30% |
| DISCIPLINE_MISMATCH | 学科不匹配 | SOFT | WARNING | 关键词匹配率≥20% |
| ADVISOR_MISALIGNMENT | 导师方向不对齐 | SOFT | WARNING | 与导师方向匹配 |
| NOVELTY_SCORE | 新颖性分数 | SCORE | ERROR | ≥60分 |
| AI_TRACE_DETECTED | AI痕迹检测 | SOFT | WARNING | 去除AI痕迹 |
| CITATION_FORMAT | 引用格式 | SOFT | WARNING | GB/T 7714 |
| STRUCTURE_COMPLETE | 结构完整 | HARD | ERROR | 包含必需章节 |
| WORD_COUNT | 字数要求 | SOFT | WARNING | 符合粒度要求 |

### 12.2 规则分类统计

```
┌─────────────────────────────────────────────────────────────────┐
│                    规则分类统计                                   │
├──────────────────┬──────────┬──────────┬──────────┬────────────┤
│ 类别             │ HARD     │ SOFT     │ SCORE    │ 总计       │
├──────────────────┼──────────┼──────────┼──────────┼────────────┤
│ 标题规则         │ 3        │ 1        │ 0        │ 4          │
│ 时间线规则       │ 2        │ 2        │ 0        │ 4          │
│ 文献规则         │ 0        │ 2        │ 0        │ 2          │
│ 查重规则         │ 2        │ 0        │ 0        │ 2          │
│ 学科规则         │ 0        │ 1        │ 0        │ 1          │
│ 导师规则         │ 0        │ 1        │ 0        │ 1          │
│ 新颖性规则       │ 0        │ 0        │ 1        │ 1          │
│ AI痕迹规则       │ 0        │ 1        │ 0        │ 1          │
│ 格式规则         │ 0        │ 2        │ 0        │ 2          │
│ 结构规则         │ 1        │ 0        │ 0        │ 1          │
│ 字数规则         │ 0        │ 1        │ 0        │ 1          │
├──────────────────┼──────────┼──────────┼──────────┼────────────┤
│ 总计             │ 8        │ 12       │ 1        │ 21         │
└──────────────────┴──────────┴──────────┴──────────┴────────────┘
```

---

## 13. 配置参考

### 13.1 硬约束配置

```yaml
# config/constraints/hard_rules.yaml
# 标题约束
title:
  length:
    master: 25
    doctor: 30
    default: 25
  forbidden_prefixes: ["基于", "关于", "浅谈", "试论"]
  forbidden_suffixes_short: ["研究", "应用", "探讨", "浅析", "初探"]

# 时间线约束
timeline:
  duration_months:
    master: [6, 36]
    doctor: [12, 60]

# 文献基线
literature:
  count_baseline:
    master: 30
    doctor: 80
  recent_ratio:
    min: 0.5
    target: 0.7

# 查重阈值
duplication:
  thresholds:
    overall_max: 0.30
    single_source_max: 0.10
    self_duplication: 0.20
  algorithm: levenshtein

# 学科匹配
discipline:
  keyword_match_threshold: 0.2

# 导师对齐
advisor:
  direction_alignment: true
```

### 13.2 新颖性配置

```yaml
# config/constraints/novelty_weights.yaml
novelty:
  weights:
    cross_discipline: 0.30
    method_transfer: 0.25
    pain_point_breakthrough: 0.25
    trend_forecast: 0.20
  thresholds:
    excellent: 85
    good: 70
    pass: 60
    fail: 0
```

### 13.3 样式配置

```yaml
# config/constraints/style_normalizer_rules.yaml
style:
  terminology:
    mapping: {...}
  citation:
    format: "GB/T 7714"
  punctuation:
    convert_to_chinese: true
  ai_trace_removal:
    enabled: true
    remove_phrases: [...]
    replace_patterns: [...]
```

---

## 14. 附录

### 14.1 约束速查表

```
┌─────────────────────────────────────────────────────────────────┐
│                    约束速查表                                     │
├──────────────────┬──────────────────┬──────────────────────────┤
│ 约束类别         │ 关键阈值         │ 失败处理                 │
├──────────────────┼──────────────────┼──────────────────────────┤
│ 标题长度         │ 硕士≤25, 博士≤30 │ 拒绝                     │
│ 标题前缀         │ 禁用"基于"       │ 拒绝                     │
│ 时间线跨度       │ 硕士6-36月       │ 警告                     │
│ 文献数量         │ 硕士≥30, 博士≥80 │ 警告                     │
│ 近5年文献        │ ≥50%             │ 警告                     │
│ 单源查重         │ ≤10%             │ 拒绝                     │
│ 总查重率         │ ≤30%             │ 拒绝                     │
│ 新颖性分数       │ ≥60              │ 拒绝（重新生成）         │
│ Critic评分       │ ≥60              │ 拒绝（重新生成）         │
│ AI痕迹           │ 去除             │ 自动修正                 │
│ 引用格式         │ GB/T 7714        │ 警告                     │
└──────────────────┴──────────────────┴──────────────────────────┘
```

### 14.2 常见问题

#### Q1: 如何添加自定义约束规则？

```python
from backend.constraints.rule_engine import Rule, RuleType, Severity

# 定义自定义规则
custom_rule = Rule(
    rule_id="CUSTOM_KEYWORD",
    rule_name="关键词检查",
    rule_type=RuleType.HARD,
    severity=Severity.ERROR,
    description="必须包含指定关键词",
    check_fn=lambda data: validate_keywords(data.get("content", ""))
)

# 添加到规则引擎
engine.rule_chain.add_rule(custom_rule)
```

#### Q2: 如何调整新颖性评分权重？

修改 `config/constraints/novelty_weights.yaml`：

```yaml
novelty:
  weights:
    cross_discipline: 0.40  # 提高
    method_transfer: 0.20   # 降低
    pain_point_breakthrough: 0.25
    trend_forecast: 0.15    # 降低
```

#### Q3: 硬约束和软约束的区别？

- **硬约束（HARD）**：必须满足，违反则拒绝生成
- **软约束（SOFT）**：建议满足，违反则标记警告

### 14.3 相关文档

- [Agent 参考](agent_reference.md)
- [API 参考](api_reference.md)
- [配置参考](configuration_reference.md)
- [故障排查参考](troubleshooting_reference.md)
- [硬约束设计](../constraints/hard_rules.md)
- [新颖性评分](../constraints/novelty_scoring.md)
- [规则目录](../constraints/rule_catalog.md)

### 14.4 术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 硬约束 | Hard Rule | 必须满足的规则 |
| 软约束 | Soft Rule | 建议遵守的规则 |
| 新颖性 | Novelty | 选题与已有文献的差异程度 |
| 门控 | Gate | 控制阶段流转的机制 |
| 规则链 | Rule Chain | 按顺序执行的规则集合 |
| 冲突解决 | Conflict Resolution | 多规则冲突时的解决策略 |
| 严重级别 | Severity | 规则违反的严重程度 |
| Levenshtein 距离 | Levenshtein Distance | 编辑距离，衡量字符串相似度 |
| AI 痕迹 | AI Trace | AI 生成文本的特征性词汇 |
| 样式规范化 | Style Normalization | 统一文本样式 |

### 14.5 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v8.0.0 | 2026-06-20 | 初始版本，50+ 规则 |
| v7.5.0 | 2026-05-15 | 添加 AI 痕迹去除 |
| v7.0.0 | 2026-04-01 | 重构为规则引擎架构 |
| v6.0.0 | 2026-02-10 | 添加五阶段门控 |

---

## 15. 约束规则详解

### 15.1 标题约束规则详解

#### 15.1.1 标题长度规则（TITLE_LENGTH）

**规则定义**：
- 规则 ID：`TITLE_LENGTH`
- 类型：HARD（硬约束）
- 严重级别：ERROR
- 描述：硕士标题 ≤25 字，博士标题 ≤30 字

**实现细节**：

```python
def validate_title_length(title: str, degree: str) -> List[RuleViolation]:
    """验证标题长度"""
    violations = []
    
    # 根据学位确定最大长度
    if degree == "硕士":
        max_length = 25
    elif degree == "博士":
        max_length = 30
    else:
        max_length = 25  # 默认按硕士
    
    # 计算标题长度（中英文混合计算）
    # 中文字符算 1 字，英文字符算 0.5 字（2 个英文 = 1 字）
    length = 0
    for char in title:
        if '\u4e00' <= char <= '\u9fff':
            length += 1  # 中文
        elif char.isalpha():
            length += 0.5  # 英文
        elif char.isdigit():
            length += 0.5  # 数字
    
    if length > max_length:
        violations.append(RuleViolation(
            rule_id="TITLE_LENGTH",
            rule_name="标题长度",
            severity=Severity.ERROR,
            message=f"标题长度 {length:.1f} 超过 {degree}限制 {max_length} 字",
            actual_value=length,
            expected_value=max_length
        ))
    
    return violations
```

**测试用例**：

```python
# 测试 1: 合法的硕士标题
assert len(validate_title_length("面向多模态文档的检索增强生成方法", "硕士")) == 0

# 测试 2: 超长的硕士标题
long_title = "这是一个非常非常非常非常非常非常非常非常长的标题超过二十五个字"
assert len(validate_title_length(long_title, "硕士")) == 1

# 测试 3: 合法的博士标题
assert len(validate_title_length("基于知识图谱的大语言模型幻觉检测与缓解方法研究", "博士")) == 0
```

#### 15.1.2 标题禁用前缀规则（TITLE_FORBIDDEN_PREFIX）

**规则定义**：
- 规则 ID：`TITLE_FORBIDDEN_PREFIX`
- 类型：HARD
- 严重级别：ERROR
- 描述：标题不应以"基于"、"关于"、"浅谈"、"试论"开头

**禁用前缀列表**：

| 前缀 | 原因 | 替代方案 |
|------|------|----------|
| 基于 | 过于空泛，缺乏具体性 | 直接描述研究对象 |
| 关于 | 口语化，不学术 | 直接描述研究内容 |
| 浅谈 | 过于谦逊，缺乏自信 | 直接陈述研究观点 |
| 试论 | 过时表达，现代学术少用 | 直接论述 |

**示例**：

```
✗ 基于：基于深度学习的图像识别研究
✓ 修改：面向图像识别的深度学习方法

✗ 关于：关于人工智能在教育中的应用
✓ 修改：人工智能在教育领域的应用研究

✗ 浅谈：浅谈大语言模型的幻觉问题
✓ 修改：大语言模型幻觉问题的成因与对策
```

#### 15.1.3 标题禁用词规则（TITLE_FORBIDDEN_WORD）

**规则定义**：
- 规则 ID：`TITLE_FORBIDDEN_WORD`
- 类型：HARD
- 严重级别：WARNING
- 描述：标题不应以空泛词结尾（短标题时）

**禁用后缀**：

| 后缀 | 问题 | 示例 |
|------|------|------|
| 研究 | 过于空泛 | "深度学习研究" |
| 应用 | 缺乏具体性 | "人工智能应用" |
| 探讨 | 过于谦逊 | "教育公平探讨" |
| 浅析 | 缺乏深度 | "算法浅析" |
| 初探 | 过于谦逊 | "区块链初探" |

**判断逻辑**：
- 如果标题长度 ≤10 字且以禁用词结尾，则警告
- 如果标题长度 >10 字，则允许（因为有更多具体内容）

### 15.2 时间线约束规则详解

#### 15.2.1 时间线跨度规则

**学位对应的时间跨度**：

| 学位 | 最短 | 最长 | 典型 |
|------|------|------|------|
| 硕士 | 6 个月 | 36 个月 | 12-24 个月 |
| 博士 | 12 个月 | 60 个月 | 36-48 个月 |

**实现细节**：

```python
from datetime import datetime
from typing import Tuple

def calculate_duration_months(start: str, end: str) -> int:
    """计算时间跨度（月）"""
    start_date = datetime.strptime(start, "%Y-%m")
    end_date = datetime.strptime(end, "%Y-%m")
    
    months = (end_date.year - start_date.year) * 12
    months += (end_date.month - start_date.month)
    
    return months

def validate_timeline_duration(timeline: dict, degree: str) -> List[RuleViolation]:
    """验证时间线跨度"""
    violations = []
    
    start = timeline.get("start")
    end = timeline.get("end")
    
    if not start or not end:
        return violations  # 由 TIMELINE_MISSING 规则处理
    
    duration = calculate_duration_months(start, end)
    
    # 获取学位对应的时间范围
    if degree == "硕士":
        min_months, max_months = 6, 36
    elif degree == "博士":
        min_months, max_months = 12, 60
    else:
        min_months, max_months = 6, 36
    
    if duration < min_months:
        violations.append(RuleViolation(
            rule_id="TIMELINE_TOO_SHORT",
            rule_name="时间线过短",
            severity=Severity.WARNING,
            message=f"时间跨度 {duration} 个月少于 {degree}最低要求 {min_months} 个月",
            actual_value=duration,
            expected_value=f"≥{min_months}"
        ))
    
    if duration > max_months:
        violations.append(RuleViolation(
            rule_id="TIMELINE_TOO_LONG",
            rule_name="时间线过长",
            severity=Severity.WARNING,
            message=f"时间跨度 {duration} 个月超过 {degree}最高要求 {max_months} 个月",
            actual_value=duration,
            expected_value=f"≤{max_months}"
        ))
    
    return violations
```

### 15.3 文献基线规则详解

#### 15.3.1 文献数量基线

**学位对应的文献数量**：

| 学位 | 最低数量 | 推荐数量 | 高质量要求 |
|------|----------|----------|------------|
| 硕士 | 30 篇 | 50-80 篇 | ≥10 篇 Q1/Q2 |
| 博士 | 80 篇 | 150-200 篇 | ≥30 篇 Q1/Q2 |

#### 15.3.2 文献质量评估

```python
def assess_literature_quality(literature: list) -> dict:
    """评估文献质量"""
    total = len(literature)
    
    # 统计各质量等级
    q1_q2 = sum(1 for p in literature if p.get("journal_rank") in ["Q1", "Q2"])
    top_conf = sum(1 for p in literature if p.get("conference_tier") in ["A*", "A"])
    recent = sum(1 for p in literature if p.get("year", 0) >= 2021)
    
    return {
        "total": total,
        "q1_q2_count": q1_q2,
        "q1_q2_ratio": q1_q2 / total if total else 0,
        "top_conf_count": top_conf,
        "top_conf_ratio": top_conf / total if total else 0,
        "recent_count": recent,
        "recent_ratio": recent / total if total else 0,
        "quality_score": (
            (q1_q2 / total if total else 0) * 0.4 +
            (top_conf / total if total else 0) * 0.3 +
            (recent / total if total else 0) * 0.3
        )
    }
```

### 15.4 查重规则详解

#### 15.4.1 查重算法

ThesisMiner v8.0 使用 Levenshtein 距离进行查重：

```python
def levenshtein_distance(s1: str, s2: str) -> int:
    """计算 Levenshtein 编辑距离"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def calculate_similarity(s1: str, s2: str) -> float:
    """计算相似度（0-1）"""
    if not s1 or not s2:
        return 0.0
    
    distance = levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    return 1.0 - (distance / max_len)
```

#### 15.4.2 查重阈值

| 查重类型 | 阈值 | 处理 |
|----------|------|------|
| 单源重复率 | ≤10% | 超过则拒绝 |
| 总重复率 | ≤30% | 超过则拒绝 |
| 自我重复 | ≤20% | 超过则警告 |

### 15.5 新颖性评分详解

#### 15.5.1 四维评分计算示例

```python
# 示例选题：基于知识图谱的大语言模型幻觉检测

# 各维度评分
dimension_scores = {
    "cross_discipline": 85,        # 跨学科融合（知识图谱 × LLM）
    "method_transfer": 75,         # 方法迁移（KG 检测方法迁移到 LLM）
    "pain_point_breakthrough": 90, # 痛点突破（幻觉问题是重要痛点）
    "trend_forecast": 80           # 趋势预测（可信 AI 是趋势）
}

# 权重
weights = {
    "cross_discipline": 0.30,
    "method_transfer": 0.25,
    "pain_point_breakthrough": 0.25,
    "trend_forecast": 0.20
}

# 计算
total = (
    85 * 0.30 +      # 25.5
    75 * 0.25 +      # 18.75
    90 * 0.25 +      # 22.5
    80 * 0.20         # 16.0
)
# total = 82.75

# 风险等级
if total >= 85:
    risk = "low"      # 低风险
elif total >= 60:
    risk = "medium"   # 中风险
else:
    risk = "high"     # 高风险

# 结果：82.75 分，中风险
```

#### 15.5.2 新颖性评分流程

```
[输入: 选题 + 文献]
       │
       ▼
[1. 本地新颖性检查]
   │  - Levenshtein 距离计算
   │  - 与每篇文献比较
   │  - 取最低新颖性
   │
   ▼
[2. LLM 评估]
   │  - 四维评分
   │  - 0-100 分
   │
   ▼
[3. 评分融合]
   │  - min(LLM分数, 本地分数×100)
   │  - 保守策略
   │
   ▼
[4. 风险等级判定]
   │  - ≥85: 低风险
   │  - 60-84: 中风险
   │  - <60: 高风险
   │
   ▼
[输出: 最终评分 + 风险等级]
```

### 15.6 AI 痕迹去除详解

#### 15.6.1 AI 痕迹特征

**词汇级特征**：

| 类别 | 示例 | 处理 |
|------|------|------|
| 空泛连接词 | 总之、综上所述 | 删除 |
| AI 常用词 | 值得注意的是 | 删除 |
| 过度修饰 | 显著的、重要的 | 删除 |
| 第一人称 | 本文、本研究 | 替换/删除 |

**句式级特征**：

| 类别 | 示例 | 处理 |
|------|------|------|
| 被动语态 | 被广泛应用于 | 转主动 |
| 长句 | 超过 100 字 | 拆短 |
| 模板句式 | 本文提出了一种...方法 | 简化 |

**段落级特征**：

| 类别 | 示例 | 处理 |
|------|------|------|
| 模板过渡 | 首先、其次、最后 | 自然化 |
| 段落过长 | 超过 500 字 | 拆分 |
| 逻辑生硬 | 缺乏过渡 | 添加衔接 |

#### 15.6.2 去除效果对比

**原始文本（含 AI 痕迹）**：

```
总之，大语言模型在自然语言处理领域取得了显著的成果。值得注意的是，
本文提出了一种基于知识图谱的幻觉检测方法。该方法有效地解决了大语言
模型的幻觉问题，具有重要的学术价值。综上所述，本研究的贡献是显著的。
```

**去除后文本**：

```
大语言模型在自然语言处理领域取得了丰富成果。提出一种基于知识图谱的
幻觉检测方法，该方法解决了大语言模型的幻觉问题，具有一定的学术价值。
研究的贡献在于提供了新的技术路径。
```

### 15.7 多粒度生成规则详解

#### 15.7.1 标题生成规则

**生成流程**：

```
[输入: 研究方向 + 学位]
       │
       ▼
[1. 分析研究方向]
   │  - 提取关键词
   │  - 确定研究类型
   │
   ▼
[2. 生成候选标题]
   │  - 3-5 个候选
   │  - 不同角度
   │
   ▼
[3. 硬约束检查]
   │  - 长度检查
   │  - 禁用词检查
   │
   ▼
[4. 输出合法标题]
```

**标题生成模板**：

```
模板 1: 面向[研究对象]的[方法]方法
模板 2: [方法]在[领域]中的应用
模板 3: [问题]的[解决方案]研究
模板 4: 基于[技术]的[任务]系统
模板 5: [对象]的[方法]与[应用]
```

#### 15.7.2 摘要生成规则

**五要素结构**：

```
[背景] → [问题] → [方法] → [结果] → [贡献]
  │        │        │        │        │
  │        │        │        │        │
  ▼        ▼        ▼        ▼        ▼
随着...   现有...   提出...   实验...   该方法...
广泛应用  存在...   通过...   显示...   为...提供...
```

**字数分配**：

| 要素 | 字数 | 占比 |
|------|------|------|
| 背景 | 50-80 字 | 15-20% |
| 问题 | 50-80 字 | 15-20% |
| 方法 | 80-120 字 | 25-30% |
| 结果 | 60-100 字 | 20-25% |
| 贡献 | 40-60 字 | 10-15% |
| 总计 | 300-500 字 | 100% |

#### 15.7.3 大纲生成规则

**章节结构**：

```
第一章 引言
  1.1 研究背景
  1.2 研究问题
  1.3 研究意义
  1.4 论文结构

第二章 相关工作
  2.1 [领域 A]
  2.2 [领域 B]
  2.3 [技术 C]
  2.4 现有方法分析

第三章 研究内容
  3.1 问题定义
  3.2 研究框架
  3.3 关键问题

第四章 方法
  4.1 方法概述
  4.2 [方法 A]
  4.3 [方法 B]
  4.4 算法设计

第五章 实验
  5.1 实验设置
  5.2 数据集
  5.3 评价指标
  5.4 实验结果
  5.5 结果分析

第六章 结论
  6.1 研究总结
  6.2 主要贡献
  6.3 未来工作
```

### 15.8 阶段门控详解

#### 15.8.1 各阶段门控条件

| 阶段 | 门控条件 | 失败处理 | 最大重试 |
|------|----------|----------|----------|
| info_confirm | 信息完整（学科、学位、方向） | 追问用户 | 5 次 |
| creativity | 生成 ≥3 个候选 | 重新生成 | 3 次 |
| validation | score ≥60 | 重新生成 | 2 次 |
| generation | 报告生成成功 | 模板兜底 | 3 次 |
| deep_assist | 用户主动结束 | 循环 | 无限 |

#### 15.8.2 门控检查流程

```python
async def check_stage_gate(stage: Stage, result: dict) -> GateResult:
    """检查阶段门控"""
    gate = STAGE_GATES[stage]
    
    # 1. 检查必需字段
    for field in gate.required_fields:
        if field not in result:
            return GateResult(
                passed=False,
                stage=stage.value,
                reason=f"缺少必需字段: {field}",
                missing_fields=[field]
            )
    
    # 2. 检查分数阈值
    if gate.min_score > 0:
        score = result.get("score", 0)
        if score < gate.min_score:
            return GateResult(
                passed=False,
                stage=stage.value,
                score=score,
                reason=f"分数 {score} 低于阈值 {gate.min_score}"
            )
    
    # 3. 检查候选数量（creativity 阶段）
    if stage == Stage.CREATIVITY:
        candidates = result.get("candidates", [])
        if len(candidates) < 3:
            return GateResult(
                passed=False,
                stage=stage.value,
                reason=f"候选数量 {len(candidates)} 少于 3"
            )
    
    return GateResult(
        passed=True,
        stage=stage.value,
        score=result.get("score")
    )
```

### 15.9 规则引擎详解

#### 15.9.1 规则链执行

```python
class RuleChain:
    """规则链"""
    
    def __init__(self):
        self.rules: List[Rule] = []
        self.execution_order = []
    
    def add_rule(self, rule: Rule, priority: int = 0) -> None:
        """添加规则（按优先级排序）"""
        self.rules.append((priority, rule))
        self.rules.sort(key=lambda x: x[0], reverse=True)
    
    def execute(self, input_data: dict) -> List[RuleViolation]:
        """执行规则链"""
        all_violations = []
        
        for priority, rule in self.rules:
            if not rule.enabled:
                continue
            
            start_time = time.time()
            
            try:
                violations = rule.check_fn(input_data)
                all_violations.extend(violations)
                
                # 记录执行信息
                self.execution_order.append({
                    "rule_id": rule.rule_id,
                    "priority": priority,
                    "duration_ms": (time.time() - start_time) * 1000,
                    "violation_count": len(violations)
                })
                
            except Exception as e:
                # 规则执行出错，记录但不中断
                self.execution_order.append({
                    "rule_id": rule.rule_id,
                    "priority": priority,
                    "error": str(e)
                })
        
        return all_violations
```

#### 15.9.2 冲突解决策略

```python
class ConflictResolver:
    """冲突解决器"""
    
    def resolve(self, violations: List[RuleViolation]) -> List[RuleViolation]:
        """解决冲突"""
        # 1. 按严重级别排序
        severity_order = {
            Severity.ERROR: 0,
            Severity.WARNING: 1,
            Severity.INFO: 2
        }
        violations.sort(key=lambda v: severity_order[v.severity])
        
        # 2. 去重
        seen = set()
        unique = []
        for v in violations:
            key = (v.rule_id, v.severity)
            if key not in seen:
                seen.add(key)
                unique.append(v)
        
        # 3. 解决矛盾规则
        # 如果同一字段有 ERROR 和 WARNING，只保留 ERROR
        error_rules = {v.rule_id for v in unique if v.severity == Severity.ERROR}
        result = [
            v for v in unique
            if v.severity != Severity.WARNING or v.rule_id not in error_rules
        ]
        
        return result
```

### 15.10 样式规范化详解

#### 15.10.1 术语统一

**术语映射表**：

| 标准术语 | 变体 | 处理 |
|----------|------|------|
| 大语言模型 | LLM, Large Language Model, 大型语言模型 | 统一为"大语言模型" |
| 人工智能 | AI, Artificial Intelligence | 统一为"人工智能" |
| 机器学习 | ML, Machine Learning | 统一为"机器学习" |
| 深度学习 | DL, Deep Learning | 统一为"深度学习" |
| 自然语言处理 | NLP, Natural Language Processing | 统一为"自然语言处理" |

#### 15.10.2 引用格式统一

**GB/T 7714 格式**：

```
[序号] 作者. 题名[文献类型标志]. 刊名, 年, 卷(期): 页码.

示例:
[1] 张三, 李四. 大语言模型综述[J]. 计算机学报, 2025, 48(3): 1-20.
[2] Wang Y, Smith J. Attention Is All You Need[C]//NeurIPS. 2017: 5998-6008.
```

**格式化函数**：

```python
def format_citation_gbt7714(paper: dict) -> str:
    """格式化为 GB/T 7714"""
    authors = ", ".join(paper.get("authors", []))
    title = paper.get("title", "")
    year = paper.get("year", "")
    
    # 期刊论文
    if paper.get("type") == "journal":
        journal = paper.get("journal", "")
        volume = paper.get("volume", "")
        issue = paper.get("issue", "")
        pages = paper.get("pages", "")
        return f"[{paper['id']}] {authors}. {title}[J]. {journal}, {year}, {volume}({issue}): {pages}."
    
    # 会议论文
    elif paper.get("type") == "conference":
        conf = paper.get("conference", "")
        pages = paper.get("pages", "")
        return f"[{paper['id']}] {authors}. {title}[C]//{conf}. {year}: {pages}."
    
    return f"[{paper['id']}] {authors}. {title}. {year}."
```

### 15.11 评估标准详解

#### 15.11.1 评估维度权重

```
┌─────────────────────────────────────────────────────────────────┐
│                    评估维度权重                                   │
├──────────────────┬────────┬────────────────────────────────────┤
│ 维度             │ 权重   │ 评估要点                           │
├──────────────────┼────────┼────────────────────────────────────┤
│ 创新性           │ 30%    │ - 方法新颖性                       │
│ (innovation)     │        │ - 视角独特性                       │
│                  │        │ - 问题定义创新                     │
├──────────────────┼────────┼────────────────────────────────────┤
│ 可行性           │ 25%    │ - 技术可行性                       │
│ (feasibility)    │        │ - 资源可获得性                     │
│                  │        │ - 时间充裕度                       │
├──────────────────┼────────┼────────────────────────────────────┤
│ 学术价值         │ 25%    │ - 理论贡献                         │
│ (academic_value) │        │ - 实践意义                         │
│                  │        │ - 学科推动                         │
├──────────────────┼────────┼────────────────────────────────────┤
│ 方法论严谨性     │ 20%    │ - 方法科学性                       │
│ (methodology)    │        │ - 实验设计                         │
│                  │        │ - 数据分析                         │
└──────────────────┴────────┴────────────────────────────────────┘
```

#### 15.11.2 评分等级

| 等级 | 分数范围 | 评价 | 建议 |
|------|----------|------|------|
| A | 90-100 | 优秀 | 强烈推荐 |
| B | 80-89 | 良好 | 推荐 |
| C | 70-79 | 一般 | 可接受 |
| D | 60-69 | 及格 | 需修改 |
| F | 0-59 | 不及格 | 拒绝 |

### 15.12 约束规则测试

#### 15.12.1 单元测试

```python
# tests/test_constraints.py
import pytest
from backend.constraints.hard_rules import (
    validate_title,
    validate_timeline,
    validate_literature,
    validate_duplication
)
from backend.constraints.rule_engine import RuleEngine
from backend.constraints.stage_gate import STAGE_GATES, Stage
from backend.constraints.novelty_scorer import NoveltyScorer

class TestTitleValidation:
    """标题验证测试"""
    
    def test_valid_master_title(self):
        """测试合法硕士标题"""
        title = "面向多模态文档的检索增强生成方法"
        violations = validate_title(title, "硕士")
        assert len(violations) == 0
    
    def test_too_long_title(self):
        """测试过长标题"""
        title = "这是一个非常非常非常非常非常非常非常非常长的标题"
        violations = validate_title(title, "硕士")
        assert any(v.rule_id == "TITLE_LENGTH" for v in violations)
    
    def test_forbidden_prefix(self):
        """测试禁用前缀"""
        title = "基于深度学习的研究"
        violations = validate_title(title, "硕士")
        assert any(v.rule_id == "TITLE_FORBIDDEN_PREFIX" for v in violations)
    
    def test_empty_title(self):
        """测试空标题"""
        violations = validate_title("", "硕士")
        assert any(v.rule_id == "TITLE_EMPTY" for v in violations)


class TestTimelineValidation:
    """时间线验证测试"""
    
    def test_valid_timeline(self):
        """测试合法时间线"""
        timeline = {"start": "2026-09", "end": "2027-06"}
        violations = validate_timeline(timeline, "硕士")
        assert len(violations) == 0
    
    def test_missing_dates(self):
        """测试缺失日期"""
        timeline = {"start": "2026-09"}
        violations = validate_timeline(timeline, "硕士")
        assert any(v.rule_id == "TIMELINE_MISSING" for v in violations)
    
    def test_invalid_order(self):
        """测试顺序错误"""
        timeline = {"start": "2027-06", "end": "2026-09"}
        violations = validate_timeline(timeline, "硕士")
        assert any(v.rule_id == "TIMELINE_INVALID_ORDER" for v in violations)


class TestNoveltyScorer:
    """新颖性评分测试"""
    
    def test_high_novelty(self):
        """测试高新颖性"""
        scorer = NoveltyScorer()
        scores = {
            "cross_discipline": 90,
            "method_transfer": 85,
            "pain_point_breakthrough": 88,
            "trend_forecast": 82
        }
        result = scorer.calculate(scores)
        assert result.total_score >= 85
        assert result.risk_level == "low"
    
    def test_low_novelty(self):
        """测试低新颖性"""
        scorer = NoveltyScorer()
        scores = {
            "cross_discipline": 50,
            "method_transfer": 55,
            "pain_point_breakthrough": 45,
            "trend_forecast": 60
        }
        result = scorer.calculate(scores)
        assert result.total_score < 60
        assert result.risk_level == "high"


class TestStageGate:
    """阶段门控测试"""
    
    def test_info_confirm_pass(self):
        """测试 info_confirm 通过"""
        result = {
            "discipline": "计算机科学",
            "degree": "硕士",
            "direction": "大语言模型"
        }
        gate = STAGE_GATES[Stage.INFO_CONFIRM]
        gate_result = gate.check(result)
        assert gate_result.passed is True
    
    def test_info_confirm_fail(self):
        """测试 info_confirm 失败"""
        result = {
            "discipline": "计算机科学"
        }
        gate = STAGE_GATES[Stage.INFO_CONFIRM]
        gate_result = gate.check(result)
        assert gate_result.passed is False
        assert "degree" in gate_result.missing_fields
    
    def test_validation_pass(self):
        """测试 validation 通过"""
        result = {
            "evaluations": [...],
            "score": 75
        }
        gate = STAGE_GATES[Stage.VALIDATION]
        gate_result = gate.check(result)
        assert gate_result.passed is True
    
    def test_validation_fail(self):
        """测试 validation 失败"""
        result = {
            "evaluations": [...],
            "score": 45
        }
        gate = STAGE_GATES[Stage.VALIDATION]
        gate_result = gate.check(result)
        assert gate_result.passed is False


class TestRuleEngine:
    """规则引擎测试"""
    
    def test_validate_valid_input(self):
        """测试合法输入"""
        engine = RuleEngine()
        input_data = {
            "title": "面向多模态文档的检索增强生成方法",
            "degree": "硕士",
            "timeline": {"start": "2026-09", "end": "2027-06"},
            "literature": [{"title": "Paper 1", "year": 2025}] * 30
        }
        result = engine.validate(input_data)
        assert result["passed"] is True
    
    def test_validate_invalid_input(self):
        """测试非法输入"""
        engine = RuleEngine()
        input_data = {
            "title": "基于深度学习的研究",
            "degree": "硕士"
        }
        result = engine.validate(input_data)
        assert result["passed"] is False
        assert len(result["errors"]) > 0
```

### 15.13 约束规则最佳实践

#### 15.13.1 规则设计原则

1. **单一职责**：每个规则只检查一个方面
2. **可配置**：规则参数通过 YAML 配置
3. **可扩展**：易于添加新规则
4. **可测试**：每个规则有对应的单元测试
5. **性能优先**：规则执行快速，避免复杂计算

#### 15.13.2 规则优先级

```python
# 规则优先级（数字越大越先执行）
RULE_PRIORITIES = {
    "TITLE_EMPTY": 100,           # 标题非空（最高）
    "TITLE_LENGTH": 90,           # 标题长度
    "TITLE_FORBIDDEN_PREFIX": 80, # 标题禁用前缀
    "TIMELINE_MISSING": 70,       # 时间线缺失
    "TIMELINE_ORDER": 60,         # 时间线顺序
    "DUPLICATION_SINGLE_SOURCE": 50, # 单源查重
    "LITERATURE_COUNT": 40,       # 文献数量
    "NOVELTY_SCORE": 30,          # 新颖性分数
    "AI_TRACE_DETECTED": 20,      # AI 痕迹
    "CITATION_FORMAT": 10         # 引用格式（最低）
}
```

#### 15.13.3 性能优化

```python
# 1. 规则缓存
from functools import lru_cache

@lru_cache(maxsize=128)
def cached_validate_title(title: str, degree: str) -> tuple:
    """缓存标题验证结果"""
    violations = validate_title(title, degree)
    return tuple((v.rule_id, v.severity) for v in violations)

# 2. 并行执行
import asyncio

async def parallel_validate(input_data: dict) -> List[RuleViolation]:
    """并行执行规则"""
    tasks = [
        asyncio.create_task(validate_title_async(input_data)),
        asyncio.create_task(validate_timeline_async(input_data)),
        asyncio.create_task(validate_literature_async(input_data))
    ]
    results = await asyncio.gather(*tasks)
    
    violations = []
    for result in results:
        violations.extend(result)
    
    return violations

# 3. 短路执行
def short_circuit_validate(input_data: dict) -> List[RuleViolation]:
    """短路执行（遇到 ERROR 立即返回）"""
    for rule in CRITICAL_RULES:
        violations = rule.check_fn(input_data)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        if errors:
            return errors  # 立即返回，不继续检查
    return []
```

### 15.14 约束规则扩展

#### 15.14.1 添加自定义规则

```python
from backend.constraints.rule_engine import (
    Rule, RuleType, Severity, RuleViolation
)

# 自定义规则：检查是否包含方法论
def validate_methodology(content: str) -> List[RuleViolation]:
    """验证是否包含方法论"""
    violations = []
    
    methodology_keywords = ["方法", "算法", "模型", "框架", "流程"]
    
    has_methodology = any(kw in content for kw in methodology_keywords)
    
    if not has_methodology:
        violations.append(RuleViolation(
            rule_id="METHODOLOGY_MISSING",
            rule_name="方法论缺失",
            severity=Severity.WARNING,
            message="内容中未检测到方法论相关描述",
            actual_value="无方法论关键词",
            expected_value="包含方法/算法/模型等关键词"
        ))
    
    return violations

# 创建规则
methodology_rule = Rule(
    rule_id="METHODOLOGY_MISSING",
    rule_name="方法论缺失",
    rule_type=RuleType.SOFT,
    severity=Severity.WARNING,
    description="内容应包含方法论描述",
    check_fn=lambda data: validate_methodology(data.get("content", ""))
)

# 添加到规则引擎
engine = RuleEngine()
engine.rule_chain.add_rule(methodology_rule, priority=15)
```

#### 15.14.2 自定义评分维度

```python
# 自定义评分维度：社会影响
def calculate_social_impact(topic: dict) -> float:
    """计算社会影响分数"""
    impact_keywords = {
        "high": ["医疗", "教育", "安全", "环境", "贫困"],
        "medium": ["效率", "成本", "体验", "服务"],
        "low": ["理论", "算法", "模型"]
    }
    
    text = topic.get("title", "") + topic.get("abstract", "")
    
    for level, keywords in impact_keywords.items():
        if any(kw in text for kw in keywords):
            return {"high": 90, "medium": 70, "low": 50}[level]
    
    return 60  # 默认

# 集成到评分系统
class ExtendedNoveltyScorer(NoveltyScorer):
    """扩展的新颖性评分器"""
    
    WEIGHTS = {
        "cross_discipline": 0.25,          # 降低
        "method_transfer": 0.20,           # 降低
        "pain_point_breakthrough": 0.20,   # 降低
        "trend_forecast": 0.15,            # 降低
        "social_impact": 0.20              # 新增
    }
    
    def calculate(self, dimension_scores: Dict[str, float]) -> NoveltyScore:
        # 添加社会影响维度
        if "social_impact" not in dimension_scores:
            dimension_scores["social_impact"] = 70  # 默认
        
        return super().calculate(dimension_scores)
```

---

## 16. 约束规则运维

### 16.1 规则监控

```python
# backend/observability/rule_metrics.py
from prometheus_client import Counter, Histogram

# 规则执行次数
rule_executions = Counter(
    "thesisminer_rule_executions_total",
    "规则执行总次数",
    ["rule_id", "severity"]
)

# 规则违反次数
rule_violations = Counter(
    "thesisminer_rule_violations_total",
    "规则违反次数",
    ["rule_id", "severity"]
)

# 规则执行耗时
rule_duration = Histogram(
    "thesisminer_rule_duration_seconds",
    "规则执行耗时",
    ["rule_id"]
)

# 门控通过率
gate_pass_rate = Gauge(
    "thesisminer_gate_pass_rate",
    "门控通过率",
    ["stage"]
)
```

### 16.2 规则日志

```python
# 规则执行日志
{
    "timestamp": "2026-06-20T10:30:00Z",
    "level": "INFO",
    "rule_id": "TITLE_LENGTH",
    "severity": "ERROR",
    "input": {
        "title": "基于深度学习的研究",
        "degree": "硕士"
    },
    "violations": [
        {
            "rule_id": "TITLE_LENGTH",
            "message": "标题以空泛词结尾",
            "actual_value": "研究",
            "expected_value": "具体内容"
        }
    ],
    "duration_ms": 5
}
```

### 16.3 规则告警

```python
# 告警规则
ALERT_RULES = [
    {
        "name": "高违反率",
        "condition": "rule_violations_total{severity='ERROR'} > 100",
        "duration": "5m",
        "action": "notify_admin"
    },
    {
        "name": "门控通过率低",
        "condition": "gate_pass_rate{stage='validation'} < 0.5",
        "duration": "10m",
        "action": "notify_admin"
    }
]
```

---

> **文档结束**
> 
> 如有疑问，请参考相关文档或提交 Issue。
