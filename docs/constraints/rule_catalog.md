# ThesisMiner v8.0 规则目录文档（Rule Catalog）

> 版本：v8.0
> 最后更新：2026-06-19
> 适用范围：`backend/constraints/`、`backend/orchestration/hooks/`、`backend/agents/`
> 配置源：`config/constraints/hard_rules.yaml`、`config/constraints/novelty_weights.yaml`、`config/constraints/style_rules.yaml`
> 文档维护：ThesisMiner 团队

---

## 目录

- [0. 文档说明](#0-文档说明)
- [1. 规则体系总览](#1-规则体系总览)
- [2. 硬约束规则（Hard Rules）](#2-硬约束规则hard-rules)
- [3. 新颖性评分规则（Novelty Scoring）](#3-新颖性评分规则novelty-scoring)
- [4. 去 AI 痕迹规则（Style Normalization）](#4-去-ai-痕迹规则style-normalization)
- [5. 多粒度生成规则（Multi-Granularity）](#5-多粒度生成规则multi-granularity)
- [6. 五阶段门禁规则（Stage Gate）](#6-五阶段门禁规则stage-gate)
- [7. 学术规范规则（Academic Standards）](#7-学术规范规则academic-standards)
- [8. 规则优先级与冲突解决](#8-规则优先级与冲突解决)
- [9. 规则版本管理](#9-规则版本管理)
- [10. 完整规则示例库](#10-完整规则示例库)
- [11. 附录](#11-附录)

---

## 0. 文档说明

### 0.1 文档目的

本文档是 ThesisMiner v8.0 的**规则目录权威参考**，系统化地收录了项目内所有可配置、可校验、可执行的规则定义。文档面向以下使用场景：

1. **规则查询**：开发者需要查阅某条规则的阈值、验证逻辑、错误消息时，可直接定位至对应章节。
2. **规则扩展**：新增规则时，可参照本文档的规则模板与编号规范，确保新规则与既有体系一致。
3. **规则调优**：运维人员或高级用户需要调整阈值时，可参照本文档理解每条规则的语义与影响范围。
4. **规则审计**：质量保障团队可通过本文档核对线上配置与文档定义的一致性。
5. **规则教学**：新加入团队成员可通过本文档快速理解 ThesisMiner 的约束体系设计哲学。

ThesisMiner v8.0 的规则体系是整个系统"严谨性"与"规范性"的基石。与 v7 相比，v8 在以下方面进行了显著扩展：

- **新增四维创意引擎**：将新颖性评估从单一相似度阈值扩展为四维加权评分（学科交叉 30% / 方法迁移 25% / 痛点突破 25% / 趋势前瞻 20%）。
- **新增去 AI 痕迹规则**：内置 55 条模板词替换规则，覆盖篇章连接词、强调副词、转折让步、因果推导、程度修饰、学术套话、列举模板、对仗排比、冗余修饰、口语化混用、过度绝对化等 11 大类。
- **新增多粒度生成规则**：支持标题级（≤20 字）、摘要级（200-300 字）、大纲级（3 级目录）、全文级（≥5000 字）四种粒度的差异化生成与校验。
- **新增五阶段门禁**：将原本线性的生成流程重构为 info_confirm → creativity → validation → generation → deep_assist 的闭环导航流，每阶段具备进入/退出/回退条件。
- **新增学术规范规则**：内置 100+ 引用格式校验规则，支持 GB/T 7714、APA、MLA、Chicago、IEEE、Vancouver 六种引用格式。

### 0.2 适用读者

| 读者角色 | 推荐章节 | 阅读目的 |
|---------|---------|---------|
| 后端开发者 | 全文 | 理解规则实现细节，进行规则扩展 |
| 前端开发者 | 第 2、4、5 章 | 理解规则错误消息，进行 UI 提示 |
| 测试工程师 | 第 2、6、10 章 | 编写规则测试用例，覆盖边界条件 |
| 运维工程师 | 第 8、9 章 | 规则版本管理、冲突排查 |
| 产品经理 | 第 1、3、6 章 | 理解规则业务语义，进行需求评审 |
| 学术顾问 | 第 3、7 章 | 校验规则学术合理性 |
| 终端用户 | 第 2、5 章 | 理解规则约束，避免违规 |

### 0.3 术语表

| 术语 | 英文 | 释义 |
|------|------|------|
| 硬约束 | Hard Constraint | 必须满足的规则，违反则阻断流程 |
| 软约束 | Soft Constraint | 建议满足的规则，违反仅警告 |
| 门禁 | Stage Gate | 阶段切换的检查点，控制流程推进 |
| 新颖性 | Novelty | 论题相对已有文献的创新程度 |
| 重复度 | Duplication / Similarity | 论题与已有文献的相似程度 |
| 学科交叉 | Cross-Discipline | 论题跨越两个及以上学科边界 |
| 方法迁移 | Method Transfer | 将 A 领域方法应用到 B 领域 |
| 痛点突破 | Pain Point Breakthrough | 针对领域公认瓶颈提出突破方案 |
| 趋势前瞻 | Trend Foresight | 前瞻性把握领域未来发展趋势 |
| 多粒度 | Multi-Granularity | 同一论题按不同详细程度生成内容 |
| 去 AI 痕迹 | Style Normalization | 将 AI 生成文本调整为人类学术写作风格 |
| 风险评级 | Risk Level | 基于相似度与新颖性的综合风险判定 |
| 短板检测 | Shortboard Detection | 检测任一维度评分过低 |
| 降级链 | Fallback Chain | 主模型失败时的备选模型序列 |
| 缓存前缀 | Cached Prefix | DeepSeek 缓存要求的不可变前缀 |

### 0.4 阅读约定

- **规则编号**：每条规则有唯一编号，格式为 `<类别>-<三位序号>`，如 `HR-001` 表示第 1 条硬约束规则。
- **严重级别**：`error`（阻断）、`warning`（警告）、`info`（提示）。
- **作用域**：`global`（全局生效）、`paragraph_start`（仅段落开头）、`sentence_end`（仅句末）。
- **阈值符号**：`≤` 表示小于等于，`≥` 表示大于等于，`<` 表示严格小于，`>` 表示严格大于。
- **代码示例**：所有代码示例采用 Python 3.11+ 语法，遵循 PEP 8 规范。
- **配置引用**：形如 `hard_rules.yaml#title.max_length_master` 表示 `config/constraints/hard_rules.yaml` 文件中 `title.max_length_master` 字段。

---

## 1. 规则体系总览

### 1.1 规则分层架构

ThesisMiner v8.0 的规则体系采用**五层分层架构**，自底向上分别为：配置层、规则层、引擎层、门禁层、应用层。

```
┌─────────────────────────────────────────────────────────────────┐
│                      应用层（Application Layer）                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │Orchestrator│ │ Reasoner │  │  Writer  │  │  Critic  │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
└───────┼──────────────┼──────────────┼──────────────┼─────────────┘
        │              │              │              │
┌───────▼──────────────▼──────────────▼──────────────▼─────────────┐
│                    门禁层（Gate Layer）                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │info_confirm│ │creativity│ │validation│ │generation│ │deep_assist│ │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘ │
└───────┼──────────────┼──────────────┼──────────────┼─────────────┘
        │              │              │              │
┌───────▼──────────────▼──────────────▼──────────────▼─────────────┐
│                    引擎层（Engine Layer）                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ RuleEngine   │  │ NoveltyChecker│  │StyleNormalizer│            │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘            │
└─────────┼──────────────────┼──────────────────┼──────────────────┘
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼──────────────────┐
│                    规则层（Rule Layer）                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │
│  │HardRules│ │Novelty  │ │StyleAI  │ │Granular │ │Academic │     │
│  │ (20条)  │ │ (15条)  │ │ (55条)  │ │ (8条)   │ │ (100+)  │     │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘     │
└───────┼──────────┼──────────┼──────────┼──────────┼─────────────┘
        │          │          │          │          │
┌───────▼──────────▼──────────▼──────────▼──────────▼─────────────┐
│                配置层（Config Layer）                            │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │
│  │hard_rules.yaml │  │novelty_weights │  │ style_rules    │      │
│  │                │  │     .yaml      │  │     .yaml      │      │
│  └────────────────┘  └────────────────┘  └────────────────┘      │
└──────────────────────────────────────────────────────────────────┘
```

**分层职责说明**：

- **配置层**：以 YAML 文件形式存储所有规则的可调参数，支持热加载。
- **规则层**：将配置转化为可执行的规则对象，每条规则包含 ID、名称、描述、阈值、验证逻辑、错误消息、修复建议。
- **引擎层**：负责规则的加载、调度、执行、结果聚合。`RuleEngine` 是核心调度器，`NoveltyChecker` 与 `StyleNormalizer` 是领域专用引擎。
- **门禁层**：将规则执行结果与五阶段流程绑定，控制阶段推进与回退。
- **应用层**：各 Agent 在执行具体任务时调用规则引擎进行前置校验与后置校验。

### 1.2 规则分类

ThesisMiner v8.0 的规则按业务维度分为五大类，共计 200+ 条规则：

| 类别 | 编号前缀 | 规则数 | 配置文件 | 核心模块 |
|------|---------|--------|---------|---------|
| 硬约束规则 | HR | 20 | `hard_rules.yaml` | `backend/constraints/hard_rules.py` |
| 新颖性评分规则 | NS | 15 | `novelty_weights.yaml` | `backend/constraints/novelty_checker.py` |
| 去 AI 痕迹规则 | AI | 55 | `style_rules.yaml` | `backend/constraints/style_normalizer.py` |
| 多粒度生成规则 | MG | 8 | 内置于 `multi_granularity.py` | `backend/constraints/multi_granularity.py` |
| 学术规范规则 | AS | 100+ | 内置于 `academic_standards.py` | `backend/constraints/academic_standards.py` |
| 五阶段门禁规则 | SG | 5 | 内置于 `stage_gate.py` | `backend/constraints/stage_gate.py` |

按执行时机分为：

- **前置校验（Pre-validation）**：在 Agent 执行前校验输入，如标题长度、学科匹配。
- **后置校验（Post-validation）**：在 Agent 执行后校验输出，如生成内容的重复度、AI 痕迹评分。
- **门禁校验（Gate-validation）**：在阶段切换时校验，如候选数量、平均评分。

按严重级别分为：

- **Error 级**：违反则阻断流程，必须修复后才能继续。如标题长度超限、学科不匹配、时间不可行。
- **Warning 级**：违反仅标记警告，不阻断流程，但需用户确认。如导师方向对齐度低、文献数量不足。
- **Info 级**：仅作提示，不影响流程。如建议补充某类文献、建议调整某段表述。

### 1.3 规则生命周期

每条规则在 ThesisMiner 中经历以下生命周期：

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  定义    │ -> │  加载    │ -> │  执行    │ -> │  报告    │ -> │  归档    │
│ Define   │    │ Load     │    │ Execute  │    │ Report   │    │ Archive  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
  YAML 配置      RuleEngine      Agent 调用      Violation      日志/DB
  人工编写       启动时加载      运行时校验      返回结果        持久化
```

**生命周期各阶段说明**：

1. **定义（Define）**：规则在 YAML 配置文件中定义，包含 ID、名称、描述、阈值、验证逻辑、错误消息、修复建议。
2. **加载（Load）**：`RuleEngine` 在应用启动时（`lifespan` 钩子内）加载所有规则配置，构建规则对象注册表。
3. **执行（Execute）**：Agent 在执行任务前后调用规则引擎，传入待校验数据，规则引擎按校验顺序依次执行规则。
4. **报告（Report）**：规则执行后返回 `Violation` 列表，包含规则 ID、严重级别、错误消息、修复建议、字段定位。
5. **归档（Archive）**：所有违规记录写入 `rule_violations` 表与日志文件，供后续审计与分析。

### 1.4 规则编号规范

ThesisMiner v8.0 采用统一的规则编号规范，格式为 `<类别前缀>-<三位序号>`：

| 类别前缀 | 含义 | 示例 |
|---------|------|------|
| HR | Hard Rule（硬约束） | HR-001 表示第 1 条硬约束规则 |
| NS | Novelty Scoring（新颖性评分） | NS-001 表示第 1 条新颖性评分规则 |
| AI | AI Trace（去 AI 痕迹） | AI-001 表示第 1 条去 AI 痕迹规则 |
| MG | Multi-Granularity（多粒度） | MG-001 表示第 1 条多粒度规则 |
| AS | Academic Standards（学术规范） | AS-001 表示第 1 条学术规范规则 |
| SG | Stage Gate（阶段门禁） | SG-001 表示第 1 条阶段门禁规则 |

编号一旦分配，**永不复用**。规则废弃后，编号保留，配置中标记 `deprecated: true`。新增规则使用下一个可用序号。

---

## 2. 硬约束规则（Hard Rules）

硬约束规则是 ThesisMiner 中**必须满足**的规则，违反 `error` 级硬约束会阻断流程，违反 `warning` 级硬约束会标记警告。硬约束规则配置于 `config/constraints/hard_rules.yaml`，由 `backend/constraints/hard_rules.py` 实现。

### 2.1 标题长度规则

#### HR-001：标题最大长度（硕士）

| 属性 | 值 |
|------|------|
| 规则 ID | HR-001 |
| 规则名称 | 标题最大长度（硕士） |
| 类别 | 硬约束 - 标题 |
| 严重级别 | error |
| 配置键 | `hard_rules.yaml#title.max_length_master` |
| 阈值 | 25 字 |
| 适用学位 | master |
| 作用域 | 标题字段 |

**描述**：硕士论题标题长度不得超过 25 字（含标点）。超过此长度会导致标题冗长、核心不突出，不符合硕士论文规范。

**验证逻辑**：

```python
def validate_title_length_master(title: str) -> list[HardRuleViolation]:
    """验证硕士标题最大长度"""
    violations = []
    max_len = 25  # hard_rules.yaml#title.max_length_master
    if len(title) > max_len:
        violations.append(HardRuleViolation(
            rule="HR-001",
            severity="error",
            message=f"标题长度{len(title)}超过限制{max_len}字（硕士）",
            field="title",
        ))
    return violations
```

**错误消息**：

```
标题长度{actual_length}超过限制{max_length}字（硕士）
```

示例：`标题长度32超过限制25字（硕士）`

**修复建议**：

- 采用 `extract_core_noun_phrase` 策略，通过依存句法分析截取核心名词短语。
- 删除冗余修饰词（如"基于...的"、"关于...的"）。
- 将长定语后置为副标题。

**自动修复示例**：

| 原标题 | 修复后标题 | 修复策略 |
|--------|-----------|---------|
| 基于深度学习的医学影像分割方法的研究与应用 | 深度学习医学影像分割方法 | extract_core_noun_phrase |
| 关于大语言模型在代码生成任务中的性能评估研究 | 大语言模型代码生成性能评估 | extract_core_noun_phrase |

#### HR-002：标题最大长度（博士）

| 属性 | 值 |
|------|------|
| 规则 ID | HR-002 |
| 规则名称 | 标题最大长度（博士） |
| 类别 | 硬约束 - 标题 |
| 严重级别 | error |
| 配置键 | `hard_rules.yaml#title.max_length_doctor` |
| 阈值 | 30 字 |
| 适用学位 | doctor |

**描述**：博士论题标题长度不得超过 30 字。博士论文研究深度更高，标题可适当延长，但仍需精炼。

**验证逻辑**：与 HR-001 类似，仅阈值不同（30 字）。

**错误消息**：`标题长度{actual_length}超过限制{max_length}字（博士）`

#### HR-003：标题最小长度

| 属性 | 值 |
|------|------|
| 规则 ID | HR-003 |
| 规则名称 | 标题最小长度 |
| 类别 | 硬约束 - 标题 |
| 严重级别 | warning |
| 配置键 | `hard_rules.yaml#title.min_length` |
| 阈值 | 8 字 |

**描述**：标题长度不得少于 8 字。过短的标题通常信息量不足，无法准确表达研究内容。

**验证逻辑**：

```python
if len(title) < 8:
    violations.append(HardRuleViolation(
        rule="HR-003",
        severity="warning",
        message=f"标题长度{len(title)}过短，建议≥8字",
        field="title",
    ))
```

**修复建议**：补充研究对象、方法或应用场景，使标题信息更完整。

### 2.2 标题动词前置规则

#### HR-004：标题禁用动词开头

| 属性 | 值 |
|------|------|
| 规则 ID | HR-004 |
| 规则名称 | 标题禁用动词开头 |
| 类别 | 硬约束 - 标题 |
| 严重级别 | error |
| 配置键 | `hard_rules.yaml#title.forbidden_verbs` |

**描述**：标题不得以动词开头。学术标题应为名词性短语，动词开头会导致标题口语化、不规范。

**禁用动词列表**（共 12 个）：

| 序号 | 禁用动词 | 序号 | 禁用动词 | 序号 | 禁用动词 |
|------|---------|------|---------|------|---------|
| 1 | 研究 | 5 | 实现 | 9 | 优化 |
| 2 | 分析 | 6 | 构建 | 10 | 改进 |
| 3 | 探讨 | 7 | 设计 | 11 | 评估 |
| 4 | 调查 | 8 | 开发 | 12 | 验证 |

**验证逻辑**：

```python
FORBIDDEN_VERBS = ["研究", "分析", "探讨", "调查", "实现", "构建",
                   "设计", "开发", "优化", "改进", "评估", "验证"]

def validate_title_verb_prefix(title: str) -> list[HardRuleViolation]:
    violations = []
    for verb in FORBIDDEN_VERBS:
        if title.startswith(verb):
            violations.append(HardRuleViolation(
                rule="HR-004",
                severity="error",
                message=f"标题不应以动词'{verb}'开头，应改为名词性短语",
                field="title",
            ))
            break
    return violations
```

**错误消息**：`标题不应以动词'{verb}'开头，应改为名词性短语`

**修复建议**：采用 `convert_to_noun_phrase` 策略，将动词前置转为名词性短语。

**修复示例**：

| 原标题 | 修复后标题 | 修复策略 |
|--------|-----------|---------|
| 研究深度学习在医学影像中的应用 | 深度学习医学影像应用研究 | convert_to_noun_phrase |
| 分析社交网络中的信息传播机制 | 社交网络信息传播机制分析 | convert_to_noun_phrase |
| 设计基于图神经网络推荐系统 | 基于图神经网络的推荐系统设计 | convert_to_noun_phrase |

### 2.3 标题禁止模式规则

#### HR-005：标题禁止模式匹配

| 属性 | 值 |
|------|------|
| 规则 ID | HR-005 |
| 规则名称 | 标题禁止模式匹配 |
| 类别 | 硬约束 - 标题 |
| 严重级别 | error |
| 配置键 | `hard_rules.yaml#title.forbidden_patterns` |

**描述**：标题不得匹配预设的禁止正则模式。这些模式通常是过于宽泛、缺乏创新的标题套路。

**禁止模式列表**（共 9 个）：

| 序号 | 正则模式 | 匹配示例 | 禁止原因 |
|------|---------|---------|---------|
| 1 | `基于.*的研究` | 基于深度学习的研究 | 太通用 |
| 2 | `基于.*的分析` | 基于大数据的分析 | 太通用 |
| 3 | `基于.*的探讨` | 基于图神经网络的探讨 | 太通用 |
| 4 | `基于.*的应用研究` | 基于Transformer的应用研究 | 太通用 |
| 5 | `基于.*的设计` | 基于注意力机制的设计 | 太通用 |
| 6 | `基于.*的实现` | 基于微服务架构的实现 | 太通用 |
| 7 | `.*的应用研究` | 大语言模型的应用研究 | 太通用 |
| 8 | `.*的初步研究` | 多模态学习的初步研究 | 显得不够深入 |
| 9 | `.*的探索性研究` | 联邦学习的探索性研究 | 显得不够深入 |

**验证逻辑**：

```python
import re

FORBIDDEN_PATTERNS = [
    r"基于.*的研究",
    r"基于.*的分析",
    r"基于.*的探讨",
    r"基于.*的应用研究",
    r"基于.*的设计",
    r"基于.*的实现",
    r".*的应用研究",
    r".*的初步研究",
    r".*的探索性研究",
]

def validate_title_pattern(title: str) -> list[HardRuleViolation]:
    violations = []
    for pattern in FORBIDDEN_PATTERNS:
        if re.match(pattern, title):
            violations.append(HardRuleViolation(
                rule="HR-005",
                severity="error",
                message=f"标题匹配禁止模式'{pattern}'，过于宽泛",
                field="title",
            ))
            break
    return violations
```

**错误消息**：`标题匹配禁止模式'{pattern}'，过于宽泛`

**修复建议**：采用 `reconstruct_noun_phrase` 策略，重组为突出核心贡献的名词短语。

**修复示例**：

| 原标题 | 修复后标题 | 修复策略 |
|--------|-----------|---------|
| 基于深度学习的研究 | 深度学习驱动的跨模态对齐机制 | reconstruct_noun_phrase |
| 基于图神经网络的应用研究 | 图神经网络在分子性质预测中的稀疏注意力机制 | reconstruct_noun_phrase |
| 联邦学习的探索性研究 | 异构联邦学习中的梯度混淆攻击防御 | reconstruct_noun_phrase |

### 2.4 学科匹配规则

#### HR-006：学科匹配检查

| 属性 | 值 |
|------|------|
| 规则 ID | HR-006 |
| 规则名称 | 学科匹配检查 |
| 类别 | 硬约束 - 学科 |
| 严重级别 | error |
| 配置键 | `hard_rules.yaml#discipline.require_match` |

**描述**：论题必须与用户指定的学科领域匹配。学科匹配通过预定义的学科关系映射表判断，论题关键词需落入目标学科或其相关学科集合。

**学科关系映射**（部分示例）：

```yaml
discipline:
  relations:
    计算机科学:
      - 计算机科学
      - 人工智能
      - 软件工程
      - 数据科学
      - 信息工程
    人工智能:
      - 人工智能
      - 计算机科学
      - 机器学习
      - 深度学习
    医学:
      - 医学
      - 临床医学
      - 生物医学
      - 医疗信息学
    教育学:
      - 教育学
      - 教育技术
      - 心理学
      - 课程与教学论
```

**验证逻辑**：

```python
def validate_discipline_match(topic: str, discipline: str) -> list[HardRuleViolation]:
    violations = []
    if not discipline:
        violations.append(HardRuleViolation(
            rule="HR-006",
            severity="warning",
            message="未指定学科领域",
            field="discipline",
        ))
        return violations

    relations = DISCIPLINE_RELATIONS.get(discipline, [discipline])
    topic_keywords = extract_keywords(topic)
    matched = any(kw in relations for kw in topic_keywords)

    if not matched:
        violations.append(HardRuleViolation(
            rule="HR-006",
            severity="error",
            message=f"论题关键词{topic_keywords}与学科'{discipline}'不匹配",
            field="discipline",
        ))
    return violations
```

**错误消息**：`论题关键词{keywords}与学科'{discipline}'不匹配`

**修复建议**：

- 调整论题关键词，使其落入目标学科范围。
- 若论题确属交叉学科，在信息确权阶段标注交叉学科。

### 2.5 导师方向对齐规则

#### HR-007：导师方向对齐

| 属性 | 值 |
|------|------|
| 规则 ID | HR-007 |
| 规则名称 | 导师方向对齐 |
| 类别 | 硬约束 - 导师 |
| 严重级别 | warning |
| 配置键 | `hard_rules.yaml#advisor.require_alignment`、`hard_rules.yaml#advisor.min_alignment_score` |
| 阈值 | 最小对齐度分数 0.3 |

**描述**：论题应与导师研究方向对齐，对齐度分数不得低于 0.3。对齐度通过关键词重叠法计算。

**对齐度计算方法**：

```python
def calculate_alignment(topic: str, advisor_direction: str) -> float:
    """计算论题与导师方向的对齐度（关键词重叠法）"""
    if not advisor_direction or not topic:
        return 0.0

    advisor_keywords = set(jieba.cut(advisor_direction))
    topic_keywords = set(jieba.cut(topic))

    # 去除停用词
    advisor_keywords = advisor_keywords - STOPWORDS
    topic_keywords = topic_keywords - STOPWORDS

    if not advisor_keywords or not topic_keywords:
        return 0.0

    overlap = advisor_keywords & topic_keywords
    union = advisor_keywords | topic_keywords

    # Jaccard 相似度
    return len(overlap) / len(union)
```

**验证逻辑**：

```python
def validate_advisor_alignment(topic: str, advisor_direction: str) -> list[HardRuleViolation]:
    violations = []
    min_score = 0.3  # hard_rules.yaml#advisor.min_alignment_score

    score = calculate_alignment(topic, advisor_direction)
    if score < min_score:
        violations.append(HardRuleViolation(
            rule="HR-007",
            severity="warning",
            message=f"导师方向对齐度{score:.2f}低于阈值{min_score}",
            field="advisor",
        ))
    return violations
```

**错误消息**：`导师方向对齐度{score}低于阈值{min_score}`

**修复建议**：

- 在论题中融入导师研究方向的关键词。
- 与导师沟通确认论题方向的合理性。
- 若确需跨方向，在信息确权阶段说明理由。

### 2.6 时间可行性规则

#### HR-008：时间可行性（硕士）

| 属性 | 值 |
|------|------|
| 规则 ID | HR-008 |
| 规则名称 | 时间可行性（硕士） |
| 类别 | 硬约束 - 时间 |
| 严重级别 | error |
| 配置键 | `hard_rules.yaml#calendar.master_max_years`、`hard_rules.yaml#calendar.master_max_months` |
| 阈值 | 最大 1 年（12 个月） |

**描述**：硕士论题的研究时间规划不得超过 1 年（12 个月）。超过此时间通常意味着论题工作量过大或时间管理不合理。

**验证逻辑**：

```python
def validate_timeline_master(timeline: dict) -> list[HardRuleViolation]:
    violations = []
    max_months = 12  # hard_rules.yaml#calendar.master_max_months

    total_months = timeline.get("total_months", 0)
    if total_months > max_months:
        violations.append(HardRuleViolation(
            rule="HR-008",
            severity="error",
            message=f"总时长{total_months}个月超过硕士最大年限12个月",
            field="timeline",
        ))
    return violations
```

**错误消息**：`总时长{total_months}个月超过硕士最大年限12个月`

**修复建议**：采用 `inject_parallel_strategy` 策略，注入分阶段并行执行策略，压缩总时长。

**修复示例**：

| 原时间规划 | 修复后规划 | 修复策略 |
|-----------|-----------|---------|
| 文献综述3月+实验6月+写作3月=12月 | 文献综述2月+实验4月（并行写作1月）+写作3月=9月 | inject_parallel_strategy |

#### HR-009：时间可行性（博士）

| 属性 | 值 |
|------|------|
| 规则 ID | HR-009 |
| 规则名称 | 时间可行性（博士） |
| 类别 | 硬约束 - 时间 |
| 严重级别 | error |
| 阈值 | 最大 2 年（24 个月） |

**描述**：博士论题的研究时间规划不得超过 2 年（24 个月）。

### 2.7 文献基线规则

#### HR-010：文献数量基线（硕士）

| 属性 | 值 |
|------|------|
| 规则 ID | HR-010 |
| 规则名称 | 文献数量基线（硕士） |
| 类别 | 硬约束 - 文献 |
| 严重级别 | warning |
| 配置键 | `hard_rules.yaml#literature.master_min_count` |
| 阈值 | 最少 30 篇 |

**描述**：硕士论文参考文献数量不得少于 30 篇。文献数量不足会导致综述深度不够，论题立足不稳。

**推荐数据库**：

| 数据库 | 类型 | 适用学科 |
|--------|------|---------|
| CNKI | 中文综合 | 全学科 |
| WanFang | 中文综合 | 全学科 |
| VIP | 中文综合 | 全学科 |
| Web of Science | 英文综合 | 全学科 |
| Scopus | 英文综合 | 全学科 |
| IEEE Xplore | 英文专业 | 工程/计算机 |
| ACM Digital Library | 英文专业 | 计算机 |
| PubMed | 英文专业 | 医学/生物 |
| arXiv | 预印本 | 物理/计算机/数学 |
| Semantic Scholar | 英文综合 | 全学科 |

**验证逻辑**：

```python
def validate_literature_count_master(count: int) -> list[HardRuleViolation]:
    violations = []
    min_count = 30  # hard_rules.yaml#literature.master_min_count

    if count < min_count:
        violations.append(HardRuleViolation(
            rule="HR-010",
            severity="warning",
            message=f"文献数量{count}少于硕士最低要求{min_count}篇",
            field="literature",
        ))
    return violations
```

**错误消息**：`文献数量{count}少于硕士最低要求{min_count}篇`

**修复建议**：采用 `supplement_search_suggestions` 策略，补充子方向检索词与数据库建议。

#### HR-011：文献数量基线（博士）

| 属性 | 值 |
|------|------|
| 规则 ID | HR-011 |
| 规则名称 | 文献数量基线（博士） |
| 类别 | 硬约束 - 文献 |
| 严重级别 | warning |
| 阈值 | 最少 50 篇 |

### 2.8 重复度阈值规则

#### HR-012：重复度阈值

| 属性 | 值 |
|------|------|
| 规则 ID | HR-012 |
| 规则名称 | 重复度阈值 |
| 类别 | 硬约束 - 重复度 |
| 严重级别 | error |
| 配置键 | `hard_rules.yaml#duplication.max_similarity`、`hard_rules.yaml#duplication.min_novelty_score` |
| 阈值 | 最大相似度 0.3，最小新颖性评分 60 |

**描述**：论题与已有文献的相似度不得超过 0.3，新颖性评分不得低于 60。超过相似度阈值会触发阻断，要求调整差异化方向。

**风险评级阈值**：

| 风险级别 | 相似度范围 | 新颖性范围 | 处理策略 | 标签 |
|---------|-----------|-----------|---------|------|
| 低风险 | < 0.5 | ≥ 70 | pass（直接通过） | 低风险 |
| 中风险 | 0.5 - 0.7 | 60 - 70 | downweight（降权，要求用户确认） | 中风险 |
| 高风险 | ≥ 0.7 | < 60 | block（阻断，要求调整方向） | 高风险 |

**验证逻辑**：

```python
def validate_duplication(similarity: float, novelty_score: int) -> list[HardRuleViolation]:
    violations = []
    max_sim = 0.3  # hard_rules.yaml#duplication.max_similarity
    min_novelty = 60  # hard_rules.yaml#duplication.min_novelty_score

    if similarity > max_sim:
        risk = assess_risk(similarity, novelty_score)
        if risk == "high":
            violations.append(HardRuleViolation(
                rule="HR-012",
                severity="error",
                message=f"相似度{similarity:.2f}超过阈值{max_sim}，风险级别：高风险，需调整差异化方向",
                field="duplication",
            ))
        elif risk == "medium":
            violations.append(HardRuleViolation(
                rule="HR-012",
                severity="warning",
                message=f"相似度{similarity:.2f}接近阈值{max_sim}，风险级别：中风险，需用户确认",
                field="duplication",
            ))

    if novelty_score < min_novelty:
        violations.append(HardRuleViolation(
            rule="HR-012",
            severity="error",
            message=f"新颖性评分{novelty_score}低于阈值{min_novelty}",
            field="novelty",
        ))
    return violations
```

**错误消息**：

- 高风险：`相似度{similarity}超过阈值{max_sim}，风险级别：高风险，需调整差异化方向`
- 中风险：`相似度{similarity}接近阈值{max_sim}，风险级别：中风险，需用户确认`
- 新颖性不足：`新颖性评分{novelty_score}低于阈值{min_novelty}`

**修复建议**：

- 高风险：回退至创意阶段（creativity），重新生成候选论题，调整差异化方向。
- 中风险：要求用户确认差异化方向，或在论题中强化创新点表述。
- 新颖性不足：参照新颖性评分规则（第 3 章）的短板维度，针对性提升。

### 2.9 逻辑自洽规则

#### HR-013：研究内容与研究目标重合度

| 属性 | 值 |
|------|------|
| 规则 ID | HR-013 |
| 规则名称 | 研究内容与研究目标重合度 |
| 类别 | 硬约束 - 逻辑 |
| 严重级别 | warning |
| 配置键 | `hard_rules.yaml#logic.max_overlap` |
| 阈值 | 最大重合度 0.7 |

**描述**：研究内容与研究目标的重合度不得超过 0.7。重合度过高意味着研究内容只是研究目标的复述，缺乏具体展开。

**验证逻辑**：

```python
def validate_logic_consistency(content: str, objective: str) -> list[HardRuleViolation]:
    violations = []
    max_overlap = 0.7  # hard_rules.yaml#logic.max_overlap

    overlap = jaccard_similarity(content, objective)
    if overlap > max_overlap:
        violations.append(HardRuleViolation(
            rule="HR-013",
            severity="warning",
            message=f"研究内容与研究目标重合度{overlap:.2f}超过阈值{max_overlap}",
            field="logic",
        ))
    return violations
```

**错误消息**：`研究内容与研究目标重合度{overlap}超过阈值{max_overlap}`

**修复建议**：采用 `mark_warning` 策略，标记 WARNING，提示用户细化研究内容，使其与研究目标形成"目标-手段"的层次关系。

### 2.10 校验顺序

硬约束规则按以下顺序依次校验，前序规则未通过时，后续规则不再执行（短路求值）：

```yaml
validation_order:
  - title_length          # HR-001/HR-002/HR-003
  - title_verb_prefix     # HR-004
  - title_pattern         # HR-005
  - discipline_match      # HR-006
  - advisor_alignment     # HR-007
  - time_feasibility      # HR-008/HR-009
  - literature_baseline   # HR-010/HR-011
  - duplication_threshold # HR-012
  - logic_consistency     # HR-013
```

**校验顺序设计原则**：

1. **先校验格式，后校验语义**：标题长度、动词前置、模式匹配等格式校验优先。
2. **先校验硬性，后校验软性**：学科匹配、时间可行性等硬性校验优先于导师对齐、文献基线等软性校验。
3. **先校验输入，后校验输出**：标题、学科、导师等输入校验优先于重复度、逻辑等输出校验。

### 2.11 严重级别汇总

```yaml
severity:
  error:                     # 严重错误，阻断流程
    - title_length           # HR-001/HR-002
    - title_verb_prefix      # HR-004
    - title_pattern          # HR-005
    - discipline_match       # HR-006
    - time_feasibility       # HR-008/HR-009
    - duplication_threshold  # HR-012
  warning:                   # 警告，标记但不阻断
    - advisor_alignment      # HR-007
    - literature_baseline    # HR-010/HR-011
    - logic_consistency      # HR-013
```

### 2.12 全局开关

```yaml
global:
  enabled: true              # 全局启用硬约束
  strict_mode: false         # 严格模式（warning 也阻断）
  log_violations: true       # 记录违规日志
```

**严格模式说明**：

- `strict_mode: false`（默认）：`warning` 级违规仅标记，不阻断流程。
- `strict_mode: true`：`warning` 级违规也阻断流程，适用于高质量要求的场景（如博士论文）。

---

## 3. 新颖性评分规则（Novelty Scoring）

新颖性评分规则是 ThesisMiner v8.0 的核心创新之一，将原本单一的相似度阈值扩展为**四维加权评分**。配置于 `config/constraints/novelty_weights.yaml`，由 `backend/constraints/novelty_checker.py` 实现。

### 3.1 四维创意引擎总览

ThesisMiner v8.0 采用**四维创意引擎**对候选论题进行多维度新颖性量化评估，四个维度及其权重如下：

| 维度 | 英文 | 权重 | 评估重点 |
|------|------|------|---------|
| 学科交叉 | cross_discipline | 30% | 论题是否跨越两个及以上学科边界 |
| 方法迁移 | method_transfer | 25% | 是否将 A 领域成熟方法迁移到 B 领域 |
| 痛点突破 | pain_point_breakthrough | 25% | 是否针对领域公认痛点提出突破方案 |
| 趋势前瞻 | trend_foresight | 20% | 是否前瞻性把握领域未来 2-3 年趋势 |

**权重设计依据**：

- **学科交叉 30%**：交叉创新是产生原创性成果的高概率路径，权重最高。
- **方法迁移 25%**：方法迁移是工程落地的高效路径，权重次高。
- **痛点突破 25%**：痛点突破是学术价值的核心体现，与方法迁移并列。
- **趋势前瞻 20%**：趋势前瞻影响论题的长期价值，权重适中。

**评分流程**：

```
┌──────────────┐
│ 候选论题输入  │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│           四维并行评分                    │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐│
│  │学科交叉│ │方法迁移│ │痛点突破│ │趋势前瞻││
│  │ 0-100  │ │ 0-100  │ │ 0-100  │ │ 0-100  ││
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘│
└──────┼──────────┼──────────┼──────────┼─────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
┌──────────────────────────────────────────┐
│  加权求和：total = 0.3*d1 + 0.25*d2 +    │
│           0.25*d3 + 0.2*d4               │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  相似度惩罚：final = total * (1 - max(0, │
│              similarity - 0.2))           │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  短板检测：任一维度 < 40 则标记短板       │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  风险评级：低/中/高                        │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  候选择优：取前 K 名进入校验阶段          │
└──────────────────────────────────────────┘
```

### 3.2 学科交叉维度（30%）

#### NS-001：学科交叉评分

| 属性 | 值 |
|------|------|
| 规则 ID | NS-001 |
| 规则名称 | 学科交叉评分 |
| 类别 | 新颖性评分 - 学科交叉 |
| 权重 | 30% |
| 配置键 | `novelty_weights.yaml#weights.cross_discipline` |

**描述**：评估论题是否跨越两个及以上学科边界，产生交叉创新。

**评分细则**（0-100）：

| 分数区间 | 描述 | 示例 |
|---------|------|------|
| 90-100 | 跨越 3 个及以上学科，形成全新交叉领域 | 将神经科学、计算拓扑学、教育心理学三者融合研究学习认知机制 |
| 70-89 | 跨越 2 个学科，在交叉点上有明确创新贡献 | 将图神经网络迁移到蛋白质结构预测 |
| 50-69 | 跨越 2 个学科，但交叉点创新性一般 | 将传统统计方法用于新媒体传播分析 |
| 30-49 | 学科边界模糊，交叉意图不明确 | 仅在文献综述中提及多学科背景 |
| 0-29 | 单一学科内部研究，无交叉 | 纯算法优化类论题 |

**加分项**：

| 加分项 | 分值 | 条件 |
|--------|------|------|
| rare_combination | +10 | 罕见学科组合（如艺术+量子计算） |
| methodological_bridge | +8 | 提供方法论桥梁（如将 A 学科实验范式引入 B） |
| theoretical_fusion | +12 | 理论层面深度融合（非简单借用） |

**扣分项**：

| 扣分项 | 分值 | 条件 |
|--------|------|------|
| superficial_mention | -15 | 仅在引言提及交叉，正文无落实 |
| forced_combination | -20 | 强行拼凑无明显逻辑关联 |
| overdone_combination | -10 | 交叉过多导致焦点涣散（>4 个学科） |

**评分示例**：

| 论题 | 学科数 | 基础分 | 加分 | 扣分 | 最终分 |
|------|--------|--------|------|------|--------|
| 神经科学+计算拓扑学+教育心理学融合研究学习认知 | 3 | 95 | +12（theoretical_fusion） | 0 | 100 |
| 图神经网络迁移到蛋白质结构预测 | 2 | 80 | +8（methodological_bridge） | 0 | 88 |
| 传统统计方法用于新媒体传播分析 | 2 | 60 | 0 | 0 | 60 |
| 仅在综述中提及多学科背景 | 1 | 40 | 0 | -15（superficial_mention） | 25 |
| 纯算法优化 | 1 | 20 | 0 | 0 | 20 |

### 3.3 方法迁移维度（25%）

#### NS-002：方法迁移评分

| 属性 | 值 |
|------|------|
| 规则 ID | NS-002 |
| 规则名称 | 方法迁移评分 |
| 类别 | 新颖性评分 - 方法迁移 |
| 权重 | 25% |
| 配置键 | `novelty_weights.yaml#weights.method_transfer` |

**描述**：评估是否将 A 领域成熟方法迁移到 B 领域解决新问题。

**评分细则**（0-100）：

| 分数区间 | 描述 | 示例 |
|---------|------|------|
| 90-100 | 迁移方法与目标问题高度契合，且做了必要适配改进 | 将 Transformer 注意力机制迁移到时间序列异常检测并改进位置编码 |
| 70-89 | 方法迁移合理，有适配性调整但创新有限 | 将 BERT 预训练范式迁移到代码理解任务 |
| 50-69 | 方法迁移可行但适配不足，存在明显水土不服 | 直接套用 NLP 方法到表格数据未做模态适配 |
| 30-49 | 方法迁移牵强，迁移后效果存疑 | 将图像卷积直接用于一维文本特征 |
| 0-29 | 无方法迁移，或迁移后完全失效 | 纯领域内方法应用 |

**加分项**：

| 加分项 | 分值 | 条件 |
|--------|------|------|
| novel_adaptation | +10 | 迁移过程中有创新性适配改造 |
| cross_modal | +12 | 跨模态迁移（视觉→文本、图→序列等） |
| efficiency_gain | +8 | 迁移后带来显著效率提升 |

**扣分项**：

| 扣分项 | 分值 | 条件 |
|--------|------|------|
| blind_copy | -25 | 无任何适配的机械搬运 |
| domain_mismatch | -20 | 方法与目标领域假设严重冲突 |
| redundant_transfer | -10 | 目标领域已有等效方法，迁移无增量价值 |

### 3.4 痛点突破维度（25%）

#### NS-003：痛点突破评分

| 属性 | 值 |
|------|------|
| 规则 ID | NS-003 |
| 规则名称 | 痛点突破评分 |
| 类别 | 新颖性评分 - 痛点突破 |
| 权重 | 25% |
| 配置键 | `novelty_weights.yaml#weights.pain_point_breakthrough` |

**描述**：评估是否针对领域内公认痛点/瓶颈提出有效突破方案。

**评分细则**（0-100）：

| 分数区间 | 描述 | 示例 |
|---------|------|------|
| 90-100 | 直击公认核心痛点，提出有理论支撑的突破方案 | 针对大模型长上下文注意力计算复杂度二次增长提出线性化方案 |
| 70-89 | 针对明确痛点提出改进，有实验验证有效性 | 针对小样本学习过拟合问题提出元学习正则化 |
| 50-69 | 触及痛点但突破力度有限，属渐进式改进 | 对已有方法做超参调优与轻量改进 |
| 30-49 | 痛点定位模糊，改进方向与痛点关联弱 | 泛泛提及"效率问题"但未具体化 |
| 0-29 | 未识别痛点，或痛点为伪需求 | 解决领域内已基本解决的问题 |

**加分项**：

| 加分项 | 分值 | 条件 |
|--------|------|------|
| long_standing | +10 | 针对长期未解难题（>5 年） |
| measurable_metric | +8 | 有可量化改进指标（如 F1 提升 X%） |
| theoretical_root | +12 | 从理论根因出发而非经验修补 |

**扣分项**：

| 扣分项 | 分值 | 条件 |
|--------|------|------|
| pseudo_pain | -30 | 伪痛点（领域内已基本解决） |
| incremental_only | -15 | 纯增量改进无实质突破 |
| unsupported_claim | -20 | 突破声明无理论或实验支撑 |

### 3.5 趋势前瞻维度（20%）

#### NS-004：趋势前瞻评分

| 属性 | 值 |
|------|------|
| 规则 ID | NS-004 |
| 规则名称 | 趋势前瞻评分 |
| 类别 | 新颖性评分 - 趋势前瞻 |
| 权重 | 20% |
| 配置键 | `novelty_weights.yaml#weights.trend_foresight` |

**描述**：评估论题是否前瞻性把握领域未来 2-3 年发展趋势。

**评分细则**（0-100）：

| 分数区间 | 描述 | 示例 |
|---------|------|------|
| 90-100 | 前瞻性强，紧扣领域未来 2-3 年关键走向，有文献佐证 | 在 2026 年预判多模态具身智能将成为下一代 AI 核心范式 |
| 70-89 | 趋势把握准确，与近期热点演进方向一致 | 围绕大模型推理能力增强开展研究 |
| 50-69 | 趋势判断一般，属当前主流方向的延伸 | 在已有 RAG 框架上做工程优化 |
| 30-49 | 趋势判断滞后，研究的是 1-2 年前的热点 | 2026 年仍以 BERT 微调为主线 |
| 0-29 | 无前瞻性，方向过时或与趋势无关 | 研究已被新范式取代的旧方法 |

**加分项**：

| 加分项 | 分值 | 条件 |
|--------|------|------|
| emerging_field | +10 | 切入新兴子领域（文献量年增 >50%） |
| paradigm_shift | +15 | 预判范式转换 |
| policy_aligned | +8 | 与国家/行业战略方向契合 |

**扣分项**：

| 扣分项 | 分值 | 条件 |
|--------|------|------|
| outdated | -25 | 方向明显过时 |
| overhyped | -15 | 追逐已过热泡沫（文献增速放缓） |
| speculative | -20 | 过度 speculative 无任何文献支撑 |

### 3.6 综合评分计算

#### NS-005：综合评分公式

| 属性 | 值 |
|------|------|
| 规则 ID | NS-005 |
| 规则名称 | 综合评分公式 |
| 类别 | 新颖性评分 - 综合 |
| 配置键 | `novelty_weights.yaml#scoring.formula` |

**加权求和公式**：

```
total = w1*d1 + w2*d2 + w3*d3 + w4*d4
      = 0.30*cross_discipline + 0.25*method_transfer
        + 0.25*pain_point_breakthrough + 0.20*trend_foresight
```

其中各维度评分归一化至 0-100，加权后总分仍为 0-100。

**相似度惩罚公式**：

```
final = total * (1 - max(0, similarity - 0.2))
```

相似度 > 0.2 开始惩罚，相似度 0.3 时惩罚系数 0.1，相似度 0.5 时惩罚系数 0.3。

**计算示例**：

| 维度 | 评分 | 权重 | 加权分 |
|------|------|------|--------|
| 学科交叉 | 85 | 0.30 | 25.5 |
| 方法迁移 | 70 | 0.25 | 17.5 |
| 痛点突破 | 80 | 0.25 | 20.0 |
| 趋势前瞻 | 75 | 0.20 | 15.0 |
| **总分** | | | **78.0** |
| 相似度 | 0.25 | 惩罚系数 | 0.05 |
| **最终分** | | | **78.0 * 0.95 = 74.1** |

#### NS-006：短板检测

| 属性 | 值 |
|------|------|
| 规则 ID | NS-006 |
| 规则名称 | 短板检测 |
| 类别 | 新颖性评分 - 短板 |
| 配置键 | `novelty_weights.yaml#thresholds.dimension_score` |
| 阈值 | 单维度最低分 40 |

**描述**：任一维度评分低于 40 则标记短板，提示用户针对性提升。

**验证逻辑**：

```python
def detect_shortboards(scores: dict) -> list[str]:
    shortboards = []
    threshold = 40  # novelty_weights.yaml#thresholds.dimension_score
    for dim, score in scores.items():
        if score < threshold:
            shortboards.append(dim)
    return shortboards
```

### 3.7 风险评级与处理策略

#### NS-007：风险评级

| 属性 | 值 |
|------|------|
| 规则 ID | NS-007 |
| 规则名称 | 风险评级 |
| 类别 | 新颖性评分 - 风险 |
| 配置键 | `novelty_weights.yaml#risk_levels` |

**风险评级阈值**：

| 风险级别 | 相似度上限 | 新颖性下限 | 处理策略 | 标签 |
|---------|-----------|-----------|---------|------|
| low | 0.3 | 70 | pass（直接通过） | 低风险 |
| medium | 0.5 | 60 | downweight（降权，要求用户确认） | 中风险 |
| high | 1.0 | 0 | block（阻断，要求调整方向） | 高风险 |

**评级逻辑**：

```python
def assess_risk(similarity: float, novelty: int) -> str:
    if similarity <= 0.3 and novelty >= 70:
        return "low"
    elif similarity <= 0.5 and novelty >= 60:
        return "medium"
    else:
        return "high"
```

#### NS-008：候选择优策略

| 属性 | 值 |
|------|------|
| 规则 ID | NS-008 |
| 规则名称 | 候选择优策略 |
| 类别 | 新颖性评分 - 择优 |
| 配置键 | `novelty_weights.yaml#selection` |

**策略**：生成 N 个候选后取前 K 名（top_k）。

**参数**：

| 参数 | 值 | 说明 |
|------|------|------|
| min_candidates | 3 | 最少生成候选数 |
| top_k_pass | 1 | 取前 K 名进入校验阶段 |

**同分处理（tiebreakers）**：

当多个候选总分相同时，按以下优先级排序：

1. 学科交叉分高者优先
2. 痛点突破分高者优先
3. 趋势前瞻分高者优先
4. 方法迁移分高者优先

#### NS-009：与硬约束的联动

| 属性 | 值 |
|------|------|
| 规则 ID | NS-009 |
| 规则名称 | 与硬约束的联动 |
| 类别 | 新颖性评分 - 联动 |
| 配置键 | `novelty_weights.yaml#hard_rule_linkage` |

**联动规则**：

| 条件 | 触发的硬约束 | 处理动作 |
|------|------------|---------|
| 新颖性评分 < 60 | HR-012（重复度阈值） | 回退至创意阶段重新生成 |
| 相似度 > 0.3 | HR-012（重复度阈值） | 阻断，要求调整方向 |
| 评分不达标 | - | retry_creativity_stage |
| 最大重试次数 | - | 3 次 |

---

## 4. 去 AI 痕迹规则（Style Normalization）

去 AI 痕迹规则是 ThesisMiner v8.0 的特色功能，用于将 AI 生成文本调整为符合人类学术写作风格。配置于 `config/constraints/style_rules.yaml`，由 `backend/constraints/style_normalizer.py` 实现，共内置 55 条替换规则。

### 4.1 句式结构约束

#### AI-001：句长分布约束

| 属性 | 值 |
|------|------|
| 规则 ID | AI-001 |
| 规则名称 | 句长分布约束 |
| 类别 | 去 AI 痕迹 - 句式 |
| 配置键 | `style_rules.yaml#sentence_structure.length_distribution` |

**目标**：使句长分布接近人类学术写作的句长分布。

**参数**：

| 参数 | 值 | 说明 |
|------|------|------|
| min_chars | 8 | 最短句长（字） |
| max_chars | 80 | 最长句长（字） |
| ideal_range | [15, 60] | 理想句长区间 |
| short_sentence_ratio | 0.25 | 短句（<20字）占比上限 |
| long_sentence_ratio | 0.15 | 长句（>60字）占比上限 |

**验证逻辑**：

```python
def validate_sentence_length(text: str) -> dict:
    sentences = split_sentences(text)
    lengths = [len(s) for s in sentences]

    short_count = sum(1 for l in lengths if l < 20)
    long_count = sum(1 for l in lengths if l > 60)
    total = len(lengths)

    short_ratio = short_count / total if total > 0 else 0
    long_ratio = long_count / total if total > 0 else 0

    issues = []
    if short_ratio > 0.25:
        issues.append(f"短句占比{short_ratio:.2%}超过上限25%")
    if long_ratio > 0.15:
        issues.append(f"长句占比{long_ratio:.2%}超过上限15%")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "short_ratio": short_ratio,
        "long_ratio": long_ratio,
    }
```

#### AI-002：并列结构约束

| 属性 | 值 |
|------|------|
| 规则 ID | AI-002 |
| 规则名称 | 并列结构约束 |
| 类别 | 去 AI 痕迹 - 句式 |
| 配置键 | `style_rules.yaml#sentence_structure.parallel_structure` |

**参数**：

| 参数 | 值 | 说明 |
|------|------|------|
| max_consecutive | 3 | 连续并列项最大数（超过则拆分） |
| avoid_over_symmetry | true | 避免过度对仗（AI 常见痕迹） |

#### AI-003：段落结构约束

| 属性 | 值 |
|------|------|
| 规则 ID | AI-003 |
| 规则名称 | 段落结构约束 |
| 类别 | 去 AI 痕迹 - 句式 |
| 配置键 | `style_rules.yaml#sentence_structure.paragraph_structure` |

**参数**：

| 参数 | 值 | 说明 |
|------|------|------|
| min_sentences | 3 | 段落最少句数 |
| max_sentences | 8 | 段落最多句数 |
| avoid_template_transitions | true | 避免模板化过渡句 |

### 4.2 模板词替换表

去 AI 痕迹规则的核心是**模板词替换表**，共 55 条规则，覆盖 11 大类。每条规则包含 ID、正则模式、替换文本、原因、作用域。

#### 4.2.1 篇章连接词类（R001-R008）

| ID | 模式 | 替换 | 原因 | 作用域 |
|----|------|------|------|--------|
| R001 | `首先[，,]` | （删除） | AI 高频开头模板词 | paragraph_start |
| R002 | `其次[，,]` | `进而，` | 机械序号连接 | global |
| R003 | `再次[，,]` | `在此基础上，` | 机械序号连接 | global |
| R004 | `最后[，,]` | `最终，` | 机械序号连接 | global |
| R005 | `综上所述[，,]` | `由此可见，` | AI 总结模板词 | paragraph_start |
| R006 | `总而言之[，,]` | `整体来看，` | AI 总结模板词 | paragraph_start |
| R007 | `总之[，,]` | `据此，` | AI 总结模板词 | global |
| R008 | `由此可见[，,]` | `由此，` | 过度使用痕迹 | global |

**替换示例**：

| 原文 | 替换后 |
|------|--------|
| 首先，本研究聚焦于... | 本研究聚焦于... |
| 其次，分析了... | 进而，分析了... |
| 综上所述，本研究提出... | 由此可见，本研究提出... |

#### 4.2.2 强调副词类（R009-R015）

| ID | 模式 | 替换 | 原因 |
|----|------|------|------|
| R009 | `值得注意的是[，,]` | `需要指出，` | AI 强调模板 |
| R010 | `需要指出的是[，,]` | `应当看到，` | AI 强调模板 |
| R011 | `值得一提的是[，,]` | （删除） | 冗余强调 |
| R012 | `显而易见[，,]` | `不难发现，` | AI 口吻痕迹 |
| R013 | `毋庸置疑[，,]` | `可以确定的是，` | 过度绝对化 |
| R014 | `至关重要` | `具有关键作用` | AI 高频套话 |
| R015 | `举足轻重` | `影响显著` | AI 高频套话 |

#### 4.2.3 转折让步类（R016-R019）

| ID | 模式 | 替换 | 原因 |
|----|------|------|------|
| R016 | `然而[，,]需要(注意\|指出)` | `不过，` | 冗长转折 |
| R017 | `尽管如此[，,]` | `即便如此，` | AI 转折模板 |
| R018 | `与此同时[，,]` | `同时，` | AI 连接模板 |
| R019 | `另一方面[，,]` | `此外，` | AI 连接模板 |

#### 4.2.4 因果推导类（R020-R023）

| ID | 模式 | 替换 | 原因 |
|----|------|------|------|
| R020 | `因此[，,]` | `据此，` | AI 高频因果词 |
| R021 | `由此可见一斑[，,]` | （删除） | AI 套话 |
| R022 | `这(表明\|说明\|意味着)[，,]` | `这反映出，` | AI 推导模板 |
| R023 | `进一步(说\|讲)[，,]` | `深入来看，` | AI 推导模板 |

#### 4.2.5 程度修饰类（R024-R028）

| ID | 模式 | 替换 | 原因 |
|----|------|------|------|
| R024 | `极大地` | `显著` | AI 程度副词滥用 |
| R025 | `充分地` | `充分` | 地字冗余 |
| R026 | `有效地` | `有效` | 地字冗余 |
| R027 | `显著地` | `显著` | 地字冗余 |
| R028 | `一定程度上` | `部分` | AI 模糊程度词 |

#### 4.2.6 学术套话类（R029-R034）

| ID | 模式 | 替换 | 原因 |
|----|------|------|------|
| R029 | `具有(重要\|重大)的(理论\|现实)意义` | `在理论与实践层面均有价值` | AI 套话模板 |
| R030 | `为.*提供了(新\|全新)的(视角\|思路\|方法)` | `拓展了.*的研究路径` | AI 套话模板 |
| R031 | `填补了.*的(空白\|漏洞)` | `补充了.*的不足` | AI 夸大表述 |
| R032 | `开辟了.*的新(方向\|领域)` | `拓展了.*的研究边界` | AI 夸大表述 |
| R033 | `具有广阔的(应用\|发展)前景` | `具备应用潜力` | AI 套话模板 |
| R034 | `引起了(广泛\|学术界的)关注` | `受到学界关注` | AI 套话模板 |

#### 4.2.7 列举模板类（R035-R037）

| ID | 模式 | 替换 | 原因 |
|----|------|------|------|
| R035 | `主要包括以下几个方面` | `涉及` | AI 列举模板 |
| R036 | `具体表现在以下几个方面` | `体现为` | AI 列举模板 |
| R037 | `可以从以下几个方面(展开\|分析)` | `可从以下维度切入` | AI 列举模板 |

#### 4.2.8 对仗排比类（R038-R040）

| ID | 模式 | 替换 | 原因 |
|----|------|------|------|
| R038 | `不仅.*而且.*更` | `既.*也` | 三段对仗过度工整 |
| R039 | `既.*又.*还` | `兼具.*与` | 三段排比痕迹 |
| R040 | `一方面.*另一方面.*再一方面` | `其一.*其二` | 三段并列痕迹 |

#### 4.2.9 冗余修饰类（R041-R044）

| ID | 模式 | 替换 | 原因 |
|----|------|------|------|
| R041 | `进行了(深入\|系统)的(研究\|分析\|探讨)` | `深入研究了` | 冗余结构 |
| R042 | `做出了(重要\|突出)贡献` | `贡献显著` | 冗余结构 |
| R043 | `起到了(重要\|关键)作用` | `作用关键` | 冗余结构 |
| R044 | `取得了(显著\|明显)成效` | `成效显著` | 冗余结构 |

#### 4.2.10 口语化与书面化混用（R045-R048）

| ID | 模式 | 替换 | 原因 |
|----|------|------|------|
| R045 | `其实[，,]` | `实际上，` | 口语化 |
| R046 | `当然[，,]` | `诚然，` | 口语化 |
| R047 | `毕竟[，,]` | `毕竟，` | 口语化（保留但规范化） |
| R048 | `说白了[，,]` | `简言之，` | 口语化 |

#### 4.2.11 过度绝对化表述（R049-R052）

| ID | 模式 | 替换 | 原因 |
|----|------|------|------|
| R049 | `完全(解决\|消除\|克服)` | `基本解决` | 学术写作避免绝对化 |
| R050 | `彻底(改变\|颠覆\|革新)` | `深刻影响` | 学术写作避免绝对化 |
| R051 | `唯一(方法\|途径\|方案)` | `主要方法之一` | 学术写作避免绝对化 |
| R052 | `必定(会\|能够)` | `有望` | 学术写作避免绝对化 |

#### 4.2.12 AI 高频名词短语（R053-R055）

| ID | 模式 | 替换 | 原因 | 作用域 |
|----|------|------|------|--------|
| R053 | `在当今社会` | `当前` | AI 套话 | global |
| R054 | `随着.*的(快速\|迅猛)发展` | `伴随.*发展` | AI 开头模板 | paragraph_start |
| R055 | `在.*背景下` | `在.*语境下` | AI 高频短语 | global |

### 4.3 句式调整规则

#### AI-004：禁用句式标记

| 属性 | 值 |
|------|------|
| 规则 ID | AI-004 |
| 规则名称 | 禁用句式标记 |
| 类别 | 去 AI 痕迹 - 句式 |
| 配置键 | `style_rules.yaml#forbidden_patterns` |

**描述**：以下句式直接标记为 WARNING，不自动替换（因替换可能破坏语义）。

**禁用句式列表**：

| 序号 | 句式 | 建议 |
|------|------|------|
| 1 | `本文将从.*角度出发` | AI 开头模板，建议改为直接陈述 |
| 2 | `本研究旨在` | AI 目的模板，建议改为"本研究聚焦于" |
| 3 | `本文(主要\|重点)探讨` | AI 主题模板，建议改为直接陈述研究对象 |
| 4 | `通过.*分析.*得出.*结论` | AI 流程模板，建议改为直接陈述结论 |
| 5 | `基于以上(分析\|讨论)[，,]可以(得出\|认为)` | AI 推导模板，建议改为"据此" |

### 4.4 对仗去除规则

#### AI-005：过度对仗检测

| 属性 | 值 |
|------|------|
| 规则 ID | AI-005 |
| 规则名称 | 过度对仗检测 |
| 类别 | 去 AI 痕迹 - 对仗 |
| 配置键 | `style_rules.yaml#sentence_structure.parallel_structure.avoid_over_symmetry` |

**描述**：AI 生成文本常出现过度工整的对仗结构，如"不仅...而且...更..."、"既...又...还..."、"一方面...另一方面...再一方面..."。这些结构在人类学术写作中较少出现，是 AI 痕迹的典型特征。

**检测逻辑**：

```python
OVER_SYMMETRY_PATTERNS = [
    r"不仅.*而且.*更",
    r"既.*又.*还",
    r"一方面.*另一方面.*再一方面",
    r"首先.*其次.*再次.*最后",
]

def detect_over_symmetry(text: str) -> list[str]:
    detected = []
    for pattern in OVER_SYMMETRY_PATTERNS:
        if re.search(pattern, text):
            detected.append(pattern)
    return detected
```

**修复策略**：将三段对仗缩减为两段，或拆分为独立句子。

### 4.5 标点规范

#### AI-006：标点规范

| 属性 | 值 |
|------|------|
| 规则 ID | AI-006 |
| 规则名称 | 标点规范 |
| 类别 | 去 AI 痕迹 - 标点 |
| 配置键 | `style_rules.yaml#punctuation` |

**参数**：

| 参数 | 值 | 说明 |
|------|------|------|
| max_consecutive_commas | 3 | 连续逗号限制（AI 常堆叠逗号构成长句） |
| dash_style | `——` | 中文破折号双连 |
| ellipsis_style | `……` | 中文省略号六点 |
| quote_style | chinese | 中文引号「」或"" |

### 4.6 词汇多样性约束

#### AI-007：词汇重复约束

| 属性 | 值 |
|------|------|
| 规则 ID | AI-007 |
| 规则名称 | 词汇重复约束 |
| 类别 | 去 AI 痕迹 - 词汇 |
| 配置键 | `style_rules.yaml#lexical_diversity` |

**参数**：

| 参数 | 值 | 说明 |
|------|------|------|
| max_repeat_in_window | 3 | 同一词在 200 字内重复次数上限 |

**高频动词替换建议**：

| 原词 | 替换建议 |
|------|---------|
| 提出 | 给出、构建、形成 |
| 分析 | 剖析、考察、探究 |
| 研究 | 考察、探讨、审视 |
| 实现 | 达成、落实、完成 |
| 影响 | 作用于、牵动、左右 |

### 4.7 AI 痕迹评分

#### AI-008：AI 痕迹评分

| 属性 | 值 |
|------|------|
| 规则 ID | AI-008 |
| 规则名称 | AI 痕迹评分 |
| 类别 | 去 AI 痕迹 - 评分 |
| 配置键 | `style_rules.yaml#ai_trace_scoring` |
| 通过阈值 | 30 分（0-100，越低越像人类写作） |

**扣分规则**：

| 扣分项 | 分值 | 条件 |
|--------|------|------|
| per_template_word_penalty | 5 | 每检测到一处模板词 |
| per_forbidden_pattern_penalty | 10 | 每检测到一处禁用句式 |
| length_distribution_penalty | 8 | 句长分布异常 |
| over_symmetry_penalty | 6 | 过度对仗 |

**评分示例**：

| 文本特征 | 扣分 | 总分 |
|---------|------|------|
| 检测到 3 处模板词 | 3*5=15 | |
| 检测到 1 处禁用句式 | 1*10=10 | |
| 句长分布异常 | 8 | |
| 过度对仗 1 处 | 6 | |
| **合计** | | **39（不合格，>30）** |

**后处理**：

```yaml
post_processing:
  recheck_sentence_length: true       # 替换后重新检测句长分布
  recheck_parallel_structure: true    # 替换后重新检测并列结构
  generate_diff_report: true          # 生成处理前后对比报告
  diff_fields:
    - original_text
    - normalized_text
    - replacements_applied
    - warnings
    - ai_trace_score_before
    - ai_trace_score_after
```

---

## 5. 多粒度生成规则（Multi-Granularity）

多粒度生成规则定义了 ThesisMiner 支持的四种内容粒度及其校验标准。由 `backend/constraints/multi_granularity.py` 实现。

### 5.1 标题级规则

#### MG-001：标题级粒度规格

| 属性 | 值 |
|------|------|
| 规则 ID | MG-001 |
| 规则名称 | 标题级粒度规格 |
| 类别 | 多粒度 - 标题 |
| 配置键 | `multi_granularity.py#GRANULARITY_SPECS.title` |

**规格**：

| 参数 | 值 |
|------|------|
| level | title |
| name | 标题级 |
| min_length | 8 字 |
| max_length | 20 字 |
| description | 精炼的论题标题 |

**生成 Prompt 模板**：

```
请为以下研究方向生成一个精炼的论题标题。
要求：
- 字数在8-20字之间
- 突出创新点
- 避免宽泛表述

研究方向：{topic}
```

**校验逻辑**：

```python
def validate_title_granularity(content: str) -> dict:
    spec = GRANULARITY_SPECS["title"]
    length = len(content)
    valid = spec.min_length <= length <= spec.max_length
    return {
        "valid": valid,
        "level": "title",
        "length": length,
        "min_required": spec.min_length,
        "max_required": spec.max_length,
        "message": "符合要求" if valid else f"长度{length}不在要求范围[{spec.min_length}, {spec.max_length}]内",
    }
```

### 5.2 摘要级规则

#### MG-002：摘要级粒度规格

| 属性 | 值 |
|------|------|
| 规则 ID | MG-002 |
| 规则名称 | 摘要级粒度规格 |
| 类别 | 多粒度 - 摘要 |

**规格**：

| 参数 | 值 |
|------|------|
| level | abstract |
| name | 摘要级 |
| min_length | 200 字 |
| max_length | 300 字 |
| description | 包含背景/问题/方法/意义的摘要 |

**生成 Prompt 模板**：

```
请为以下论题生成一个摘要。
要求：
- 字数在200-300字之间
- 包含研究背景、问题、方法、意义四个要素
- 语言精炼，避免空话

论题：{topic}
```

**四要素校验**：

```python
def validate_abstract_elements(content: str) -> dict:
    elements = {
        "background": ["背景", "近年来", "随着", "当前"],
        "problem": ["问题", "挑战", "瓶颈", "不足"],
        "method": ["方法", "提出", "构建", "采用"],
        "significance": ["意义", "价值", "贡献", "应用"],
    }
    missing = []
    for elem, keywords in elements.items():
        if not any(kw in content for kw in keywords):
            missing.append(elem)
    return {
        "valid": len(missing) == 0,
        "missing_elements": missing,
    }
```

### 5.3 大纲级规则

#### MG-003：大纲级粒度规格

| 属性 | 值 |
|------|------|
| 规则 ID | MG-003 |
| 规则名称 | 大纲级粒度规格 |
| 类别 | 多粒度 - 大纲 |

**规格**：

| 参数 | 值 |
|------|------|
| level | outline |
| name | 大纲级 |
| min_length | 500 字 |
| max_length | 2000 字 |
| description | 三级目录结构 |

**生成 Prompt 模板**：

```
请为以下论题生成一个三级大纲。
要求：
- 使用标准的学术大纲格式（一、(一)、1.）
- 包含绪论、文献综述、研究方法、预期成果等章节
- 每个三级标题下附简要说明

论题：{topic}
```

**三级目录结构校验**：

```python
def validate_outline_structure(content: str) -> dict:
    # 一级标题：一、二、三、...
    level1_pattern = r"^[一二三四五六七八九十]+、"
    # 二级标题：(一)(二)(三)...
    level2_pattern = r"^\([一二三四五六七八九十]+\)"
    # 三级标题：1. 2. 3. ...
    level3_pattern = r"^\d+\."

    level1_count = len(re.findall(level1_pattern, content, re.MULTILINE))
    level2_count = len(re.findall(level2_pattern, content, re.MULTILINE))
    level3_count = len(re.findall(level3_pattern, content, re.MULTILINE))

    issues = []
    if level1_count < 5:
        issues.append(f"一级标题数{level1_count}不足，建议≥5个")
    if level2_count < 10:
        issues.append(f"二级标题数{level2_count}不足，建议≥10个")
    if level3_count < 15:
        issues.append(f"三级标题数{level3_count}不足，建议≥15个")

    return {
        "valid": len(issues) == 0,
        "level1_count": level1_count,
        "level2_count": level2_count,
        "level3_count": level3_count,
        "issues": issues,
    }
```

### 5.4 全文级规则

#### MG-004：全文级粒度规格

| 属性 | 值 |
|------|------|
| 规则 ID | MG-004 |
| 规则名称 | 全文级粒度规格 |
| 类别 | 多粒度 - 全文 |

**规格**：

| 参数 | 值 |
|------|------|
| level | full |
| name | 全文级 |
| min_length | 5000 字 |
| max_length | 50000 字 |
| description | 完整开题报告 |

**生成 Prompt 模板**：

```
请为以下论题生成完整的开题报告。
要求：
- 字数≥5000字
- 包含：选题依据、文献综述、研究内容、研究方法、技术路线、预期成果、进度安排
- 学术规范，引用规范

论题：{topic}
```

**章节完整性校验**：

```python
REQUIRED_SECTIONS = [
    "选题依据",
    "文献综述",
    "研究内容",
    "研究方法",
    "技术路线",
    "预期成果",
    "进度安排",
]

def validate_full_text_sections(content: str) -> dict:
    missing = []
    for section in REQUIRED_SECTIONS:
        if section not in content:
            missing.append(section)
    return {
        "valid": len(missing) == 0,
        "missing_sections": missing,
        "present_sections": [s for s in REQUIRED_SECTIONS if s not in missing],
    }
```

### 5.5 粒度切换规则

#### MG-005：粒度切换规则

| 属性 | 值 |
|------|------|
| 规则 ID | MG-005 |
| 规则名称 | 粒度切换规则 |
| 类别 | 多粒度 - 切换 |

**描述**：用户可在四种粒度间自由切换，切换时保留上下文，仅改变输出详细程度。

**切换矩阵**：

| 源粒度 \ 目标粒度 | title | abstract | outline | full |
|------------------|-------|----------|---------|------|
| title | - | 扩展 | 扩展 | 扩展 |
| abstract | 精炼 | - | 扩展 | 扩展 |
| outline | 精炼 | 精炼 | - | 扩展 |
| full | 精炼 | 精炼 | 精炼 | - |

**扩展策略**：保留核心信息，补充细节。

**精炼策略**：提取核心信息，删除细节。

### 5.6 粒度与模型路由

#### MG-006：粒度与模型路由

| 属性 | 值 |
|------|------|
| 规则 ID | MG-006 |
| 规则名称 | 粒度与模型路由 |
| 类别 | 多粒度 - 路由 |

**模型分配**：

| 粒度 | 默认模型 | 备选模型 | 原因 |
|------|---------|---------|------|
| title | qwen3-max | gpt-4.1 | 创意性强，需高温度 |
| abstract | gpt-4.1 | claude-sonnet-4.5 | 平衡创意与规范 |
| outline | claude-sonnet-4.5 | gpt-4.1 | 结构化能力强 |
| full | claude-opus-4.5 | gpt-4.1 | 顶级质量，长文本 |

### 5.7 粒度与缓存

#### MG-007：粒度与缓存

| 属性 | 值 |
|------|------|
| 规则 ID | MG-007 |
| 规则名称 | 粒度与缓存 |
| 类别 | 多粒度 - 缓存 |

**缓存策略**：

| 粒度 | 可缓存 | 原因 |
|------|--------|------|
| title | 否 | 创意性强，每次生成都不同 |
| abstract | 否 | 创意性较强 |
| outline | 是 | 结构化，相似论题可复用 |
| full | 否 | 长文本，缓存成本高 |

### 5.8 粒度校验顺序

#### MG-008：粒度校验顺序

| 属性 | 值 |
|------|------|
| 规则 ID | MG-008 |
| 规则名称 | 粒度校验顺序 |
| 类别 | 多粒度 - 校验 |

**校验顺序**：

1. 长度校验（min_length ≤ length ≤ max_length）
2. 结构校验（标题/摘要/大纲/全文各自的结构要求）
3. 要素校验（摘要四要素、全文七章节等）
4. 风格校验（去 AI 痕迹）
5. 学术规范校验（引用格式、参考文献）

---

## 6. 五阶段门禁规则（Stage Gate）

五阶段门禁规则定义了 ThesisMiner v8.0 闭环导航流的阶段切换条件。由 `backend/constraints/stage_gate.py` 实现。

### 6.1 五阶段总览

```
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│  阶段一         │     │  阶段二         │     │  阶段三         │
│  info_confirm  │ ──> │  creativity    │ ──> │  validation    │
│  信息确权       │     │  谱系解析+创意  │     │  重复度+硬约束  │
└────────────────┘     └────────────────┘     └────────────────┘
                                                      │
                                                      │
                                                      ▼
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│  阶段五         │ <── │  阶段四         │ <── │  通过门禁       │
│  deep_assist   │     │  generation    │     │  (评分≥60)     │
│  深度辅助       │     │  多粒度生成     │     │                │
└────────────────┘     └────────────────┘     └────────────────┘
```

### 6.1 阶段一：信息确权

#### SG-001：信息确权门禁

| 属性 | 值 |
|------|------|
| 规则 ID | SG-001 |
| 规则名称 | 信息确权门禁 |
| 类别 | 阶段门禁 - 信息确权 |
| 阶段 | info_confirm |
| 配置键 | `stage_gate.py#STAGE_GATES[Stage.INFO_CONFIRM]` |

**门禁定义**：

| 属性 | 值 |
|------|------|
| 名称 | 信息确权 |
| 描述 | 联网检索近 2 年文献，展示摘要后等待用户确认 |
| 进入条件 | 用户发起论题生成请求 |
| 退出条件 | 用户确认信息无误 |
| 需要用户确认 | 是 |
| 失败回退 | 无（首阶段） |

**门禁检查逻辑**：

```python
def check_info_confirm_gate(data: dict) -> GateResult:
    if data.get("user_confirmed"):
        return GateResult(
            passed=True,
            stage=Stage.INFO_CONFIRM,
            message="用户已确认",
        )
    return GateResult(
        passed=False,
        stage=Stage.INFO_CONFIRM,
        message="等待用户确认",
    )
```

**进入条件详解**：

- 用户通过 Web UI 或 API 发起论题生成请求。
- 系统创建新会话（session）与对话（conversation）。
- Orchestrator Agent 接管，调用 Searcher Agent 联网检索近 2 年文献。

**退出条件详解**：

- Searcher Agent 返回文献摘要。
- 系统向用户展示文献摘要，等待用户确认。
- 用户确认信息无误后，门禁通过，进入阶段二。

**强制联网检索**：

- 信息确权阶段**强制**进行联网检索，确保信息时效性。
- 检索范围：近 2 年（24 个月）内的相关文献。
- 检索数据库：CNKI、Web of Science、arXiv、Semantic Scholar 等。
- 检索结果通过 `citation_parser` 解析为结构化引用。

### 6.2 阶段二：创意激发

#### SG-002：创意激发门禁

| 属性 | 值 |
|------|------|
| 规则 ID | SG-002 |
| 规则名称 | 创意激发门禁 |
| 类别 | 阶段门禁 - 创意 |
| 阶段 | creativity |
| 配置键 | `stage_gate.py#STAGE_GATES[Stage.CREATIVITY]` |

**门禁定义**：

| 属性 | 值 |
|------|------|
| 名称 | 谱系解析与四维创意 |
| 描述 | 基于检索结果生成候选论题 |
| 进入条件 | 信息确权阶段通过 |
| 退出条件 | 生成至少 3 个候选论题 |
| 需要用户确认 | 否 |
| 失败回退 | info_confirm |

**门禁检查逻辑**：

```python
def check_creativity_gate(data: dict) -> GateResult:
    candidates = data.get("candidates", [])
    if len(candidates) >= 3:
        return GateResult(
            passed=True,
            stage=Stage.CREATIVITY,
            message=f"生成{len(candidates)}个候选",
        )
    return GateResult(
        passed=False,
        stage=Stage.CREATIVITY,
        message=f"候选不足，需≥3个，当前{len(candidates)}个",
    )
```

**进入条件详解**：

- 信息确权门禁通过（用户已确认）。
- Reasoner Agent 接管，进行谱系解析。
- 谱系解析：基于检索结果构建学术谱系图，识别研究脉络。

**退出条件详解**：

- Inspire Agent（创意 Agent）基于谱系图生成候选论题。
- 候选论题数量：硕士 5 个，博士 8 个（可配置）。
- 至少 3 个候选论题方可通过门禁。

**候选论题生成流程**：

1. 谱系解析：构建学术谱系图，识别研究脉络。
2. 四维创意引擎：基于谱系图，从四个维度激发创意。
3. 候选生成：生成 N 个候选论题，每个论题附四维评分。
4. 候选排序：按综合评分排序，取前 K 名。

### 6.3 阶段三：可行性校验

#### SG-003：可行性校验门禁

| 属性 | 值 |
|------|------|
| 规则 ID | SG-003 |
| 规则名称 | 可行性校验门禁 |
| 类别 | 阶段门禁 - 校验 |
| 阶段 | validation |
| 配置键 | `stage_gate.py#STAGE_GATES[Stage.VALIDATION]` |

**门禁定义**：

| 属性 | 值 |
|------|------|
| 名称 | 重复度评估与硬约束修复 |
| 描述 | 评估候选论题的新颖性与可行性 |
| 进入条件 | 创意阶段产出候选论题 |
| 退出条件 | 平均评分 ≥ 60 |
| 最低通过分数 | 60 |
| 失败回退 | creativity |

**门禁检查逻辑**：

```python
def check_validation_gate(data: dict) -> GateResult:
    avg_score = data.get("avg_score", 0)
    min_score = 60  # STAGE_GATES[Stage.VALIDATION].min_score

    if avg_score >= min_score:
        return GateResult(
            passed=True,
            stage=Stage.VALIDATION,
            message=f"平均评分{avg_score}≥{min_score}",
        )
    return GateResult(
        passed=False,
        stage=Stage.VALIDATION,
        message=f"平均评分{avg_score}<{min_score}，回退至创意阶段",
        retry_stage=Stage.CREATIVITY,
    )
```

**进入条件详解**：

- 创意激发门禁通过（至少 3 个候选论题）。
- Critic Agent 接管，进行可行性校验。

**退出条件详解**：

- 对每个候选论题进行四维新颖性评分。
- 计算平均评分，平均评分 ≥ 60 方可通过门禁。
- 同时校验硬约束规则（标题、学科、时间、重复度等）。

**校验内容**：

1. **新颖性评分**：四维加权评分，平均 ≥ 60。
2. **重复度评估**：与已有文献相似度 < 0.3。
3. **硬约束校验**：标题长度、学科匹配、时间可行性等。
4. **风险评级**：低/中/高风险，高风险阻断。

### 6.4 阶段四：多粒度生成

#### SG-004：多粒度生成门禁

| 属性 | 值 |
|------|------|
| 规则 ID | SG-004 |
| 规则名称 | 多粒度生成门禁 |
| 类别 | 阶段门禁 - 生成 |
| 阶段 | generation |
| 配置键 | `stage_gate.py#STAGE_GATES[Stage.GENERATION]` |

**门禁定义**：

| 属性 | 值 |
|------|------|
| 名称 | 多粒度生成与降重脱敏 |
| 描述 | 按选定粒度生成开题内容 |
| 进入条件 | 校验阶段通过 |
| 退出条件 | 内容生成完成且通过 style_normalizer |
| 失败回退 | validation |

**门禁检查逻辑**：

```python
def check_generation_gate(data: dict) -> GateResult:
    content = data.get("content", "")
    ai_trace_score = data.get("ai_trace_score", 100)
    pass_threshold = 30  # style_rules.yaml#ai_trace_scoring.pass_threshold

    if not content:
        return GateResult(
            passed=False,
            stage=Stage.GENERATION,
            message="内容未生成",
        )

    if ai_trace_score > pass_threshold:
        return GateResult(
            passed=False,
            stage=Stage.GENERATION,
            message=f"AI痕迹评分{ai_trace_score}>{pass_threshold}，需重新规范化",
        )

    return GateResult(
        passed=True,
        stage=Stage.GENERATION,
        message="内容生成完成且通过style_normalizer",
    )
```

**进入条件详解**：

- 可行性校验门禁通过（平均评分 ≥ 60）。
- 用户选定候选论题与生成粒度。
- Writer Agent 接管，进行多粒度生成。

**退出条件详解**：

- 按选定粒度（标题/摘要/大纲/全文）生成内容。
- 内容通过 `style_normalizer` 去 AI 痕迹处理。
- AI 痕迹评分 ≤ 30 方可通过门禁。

**生成流程**：

1. **粒度选择**：用户选择标题/摘要/大纲/全文粒度。
2. **内容生成**：Writer Agent 按粒度生成内容。
3. **去 AI 痕迹**：`style_normalizer` 处理生成内容。
4. **学术规范校验**：校验引用格式、参考文献格式。
5. **降重脱敏**：必要时进行降重处理。

### 6.5 阶段五：深度辅助

#### SG-005：深度辅助门禁

| 属性 | 值 |
|------|------|
| 规则 ID | SG-005 |
| 规则名称 | 深度辅助门禁 |
| 类别 | 阶段门禁 - 深度辅助 |
| 阶段 | deep_assist |
| 配置键 | `stage_gate.py#STAGE_GATES[Stage.DEEP_ASSIST]` |

**门禁定义**：

| 属性 | 值 |
|------|------|
| 名称 | 深度辅助闭环 |
| 描述 | 文献精读/实验预研/答辩模拟 |
| 进入条件 | 生成阶段完成 |
| 退出条件 | 用户结束或发起新请求 |
| 失败回退 | 无（终阶段） |

**深度辅助功能**：

| 功能 | 描述 | 默认模型 |
|------|------|---------|
| 文献精读 | 对选定文献进行深度解读 | gemini-2.5-pro |
| 实验预研 | 辅助设计实验方案 | deepseek-r2 |
| 答辩模拟 | 模拟答辩问答 | claude-sonnet-4.5 |
| 写作辅助 | 辅助论文写作 | gpt-4.1 |
| 投稿建议 | 期刊选择与投稿建议 | gpt-4.1 |

### 6.6 回退与重试机制

#### SG-006：回退机制

| 属性 | 值 |
|------|------|
| 规则 ID | SG-006 |
| 规则名称 | 回退机制 |
| 类别 | 阶段门禁 - 回退 |

**回退规则**：

| 当前阶段 | 失败原因 | 回退至 |
|---------|---------|--------|
| creativity | 候选不足 | info_confirm |
| validation | 评分不达标 | creativity |
| validation | 重复度过高 | creativity |
| generation | AI 痕迹过重 | validation |
| generation | 内容不合规 | validation |

**回退逻辑**：

```python
def handle_gate_failure(result: GateResult) -> dict:
    if result.retry_stage:
        return {
            "action": "retry",
            "retry_stage": result.retry_stage,
            "message": result.message,
        }
    return {
        "action": "block",
        "message": result.message,
    }
```

#### SG-007：重试次数限制

| 属性 | 值 |
|------|------|
| 规则 ID | SG-007 |
| 规则名称 | 重试次数限制 |
| 类别 | 阶段门禁 - 重试 |
| 阈值 | 最大重试 3 次 |

**描述**：每个阶段最多重试 3 次，超过则阻断流程并提示用户。

```python
MAX_RETRIES = 3

def check_retry_limit(session_id: str, stage: Stage) -> bool:
    retry_count = get_retry_count(session_id, stage)
    if retry_count >= MAX_RETRIES:
        return False  # 超过重试上限
    return True
```

---

## 7. 学术规范规则（Academic Standards）

学术规范规则定义了 ThesisMiner 对引用格式、参考文献格式、图表规范的校验标准。由 `backend/constraints/academic_standards.py` 实现，内置 100+ 格式化规则。

### 7.1 引用格式规则

#### AS-001：引用格式支持

| 属性 | 值 |
|------|------|
| 规则 ID | AS-001 |
| 规则名称 | 引用格式支持 |
| 类别 | 学术规范 - 引用 |
| 配置键 | `academic_standards.py#CitationFormat` |

**支持的引用格式**：

| 格式 | 英文 | 枚举值 | 适用学科 |
|------|------|--------|---------|
| GB/T 7714 | China National Standard | gb_t_7714 | 中文全学科 |
| APA | American Psychological Association | apa | 心理学/教育学/社会科学 |
| MLA | Modern Language Association | mla | 文学/语言学/人文学科 |
| Chicago | Chicago Manual of Style | chicago | 历史/艺术/人文学科 |
| IEEE | Institute of Electrical and Electronics Engineers | ieee | 工程/计算机/电子 |
| Vancouver | Vancouver Style | vancouver | 医学/生物科学 |

#### AS-002：GB/T 7714 引用格式

| 属性 | 值 |
|------|------|
| 规则 ID | AS-002 |
| 规则名称 | GB/T 7714 引用格式 |
| 类别 | 学术规范 - 引用 |

**期刊文章格式**：

```
[序号] 作者. 题名[J]. 刊名, 年, 卷(期): 起止页码.
```

示例：

```
[1] 张三, 李四. 深度学习在医学影像中的应用[J]. 计算机学报, 2026, 49(3): 512-525.
```

**书籍格式**：

```
[序号] 作者. 书名[M]. 版次. 出版地: 出版者, 出版年: 起止页码.
```

示例：

```
[2] 王五. 机器学习导论[M]. 第3版. 北京: 清华大学出版社, 2025: 88-102.
```

**会议论文格式**：

```
[序号] 作者. 题名[C]//会议名. 出版地: 出版者, 出版年: 起止页码.
```

**学位论文格式**：

```
[序号] 作者. 题名[D]. 保存地: 保存单位, 年份.
```

**网络资源格式**：

```
[序号] 作者. 题名[EB/OL]. (发布日期)[引用日期]. URL.
```

#### AS-003：APA 引用格式

**期刊文章格式**：

```
作者. (年份). 题名. 刊名, 卷(期), 起止页码.
```

示例：

```
Zhang, S., & Li, S. (2026). Deep learning for medical image segmentation. Journal of Computer Science, 49(3), 512-525.
```

#### AS-004：IEEE 引用格式

**期刊文章格式**：

```
[序号] 作者, "题名," 刊名, vol. 卷, no. 期, pp. 起止页码, 年份.
```

示例：

```
[1] S. Zhang and S. Li, "Deep learning for medical image segmentation," J. Comput. Sci., vol. 49, no. 3, pp. 512-525, 2026.
```

### 7.2 参考文献格式规则

#### AS-005：参考文献完整性校验

| 属性 | 值 |
|------|------|
| 规则 ID | AS-005 |
| 规则名称 | 参考文献完整性校验 |
| 类别 | 学术规范 - 参考文献 |

**必填字段**：

| 文献类型 | 必填字段 |
|---------|---------|
| journal（期刊） | authors, title, year, journal, volume, issue, pages |
| book（书籍） | authors, title, year, publisher, city |
| conference（会议） | authors, title, year, conference_name, location |
| thesis（学位论文） | authors, title, year, degree, institution |
| web（网络资源） | authors, title, url, access_date |

**校验逻辑**：

```python
def validate_reference(entry: ReferenceEntry) -> list[CitationIssue]:
    issues = []
    required_fields = REQUIRED_FIELDS.get(entry.type, [])

    for field in required_fields:
        value = getattr(entry, field, "")
        if not value:
            issues.append(CitationIssue(
                field=field,
                message=f"缺失必填字段: {field}",
                severity="error",
                suggestion=f"请补充{field}字段",
            ))

    return issues
```

#### AS-006：参考文献数量校验

| 属性 | 值 |
|------|------|
| 规则 ID | AS-006 |
| 规则名称 | 参考文献数量校验 |
| 类别 | 学术规范 - 参考文献 |

**数量要求**：

| 学位 | 最少数量 | 推荐数量 |
|------|---------|---------|
| 硕士 | 30 篇 | 50-80 篇 |
| 博士 | 50 篇 | 100-200 篇 |

**中外文比例**：

| 学位 | 中文比例 | 外文比例 |
|------|---------|---------|
| 硕士 | 40-60% | 40-60% |
| 博士 | 30-50% | 50-70% |

**近 5 年文献比例**：

| 学位 | 近 5 年比例 |
|------|-----------|
| 硕士 | ≥ 50% |
| 博士 | ≥ 60% |

### 7.3 图表规范规则

#### AS-007：图规范

| 属性 | 值 |
|------|------|
| 规则 ID | AS-007 |
| 规则名称 | 图规范 |
| 类别 | 学术规范 - 图 |

**图编号规则**：

- 按章节编号：图 1-1、图 1-2、图 2-1...
- 全文连续编号：图 1、图 2、图 3...

**图题位置**：图下方居中。

**图题格式**：

```
图 1-1 深度学习模型架构
```

**校验规则**：

| 规则 | 严重级别 | 说明 |
|------|---------|------|
| 图必须有编号 | error | 每张图必须有唯一编号 |
| 图必须有标题 | error | 每张图必须有描述性标题 |
| 图编号必须连续 | warning | 图编号应连续，不跳号 |
| 图题在图下方 | warning | 图题应在图下方居中 |
| 图必须有引用 | warning | 正文中必须引用每张图 |

#### AS-008：表规范

| 属性 | 值 |
|------|------|
| 规则 ID | AS-008 |
| 规则名称 | 表规范 |
| 类别 | 学术规范 - 表 |

**表编号规则**：与图相同，按章节或全文连续编号。

**表题位置**：表上方居中。

**表题格式**：

```
表 1-1 实验结果对比
```

**三线表规范**：

- 学术论文表格应使用三线表（顶线、栏目线、底线）。
- 不使用竖线。
- 顶线和底线粗，栏目线细。

### 7.4 学术写作规范

#### AS-009：学术写作语言规范

| 属性 | 值 |
|------|------|
| 规则 ID | AS-009 |
| 规则名称 | 学术写作语言规范 |
| 类别 | 学术规范 - 写作 |

**语言要求**：

| 要求 | 说明 |
|------|------|
| 客观性 | 避免主观色彩强烈的词汇（如"完美"、"极好"） |
| 准确性 | 使用准确的专业术语，避免模糊表述 |
| 简洁性 | 避免冗长表述，能用一个词不用一句话 |
| 规范性 | 遵循学术写作规范，避免口语化 |

#### AS-010：学术写作时态规范

| 属性 | 值 |
|------|------|
| 规则 ID | AS-010 |
| 规则名称 | 学术写作时态规范 |
| 类别 | 学术规范 - 写作 |

**时态使用规则**：

| 章节 | 推荐时态 | 说明 |
|------|---------|------|
| 摘要 | 一般现在时/一般过去时 | 陈述研究内容用现在时，陈述研究过程用过去时 |
| 引言 | 一般现在时 | 陈述研究背景与现状 |
| 文献综述 | 一般现在时/一般过去时 | 他人成果用现在时，他人研究过程用过去时 |
| 方法 | 一般过去时 | 陈述自己的研究过程 |
| 结果 | 一般过去时 | 陈述自己的研究发现 |
| 讨论 | 一般现在时 | 讨论研究结果的意义 |
| 结论 | 一般现在时 | 陈述研究结论 |

#### AS-011：学术写作人称规范

| 属性 | 值 |
|------|------|
| 规则 ID | AS-011 |
| 规则名称 | 学术写作人称规范 |
| 类别 | 学术规范 - 写作 |

**人称使用规则**：

| 场合 | 推荐人称 | 示例 |
|------|---------|------|
| 中文论文 | 第三人称/无主语 | "本研究提出..."、"本文构建..." |
| 英文论文 | 第三人称/被动语态 | "This study proposes..."、"It is found that..." |
| 避免 | 第一人称单数 | 避免"我认为..."、"我发现..." |

---

## 8. 规则优先级与冲突解决

### 8.1 优先级体系

ThesisMiner v8.0 的规则优先级从高到低分为五级：

| 优先级 | 类别 | 说明 | 示例 |
|--------|------|------|------|
| P0 | 用户显式指定 | 用户通过 UI/API 显式指定的规则 | 用户指定标题长度≤20字 |
| P1 | 学位分级 | 按学位（master/doctor）分级的规则 | 硕士标题≤25字，博士≤30字 |
| P2 | 阶段默认 | 五阶段步骤的默认规则 | info_confirm 阶段默认模型 |
| P3 | 全局默认 | 全局默认规则 | 全局默认模型 deepseek-v3.2 |
| P4 | 兜底规则 | 当所有规则都不适用时的兜底规则 | 兜底使用 doubao-1.5-pro |

**优先级判定逻辑**：

```python
def resolve_rule_priority(
    user_specified: dict,
    degree: str,
    stage: str,
    global_default: dict,
) -> dict:
    """解析规则优先级"""
    # P0: 用户显式指定
    if user_specified:
        return user_specified

    # P1: 学位分级
    degree_rule = DEGREE_RULES.get(degree, {})
    if degree_rule:
        return degree_rule

    # P2: 阶段默认
    stage_rule = STAGE_RULES.get(stage, {})
    if stage_rule:
        return stage_rule

    # P3: 全局默认
    if global_default:
        return global_default

    # P4: 兜底
    return FALLBACK_RULE
```

### 8.2 冲突检测

**常见冲突场景**：

| 冲突场景 | 冲突规则 | 冲突原因 |
|---------|---------|---------|
| 标题长度冲突 | HR-001 vs 用户指定 | 用户指定标题≤20字，但 HR-001 允许≤25字 |
| 模型选择冲突 | routing.yaml vs 用户指定 | 用户指定用 gpt-4.1，但 routing.yaml 默认 claude-sonnet-4.5 |
| 重复度冲突 | HR-012 vs NS-007 | HR-012 要求相似度<0.3，NS-007 中风险允许<0.5 |
| 粒度冲突 | MG-001 vs 用户指定 | 用户指定标题≤15字，但 MG-001 要求8-20字 |

**冲突检测逻辑**：

```python
def detect_conflicts(rules: list[dict]) -> list[dict]:
    conflicts = []
    for i, rule_a in enumerate(rules):
        for rule_b in rules[i+1:]:
            if rule_a["field"] == rule_b["field"]:
                if rule_a["threshold"] != rule_b["threshold"]:
                    conflicts.append({
                        "rule_a": rule_a["id"],
                        "rule_b": rule_b["id"],
                        "field": rule_a["field"],
                        "conflict": f"{rule_a['threshold']} vs {rule_b['threshold']}",
                    })
    return conflicts
```

### 8.3 冲突解决策略

#### 8.3.1 优先级策略

按优先级高低解决冲突，高优先级规则覆盖低优先级规则。

```python
def resolve_conflict_by_priority(conflict: dict) -> dict:
    rule_a = get_rule(conflict["rule_a"])
    rule_b = get_rule(conflict["rule_b"])

    if rule_a["priority"] > rule_b["priority"]:
        return {"winner": rule_a, "loser": rule_b}
    elif rule_b["priority"] > rule_a["priority"]:
        return {"winner": rule_b, "loser": rule_a}
    else:
        # 同优先级，触发合并策略
        return resolve_conflict_by_merge(rule_a, rule_b)
```

#### 8.3.2 合并策略

同优先级规则冲突时，采用合并策略：

| 合并策略 | 适用场景 | 合并方式 |
|---------|---------|---------|
| 取严 | 阈值类规则 | 取更严格的阈值 |
| 取宽 | 阈值类规则 | 取更宽松的阈值 |
| 取并集 | 集合类规则 | 取两规则的并集 |
| 取交集 | 集合类规则 | 取两规则的交集 |
| 用户决策 | 无法自动合并 | 提示用户选择 |

```python
def resolve_conflict_by_merge(rule_a: dict, rule_b: dict) -> dict:
    if rule_a["type"] == "threshold":
        # 取严策略
        if rule_a["direction"] == "max":
            return min(rule_a["threshold"], rule_b["threshold"])
        else:
            return max(rule_a["threshold"], rule_b["threshold"])
    elif rule_a["type"] == "set":
        # 取交集策略
        return rule_a["value"] & rule_b["value"]
    else:
        # 用户决策
        return None
```

#### 8.3.3 冲突日志

所有冲突解决过程记录日志，供审计：

```python
def log_conflict_resolution(conflict: dict, resolution: dict):
    logger.info({
        "event": "rule_conflict_resolved",
        "conflict": conflict,
        "resolution": resolution,
        "timestamp": datetime.now().isoformat(),
    })
```

---

## 9. 规则版本管理

### 9.1 版本编号

ThesisMiner v8.0 的规则版本采用**语义化版本号**（Semantic Versioning）：

```
MAJOR.MINOR.PATCH
```

| 版本段 | 含义 | 触发条件 | 示例 |
|--------|------|---------|------|
| MAJOR | 主版本 | 不兼容的规则变更 | v7.0 → v8.0 |
| MINOR | 次版本 | 向后兼容的功能新增 | v8.0 → v8.1 |
| PATCH | 补丁版本 | 向后兼容的问题修复 | v8.0.0 → v8.0.1 |

**当前版本**：v8.0

### 9.2 变更类型

| 变更类型 | 说明 | 版本影响 | 示例 |
|---------|------|---------|------|
| 新增规则 | 新增规则定义 | MINOR+1 | 新增 HR-014 |
| 修改阈值 | 修改规则阈值 | MINOR+1 | 标题长度从25改为20 |
| 废弃规则 | 标记规则废弃 | MINOR+1 | 废弃 HR-005 |
| 删除规则 | 删除已废弃规则 | MAJOR+1 | 删除 HR-005 |
| 重命名规则 | 重命名规则 ID | MAJOR+1 | HR-005 → HR-014 |
| 修复 Bug | 修复规则逻辑 Bug | PATCH+1 | 修复正则匹配错误 |

### 9.3 兼容性策略

#### 9.3.1 向后兼容

- **MINOR 版本**：保证向后兼容，旧配置文件在新版本中仍可使用。
- **PATCH 版本**：保证向后兼容，仅修复 Bug。

#### 9.3.2 废弃策略

规则废弃采用**渐进式废弃**：

1. **标记废弃**：在配置中标记 `deprecated: true`，文档中标注"已废弃"。
2. **保留 1 个主版本**：废弃规则保留 1 个主版本，期间仍可使用但产生警告日志。
3. **删除**：在下一个主版本中删除废弃规则。

```yaml
# 废弃规则示例
- id: HR-005
  name: 标题禁止模式匹配
  deprecated: true
  deprecated_since: v8.0
  removed_in: v9.0
  replacement: HR-006
  reason: "与 HR-006 功能重叠，统一至 HR-006"
```

#### 9.3.3 迁移指南

主版本升级时提供迁移指南，说明规则变更与配置迁移：

```markdown
# v7.0 → v8.0 迁移指南

## 规则变更

### 新增规则
- HR-014: 标题禁用缩写词
- NS-001 ~ NS-009: 四维创意引擎规则
- AI-001 ~ AI-008: 去 AI 痕迹规则

### 废弃规则
- HR-005（v7）→ HR-006（v8）: 标题禁止模式合并至学科匹配

### 阈值变更
- 标题最大长度（硕士）: 30字 → 25字
- 重复度阈值: 0.5 → 0.3

## 配置迁移
1. 更新 hard_rules.yaml 中的阈值
2. 新增 novelty_weights.yaml
3. 新增 style_rules.yaml
```

---

## 10. 完整规则示例库

本节提供完整的规则定义示例，涵盖硬约束、新颖性评分、去 AI 痕迹三大类，共计 50+ 条规则。

### 10.1 硬约束规则示例（HR-001 ~ HR-020）

#### HR-001：标题最大长度（硕士）

```yaml
- id: HR-001
  name: 标题最大长度（硕士）
  category: hard_rule
  subcategory: title
  severity: error
  version: v8.0
  deprecated: false
  config_key: "hard_rules.yaml#title.max_length_master"
  threshold:
    type: max
    value: 25
    unit: 字
  applicable_degree: master
  scope: title
  description: |
    硕士论题标题长度不得超过25字（含标点）。
    超过此长度会导致标题冗长、核心不突出，不符合硕士论文规范。
  validation_logic: |
    def validate(title: str) -> list[Violation]:
        if len(title) > 25:
            return [Violation(
                rule="HR-001",
                severity="error",
                message=f"标题长度{len(title)}超过限制25字（硕士）",
                field="title",
            )]
        return []
  error_message: "标题长度{actual_length}超过限制{max_length}字（硕士）"
  repair_suggestion: |
    - 采用 extract_core_noun_phrase 策略，通过依存句法分析截取核心名词短语
    - 删除冗余修饰词（如"基于...的"、"关于...的"）
    - 将长定语后置为副标题
  repair_examples:
    - original: "基于深度学习的医学影像分割方法的研究与应用"
      repaired: "深度学习医学影像分割方法"
      strategy: extract_core_noun_phrase
  metadata:
    author: ThesisMiner 团队
    created_at: 2026-06-19
    updated_at: 2026-06-19
```

#### HR-002：标题最大长度（博士）

```yaml
- id: HR-002
  name: 标题最大长度（博士）
  category: hard_rule
  subcategory: title
  severity: error
  version: v8.0
  config_key: "hard_rules.yaml#title.max_length_doctor"
  threshold:
    type: max
    value: 30
    unit: 字
  applicable_degree: doctor
  scope: title
  description: |
    博士论题标题长度不得超过30字。
    博士论文研究深度更高，标题可适当延长，但仍需精炼。
  validation_logic: |
    def validate(title: str) -> list[Violation]:
        if len(title) > 30:
            return [Violation(
                rule="HR-002",
                severity="error",
                message=f"标题长度{len(title)}超过限制30字（博士）",
                field="title",
            )]
        return []
  error_message: "标题长度{actual_length}超过限制{max_length}字（博士）"
  repair_suggestion: "同 HR-001"
```

#### HR-003：标题最小长度

```yaml
- id: HR-003
  name: 标题最小长度
  category: hard_rule
  subcategory: title
  severity: warning
  version: v8.0
  config_key: "hard_rules.yaml#title.min_length"
  threshold:
    type: min
    value: 8
    unit: 字
  scope: title
  description: |
    标题长度不得少于8字。
    过短的标题通常信息量不足，无法准确表达研究内容。
  error_message: "标题长度{actual_length}过短，建议≥8字"
  repair_suggestion: "补充研究对象、方法或应用场景，使标题信息更完整"
```

#### HR-004：标题禁用动词开头

```yaml
- id: HR-004
  name: 标题禁用动词开头
  category: hard_rule
  subcategory: title
  severity: error
  version: v8.0
  config_key: "hard_rules.yaml#title.forbidden_verbs"
  forbidden_values:
    - 研究
    - 分析
    - 探讨
    - 调查
    - 实现
    - 构建
    - 设计
    - 开发
    - 优化
    - 改进
    - 评估
    - 验证
  scope: title
  description: |
    标题不得以动词开头。
    学术标题应为名词性短语，动词开头会导致标题口语化、不规范。
  validation_logic: |
    FORBIDDEN_VERBS = ["研究", "分析", "探讨", "调查", "实现", "构建",
                       "设计", "开发", "优化", "改进", "评估", "验证"]
    def validate(title: str) -> list[Violation]:
        for verb in FORBIDDEN_VERBS:
            if title.startswith(verb):
                return [Violation(
                    rule="HR-004",
                    severity="error",
                    message=f"标题不应以动词'{verb}'开头，应改为名词性短语",
                    field="title",
                )]
        return []
  error_message: "标题不应以动词'{verb}'开头，应改为名词性短语"
  repair_suggestion: "采用 convert_to_noun_phrase 策略，将动词前置转为名词性短语"
  repair_examples:
    - original: "研究深度学习在医学影像中的应用"
      repaired: "深度学习医学影像应用研究"
      strategy: convert_to_noun_phrase
    - original: "分析社交网络中的信息传播机制"
      repaired: "社交网络信息传播机制分析"
      strategy: convert_to_noun_phrase
```

#### HR-005：标题禁止模式匹配

```yaml
- id: HR-005
  name: 标题禁止模式匹配
  category: hard_rule
  subcategory: title
  severity: error
  version: v8.0
  config_key: "hard_rules.yaml#title.forbidden_patterns"
  forbidden_patterns:
    - pattern: "基于.*的研究"
      reason: 太通用
    - pattern: "基于.*的分析"
      reason: 太通用
    - pattern: "基于.*的探讨"
      reason: 太通用
    - pattern: "基于.*的应用研究"
      reason: 太通用
    - pattern: "基于.*的设计"
      reason: 太通用
    - pattern: "基于.*的实现"
      reason: 太通用
    - pattern: ".*的应用研究"
      reason: 太通用
    - pattern: ".*的初步研究"
      reason: 显得不够深入
    - pattern: ".*的探索性研究"
      reason: 显得不够深入
  scope: title
  description: |
    标题不得匹配预设的禁止正则模式。
    这些模式通常是过于宽泛、缺乏创新的标题套路。
  validation_logic: |
    import re
    FORBIDDEN_PATTERNS = [
        r"基于.*的研究", r"基于.*的分析", r"基于.*的探讨",
        r"基于.*的应用研究", r"基于.*的设计", r"基于.*的实现",
        r".*的应用研究", r".*的初步研究", r".*的探索性研究",
    ]
    def validate(title: str) -> list[Violation]:
        for pattern in FORBIDDEN_PATTERNS:
            if re.match(pattern, title):
                return [Violation(
                    rule="HR-005",
                    severity="error",
                    message=f"标题匹配禁止模式'{pattern}'，过于宽泛",
                    field="title",
                )]
        return []
  error_message: "标题匹配禁止模式'{pattern}'，过于宽泛"
  repair_suggestion: "采用 reconstruct_noun_phrase 策略，重组为突出核心贡献的名词短语"
```

#### HR-006：学科匹配检查

```yaml
- id: HR-006
  name: 学科匹配检查
  category: hard_rule
  subcategory: discipline
  severity: error
  version: v8.0
  config_key: "hard_rules.yaml#discipline.require_match"
  threshold:
    type: match
    value: true
  scope: discipline
  description: |
    论题必须与用户指定的学科领域匹配。
    学科匹配通过预定义的学科关系映射表判断。
  relations:
    计算机科学:
      - 计算机科学
      - 人工智能
      - 软件工程
      - 数据科学
      - 信息工程
    人工智能:
      - 人工智能
      - 计算机科学
      - 机器学习
      - 深度学习
    医学:
      - 医学
      - 临床医学
      - 生物医学
      - 医疗信息学
    教育学:
      - 教育学
      - 教育技术
      - 心理学
      - 课程与教学论
  error_message: "论题关键词{keywords}与学科'{discipline}'不匹配"
  repair_suggestion: |
    - 调整论题关键词，使其落入目标学科范围
    - 若论题确属交叉学科，在信息确权阶段标注交叉学科
```

#### HR-007：导师方向对齐

```yaml
- id: HR-007
  name: 导师方向对齐
  category: hard_rule
  subcategory: advisor
  severity: warning
  version: v8.0
  config_key: "hard_rules.yaml#advisor.min_alignment_score"
  threshold:
    type: min
    value: 0.3
  alignment_method: keyword_overlap
  scope: advisor
  description: |
    论题应与导师研究方向对齐，对齐度分数不得低于0.3。
    对齐度通过关键词重叠法（Jaccard相似度）计算。
  validation_logic: |
    def calculate_alignment(topic: str, advisor_direction: str) -> float:
        advisor_kw = set(jieba.cut(advisor_direction)) - STOPWORDS
        topic_kw = set(jieba.cut(topic)) - STOPWORDS
        if not advisor_kw or not topic_kw:
            return 0.0
        overlap = advisor_kw & topic_kw
        union = advisor_kw | topic_kw
        return len(overlap) / len(union)
  error_message: "导师方向对齐度{score}低于阈值{min_score}"
  repair_suggestion: |
    - 在论题中融入导师研究方向的关键词
    - 与导师沟通确认论题方向的合理性
```

#### HR-008：时间可行性（硕士）

```yaml
- id: HR-008
  name: 时间可行性（硕士）
  category: hard_rule
  subcategory: calendar
  severity: error
  version: v8.0
  config_key: "hard_rules.yaml#calendar.master_max_months"
  threshold:
    type: max
    value: 12
    unit: 月
  applicable_degree: master
  scope: timeline
  description: |
    硕士论题的研究时间规划不得超过1年（12个月）。
    超过此时间通常意味着论题工作量过大或时间管理不合理。
  error_message: "总时长{total_months}个月超过硕士最大年限12个月"
  repair_suggestion: "采用 inject_parallel_strategy 策略，注入分阶段并行执行策略"
```

#### HR-009：时间可行性（博士）

```yaml
- id: HR-009
  name: 时间可行性（博士）
  category: hard_rule
  subcategory: calendar
  severity: error
  version: v8.0
  config_key: "hard_rules.yaml#calendar.doctor_max_months"
  threshold:
    type: max
    value: 24
    unit: 月
  applicable_degree: doctor
  scope: timeline
  description: "博士论题的研究时间规划不得超过2年（24个月）。"
  error_message: "总时长{total_months}个月超过博士最大年限24个月"
```

#### HR-010：文献数量基线（硕士）

```yaml
- id: HR-010
  name: 文献数量基线（硕士）
  category: hard_rule
  subcategory: literature
  severity: warning
  version: v8.0
  config_key: "hard_rules.yaml#literature.master_min_count"
  threshold:
    type: min
    value: 30
    unit: 篇
  applicable_degree: master
  scope: literature
  description: "硕士论文参考文献数量不得少于30篇。"
  recommended_databases:
    - CNKI
    - WanFang
    - VIP
    - Web of Science
    - Scopus
    - IEEE Xplore
    - ACM Digital Library
    - PubMed
    - arXiv
    - Semantic Scholar
  error_message: "文献数量{count}少于硕士最低要求30篇"
  repair_suggestion: "采用 supplement_search_suggestions 策略，补充子方向检索词与数据库建议"
```

#### HR-011：文献数量基线（博士）

```yaml
- id: HR-011
  name: 文献数量基线（博士）
  category: hard_rule
  subcategory: literature
  severity: warning
  version: v8.0
  config_key: "hard_rules.yaml#literature.doctor_min_count"
  threshold:
    type: min
    value: 50
    unit: 篇
  applicable_degree: doctor
  scope: literature
  description: "博士论文参考文献数量不得少于50篇。"
  error_message: "文献数量{count}少于博士最低要求50篇"
```

#### HR-012：重复度阈值

```yaml
- id: HR-012
  name: 重复度阈值
  category: hard_rule
  subcategory: duplication
  severity: error
  version: v8.0
  config_key: "hard_rules.yaml#duplication.max_similarity"
  threshold:
    max_similarity: 0.3
    min_novelty_score: 60
  risk_thresholds:
    low:
      similarity_max: 0.5
      novelty_min: 70
      action: pass