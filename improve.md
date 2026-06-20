# ThesisMinerSkill — 多平台开题智能体 Skill 集合

> **版本**：V4.0（全生命周期导航版）
> **日期**：2026-06-19
> **设计底座**：ThesisArchitect v4.0 (Full-Journey Navigator Edition)
> **设计理念**：三层物理结构 · 去上下文化 I/O · 自愈兜底 · Token 效率 · 四维创意引擎 · 硬约束自动修复 · 开题直出 · 信息确权 · 降重脱敏 · 去 AI 痕迹 · 深度陪跑

---

## 目录

1. [项目概述](#1-项目概述)
2. [文件结构与职责](#2-文件结构与职责)
3. [三层架构设计](#3-三层架构设计)
4. [技术栈详情](#4-技术栈详情)
5. [核心机制与架构设计](#5-核心机制与架构设计)
6. [Skill 接口/调用清单](#6-skill-接口调用清单)
7. [配置与环境变量](#7-配置与环境变量)
8. [自测](#8-自测)
9. [部署与运行](#9-部署与运行)
10. [扩展性设计](#10-扩展性设计)
11. [常见问题与故障排除（FAQ）](#11-常见问题与故障排除faq)

---

## 1. 项目概述

### 1.1 项目定位

**一句话定义**：ThesisMinerSkill 是一个将平台无关的 ThesisArchitect v2.0 设计文档转译为 5 个主流 AI 平台原生 Skill 格式的多平台技能集合项目，使同一套研究生开题智能体能力可在不同 AI 运行时中即插即用。

- **目标用户**：研究生（硕士/博士）及其导师、需要协助学生完成开题阶段工作的学术辅助人员、希望在自有 AI 平台中部署开题智能体的研发团队。
- **解决的核心问题**：原始设计文档无法被任何具体 AI 运行时直接加载执行；不同平台 Skill 格式规范差异巨大，用户手工二次适配成本高。本项目通过一次性转译，让 ThesisArchitect 的谱系解析、四维创意、硬约束修复、开题直出等能力在 Claude、OpenAI、Cursor、Trae、GitHub Copilot 五大平台原生可用。

### 1.2 核心功能

| 模块 | 功能描述 |
| --- | --- |
| 谱系解析 | 鲁棒性解析非结构化文本，抽取导师项目与同门论文实体，并通过边缘探测标记"未走完的路"作为高价值切入点 |
| 四维创意引擎 | 并行调用导师项目延伸、同门成果继承、跨域联想、矛盾驱动四个策略生成候选论题，并通过自评分（可行性 40% + 创新度 30% + 谱系贴合度 30%）过滤低于 6 分的方向 |
| 硬约束修复 | 对标题格式（≤20 字、无动词前置、杜绝"基于 X 的 Y 研究"）、学术日历（硕士 ≤12 月 / 博士 ≤24 月）、文献基线（硕士 ≥30 篇 / 博士 ≥50 篇）、逻辑自洽（重合度 ≤70%）执行确定性自动修复 |
| 开题直出 | 严格对齐国内双一流高校标准开题模板，强制按"选题依据、国内外研究现状、研究内容与关键问题、研究方案与可行性、进度安排"五大模块填充并直出 Markdown 草稿 |
| I/O 多态 | 摒弃死板文件依赖，按意图识别路由输入（文件/对话/混合）与输出（文件/对话），适配各平台原生交互通道 |
| 多平台分发 | 同一套设计能力转译为 5 个平台原生格式（Claude SKILL.md、OpenAI GPT Instructions、Cursor .mdc、Trae SKILL.md、Copilot instructions.md），各自即插即用 |
| 信息确权与联网勘探 | 解析输入后不直接生成论题，生成检索式联网搜索近2年文献，展示摘要并等待用户确认后解锁四维创意 |
| 重复度评估 | 基于候选标题联网检索近5年硕博论文与期刊，输出新颖性风险评级（low/medium/high）与差异化空档 |
| 多粒度生成 | 支持精简/标准/详实三级颗粒度，按学科需求动态渲染 Markdown 深度与字数阈值 |
| 降重脱敏 | report_generator 输出后强制执行 style_normalizer 去 AI 痕迹（200+禁用词替换、句首过滤、语态互换） |
| 深度辅助闭环 | 报告输出后渲染导航菜单，提供文献精读工作簿/实验预研映射/答辩模拟三件套 |

### 1.3 技术底座

本项目是 **Skill 集合项目**，而非传统应用代码库。项目内除 `core/scripts/` 下 6 个可执行 Python 脚本（供各平台 Skill 按需调用）与 `tests/` 自测脚本外，主体产物均为面向各 AI 平台运行时的指令文本（Markdown / YAML frontmatter / JSON 配置），由底层大模型运行时加载并解释执行。

**支持的 AI 平台**：

| 平台 | 厂商 | 产物形态 |
| --- | --- | --- |
| Claude Code / Anthropic 运行时 | Anthropic | SKILL.md（元数据）+ INSTRUCTION.md（指令） |
| OpenAI Custom GPT | OpenAI | skill.json（元数据）+ gpt-instructions.md（指令）+ config.json |
| Cursor | Anysphere | thesis-architect.mdc（frontmatter 元数据 + 正文指令） |
| Trae IDE | ByteDance | SKILL.md（元数据）+ INSTRUCTION.md（指令） |
| GitHub Copilot Chat | Microsoft/GitHub | skill.json（元数据）+ copilot-instructions.md（指令） |

---

## 2. 文件结构与职责

### 2.1 目录树

```bash
ThesisMinerSkill/
├── core/                           # 共享资源层（平台无关）
│   ├── scripts/                    # 可执行脚本（6个Python文件）
│   │   ├── lineage_parser.py
│   │   ├── idea_generator.py
│   │   ├── constraint_checker.py
│   │   ├── report_generator.py
│   │   ├── style_normalizer.py
│   │   └── deep_helper.py
│   ├── references/                 # 静态参考数据（7个文件）
│   │   ├── constraints.json
│   │   ├── scoring_weights.json
│   │   ├── report_template.md
│   │   ├── prompt_templates.json
│   │   ├── search_strategies.json
│   │   ├── forbidden_ai_phrases.json
│   │   └── output_granularity.yaml
│   └── schema/                     # I/O Schema（2个文件）
│       ├── input_schema.json
│       └── output_schema.json
├── claude-skill/                   # Claude Skill（三层结构）
│   ├── SKILL.md                    # 元数据层
│   ├── INSTRUCTION.md              # 指令层
│   └── README.md
├── openai-skill/                   # OpenAI Skill（三层结构）
│   ├── skill.json                  # 元数据层
│   ├── gpt-instructions.md         # 指令层
│   ├── config.json
│   └── README.md
├── cursor-skill/                   # Cursor Rules（三层结构）
│   ├── thesis-architect.mdc        # 元数据+指令层
│   └── README.md
├── trae-skill/                     # Trae Skill（三层结构）
│   ├── SKILL.md                    # 元数据层
│   ├── INSTRUCTION.md              # 指令层
│   └── README.md
├── copilot-skill/                  # Copilot Instructions（三层结构）
│   ├── skill.json                  # 元数据层
│   ├── copilot-instructions.md     # 指令层
│   └── README.md
├── scripts/                        # 构建脚本
│   └── build-trae-zip.py           # TRAE ZIP 打包脚本
├── tests/                          # 自测（8个测试文件）
│   ├── test_lineage_parser.py
│   ├── test_idea_generator.py
│   ├── test_constraint_checker.py
│   ├── test_report_generator.py
│   ├── test_schema.py
│   ├── test_style_normalizer.py
│   ├── test_deep_helper.py
│   └── test_search_strategies.py
├── ThesisMinerSkills设计文档.md
├── ThesisMinerSkills设计文档V4.0.md
├── TRAE_IMPORT_GUIDE.md
├── Problem.md
├── README.md
└── .gitignore
```

> 另有 `.trae/specs/` 目录承载项目规格文档（`multi-platform-skills/` 与 `skill-arch-refactor/` 各含 spec.md / tasks.md / checklist.md），为开发期产物，不参与运行时加载。

### 2.2 核心文件职责说明

#### 共享资源层 `core/`

| 文件 | 职责唯一性说明 |
| --- | --- |
| `core/scripts/lineage_parser.py` | 唯一的谱系解析脚本，提供 `parse_lineage(text)` 函数，将非结构化文本解析为结构化 `LineageGraph`（导师项目 + 同门论文 + 边缘探测） |
| `core/scripts/idea_generator.py` | 唯一的四维创意引擎脚本，提供 `generate_ideas(lineage_graph, strategy, degree)` 函数，并行执行四策略并自评分过滤 |
| `core/scripts/constraint_checker.py` | 唯一的硬约束校验脚本，提供 `check_and_repair(proposal)` 函数，对标题/学术日历/文献基线/逻辑自洽执行确定性修复 |
| `core/scripts/report_generator.py` | 唯一的开题报告直出脚本，提供 `generate_report(proposal)` 函数，按模板渲染五大模块 Markdown |
| `core/scripts/style_normalizer.py` | 唯一的去 AI 痕迹脚本，提供 `remove_ai_traces(text)` 函数，执行禁用词替换、句首过滤、语态互换 |
| `core/scripts/deep_helper.py` | 唯一的深度辅助脚本，提供 `literature_deep_reader()` / `experiment_designer()` / `thesis_defense_simulator()` 三函数 |
| `core/references/constraints.json` | 唯一的硬约束规则数据源（标题长度、学术日历、文献基线、逻辑自洽阈值），供脚本与指令层引用，避免约束内联到指令文本 |
| `core/references/scoring_weights.json` | 唯一的自评分权重数据源（可行性 40% + 创新度 30% + 谱系贴合度 30%） |
| `core/references/report_template.md` | 唯一的开题报告模板（五大模块骨架），供 `report_generator.py` 填充 |
| `core/references/prompt_templates.json` | 唯一的 Prompt 约束模板集合，供指令层按场景引用 |
| `core/references/search_strategies.json` | 唯一的检索式模板数据源（灵感2年/查重5年默认窗、可调节步长、布尔运算符） |
| `core/references/forbidden_ai_phrases.json` | 唯一的 AI 化术语映射表（200+条），供 style_normalizer 引用 |
| `core/references/output_granularity.yaml` | 唯一的多粒度配置（精简/标准/详实三级 Markdown 深度与字数阈值） |
| `core/schema/input_schema.json` | 唯一的输入 JSON Schema，定义 `degree`、`lineage` 等必填字段与枚举值，去上下文化校验输入 |
| `core/schema/output_schema.json` | 唯一的输出 JSON Schema，标准化 `status` / `data` / `error_message` 结构 |

#### 各平台 Skill 产物

| 文件 | 职责唯一性说明 |
| --- | --- |
| `ThesisMinerSkills设计文档.md` | 唯一的平台无关设计源，定义 ThesisArchitect v2.0 的全部能力与工作流，是所有平台 Skill 产物的转译源头，不被任何运行时直接加载 |
| `claude-skill/SKILL.md` | Claude Skill 元数据层，仅含 `name`/`version`/`description`（≤120 字符）触发条件 |
| `claude-skill/INSTRUCTION.md` | Claude Skill 指令层，定义工作流决策规则、I/O 接口规范与自愈兜底，引用 `../core/` 资源 |
| `openai-skill/skill.json` | OpenAI Skill 元数据层，含 `name`/`version`/`description`/`triggers`/资源指针 |
| `openai-skill/gpt-instructions.md` | OpenAI Skill 指令层，纯 Markdown 指令，引用 `../core/` 资源 |
| `openai-skill/config.json` | GPT 元信息记录文件（非官方导入文件），供团队协作统一 Name/Description/Conversation starters 口径 |
| `cursor-skill/thesis-architect.mdc` | Cursor 规则文件，frontmatter 为元数据层（`description`+`globs`+`alwaysApply`），正文为指令层，引用 `../core/` 资源 |
| `trae-skill/SKILL.md` | Trae Skill 元数据层，由 Trae 启动时扫描 `.trae/skills/` 自动加载 |
| `trae-skill/INSTRUCTION.md` | Trae Skill 指令层，定义工作流决策规则，引用 `../core/` 资源 |
| `copilot-skill/skill.json` | Copilot Skill 元数据层，含触发词与资源指针 |
| `copilot-skill/copilot-instructions.md` | Copilot Skill 指令层，纯 Markdown 指令，引用 `../core/` 资源 |
| `README.md` | 唯一的项目架构文档，面向开发者说明项目定位、文件结构、三层架构、核心机制与部署方式 |
| `.gitignore` | 唯一的 Git 忽略规则，排除 `/output/`、`/input/` 运行时产物与 Python/IDE/OS 缓存 |

---

## 3. V4.0 三层架构设计

V4.0 在 V2.1 三层物理结构基础上扩展资源层，将每个平台 Skill 从单文件结构重构为**三层物理结构**，并配套去上下文化 I/O、自愈兜底与 Token 效率优化，解决旧版"上下文成本高、无法渐进式披露、I/O 无结构化校验、缺乏自愈逻辑"四大痛点。

### 3.1 三层物理结构

每个平台 Skill 采用三层物理结构，职责分明、按需加载。V4.0 在资源层扩充了 `style_normalizer.py`、`deep_helper.py` 两个脚本与 `search_strategies.json`、`forbidden_ai_phrases.json`、`output_granularity.yaml` 三个参考数据文件，以承载信息确权、降重脱敏、多粒度生成与深度辅助闭环四大新能力：

| 层级 | 内容 | 各平台对应文件 |
| --- | --- | --- |
| **元数据层** | 仅含唯一标识（`name`）、版本（`version`）、触发条件（`description` ≤120 字符），供调度系统快速匹配，不含工作流细节 | Claude/Trae：`SKILL.md`；OpenAI/Copilot：`skill.json`；Cursor：`.mdc` frontmatter |
| **指令层** | 定义"遇到 A 情况怎么做，遇到 B 情况如何纠错"的决策规则，引用 `core/` 资源而非内联死知识 | Claude/Trae：`INSTRUCTION.md`；OpenAI：`gpt-instructions.md`；Cursor：`.mdc` 正文；Copilot：`copilot-instructions.md` |
| **资源层** | 承载可执行脚本、静态参考数据与 I/O Schema，仅在执行到对应步骤时按需加载，不在激活时全量注入上下文 | 统一引用 `../core/scripts/`、`../core/references/`、`../core/schema/` |

### 3.2 去上下文化 I/O 接口

摒弃依赖模型记忆传递数据的做法，统一以 JSON Schema 标准化输入输出：

- **输入校验**（`core/schema/input_schema.json`）：定义 `required` 字段（`degree`、`lineage`），明确枚举值（`degree`: master/phd；`strategy`: 四策略 + all；`count`: 1–10；`output_format`: dialogue/file）。模型收到输入后先按 Schema 校验，缺失必填字段则触发"缺失信息引导"。
- **输出标准化**（`core/schema/output_schema.json`）：输出固定包含 `status`（success/retry/error）、`data`（核心结果）、`error_message`（错误码）。模型依据 `status` 自主决定继续 / 重试 / 报错，不靠自然语言猜测执行结果。

### 3.3 自愈与兜底逻辑

指令层与脚本层内置错误处理预案，避免单点失败导致整体中断：

| 场景 | 兜底规则 |
| --- | --- |
| API 调用失败 | 返回 `status: retry`，附带"延迟 2 秒重试"建议，不直接报错中断 |
| 脚本执行超时 | 超过 30 秒触发超时中断，返回 `status: error` + `error_message: "执行超时"` |
| 沙盒执行 | 脚本在受限沙盒中运行，禁止网络访问与文件系统越权写入，仅允许写入 `output/` 目录（`validate_write_path` 强制校验） |
| 脚本异常 | 脚本内置 `try/except` 与重试装饰器，捕获异常后回退到结构化错误输出 |

### 3.4 Token 效率

严格管控上下文成本，避免开场即注入全部内容：

- **精简描述**：元数据层 `description` 收紧至 ≤120 字符（原 ≤200），短小精悍便于调度系统快速匹配。
- **渐进式披露**：脚本与参考数据仅在模型确认"需要执行计算"时主动调用加载，不在 Skill 激活时全量注入上下文；死知识（约束规则、评分权重、模板）下沉至 `core/references/`，由脚本按需读取。

---

## 4. 技术栈详情

本项目主体为面向各 AI 平台的指令文本，另含 `core/scripts/` 下 4 个可执行 Python 脚本与 `tests/` 自测。各平台 Skill 的三层结构格式规范如下：

| 平台 | 元数据层文件 | 指令层文件 | 资源层引用 | 触发机制 |
| --- | --- | --- | --- | --- |
| Claude | `SKILL.md`（YAML frontmatter：`name`+`version`+`description` ≤120 字符） | `INSTRUCTION.md`（Markdown） | `../core/` | 运行时按 `description` 语义匹配自动激活 |
| OpenAI Custom GPT | `skill.json`（JSON：`name`+`version`+`description`+`triggers`） | `gpt-instructions.md`（纯 Markdown，无 frontmatter） | `../core/` | 用户在 ChatGPT 中与 GPT 对话即触发 |
| Cursor | `thesis-architect.mdc` frontmatter（`description`+`globs`+`alwaysApply`） | `thesis-architect.mdc` 正文（Markdown） | `../core/` | 按 `description` 语义 + `globs` 文件模式匹配，`alwaysApply: false` 按需触发 |
| Trae IDE | `SKILL.md`（YAML frontmatter：`name`+`version`+`description`） | `INSTRUCTION.md`（Markdown） | `../core/` | Trae 启动时扫描 `.trae/skills/` 自动加载，按语义触发 |
| GitHub Copilot | `skill.json`（JSON：`name`+`version`+`description`+`triggers`） | `copilot-instructions.md`（纯 Markdown，无 frontmatter） | `../core/` | 工作区存在 `.github/copilot-instructions.md` 时自动注入为系统上下文 |

**`core/scripts/` 技术栈**：Python 3，纯标准库实现（无第三方依赖），每个脚本均内置 `timeout(30)` 超时装饰器与 `validate_write_path` 沙盒写入校验。

**通用约定**：所有平台产物在能力层面等价，均完整承载谱系解析、四维创意引擎、硬约束修复、开题直出、I/O 多态自适应五大核心能力，差异仅在外层格式包装与触发语法。

---

## 5. 核心机制与架构设计

### 5.1 系统架构分层图

```text
┌─────────────────────────────────────────────────────────────────┐
│                    设计文档层（平台无关）                          │
│                                                                 │
│   ThesisMinerSkills设计文档.md  (ThesisArchitect v2.0)          │
│   ─────────────────────────────────────────────                 │
│   定义：谱系解析 / 四维创意 / 硬约束修复 / 开题直出 / I/O 多态     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │  一次性转译（保留能力等价性）
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│              core/ 共享资源层（平台无关）                          │
│                                                                 │
│   scripts/   lineage_parser / idea_generator /                  │
│              constraint_checker / report_generator              │
│   references/ constraints / scoring_weights /                   │
│              report_template / prompt_templates                 │
│   schema/    input_schema / output_schema                       │
│   ─────────────────────────────────────────────                 │
│   去上下文化 I/O · 自愈兜底 · 渐进式披露                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │  各平台三层 Skill 引用 ../core/
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│            各平台三层 Skill 产物层                                 │
│                                                                 │
│  元数据层 + 指令层 + 资源层引用（../core/）                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ claude-skill │ │ openai-skill │ │ cursor-skill │            │
│  │SKILL.md+INST │ │skill.json+   │ │thesis-arch.  │            │
│  │RUCTION.md    │ │gpt-instruct. │ │.mdc          │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│  ┌──────────────┐ ┌──────────────┐                              │
│  │  trae-skill  │ │copilot-skill │                              │
│  │SKILL.md+INST │ │skill.json+   │                              │
│  │RUCTION.md    │ │copilot-inst. │                              │
│  └──────────────┘ └──────────────┘                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │  部署到各平台运行时（skill 目录 + core/ 同级）
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                AI 平台运行时层                                    │
│                                                                 │
│  Claude Code | ChatGPT | Cursor | Trae IDE | GitHub Copilot     │
│  （由运行时原生托管：多轮对话状态、上下文窗口、Token 账单）        │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 I/O 标准化流程

去上下文化 I/O 的端到端流转，输入输出均经 JSON Schema 校验，脚本执行结果以标准化结构回传：

```text
┌──────────────┐
│  用户输入     │  degree / lineage / strategy / count / output_format
│（对话/文件）  │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────┐
│  input_schema.json 校验       │  必填字段 + 枚举值校验
│  缺失 → 缺失信息引导补齐      │  不达标 → 提问补齐，不凭空假设
└──────┬───────────────────────┘
       │  校验通过
       ▼
┌──────────────────────────────┐
│  core/scripts/ 脚本执行       │  parse_lineage → generate_ideas
│  （沙盒 + 30s 超时 + 重试）   │  → check_and_repair → generate_report
└──────┬───────────────────────┘
       │  执行结果
       ▼
┌──────────────────────────────┐
│  output_schema.json 标准化    │  status: success / retry / error
│  输出包装                     │  data: proposals / report
│                              │  error_message: 错误码（retry/error 时）
└──────┬───────────────────────┘
       │
       ├─ success → 对话输出 Markdown / 文件写入 output/
       ├─ retry   → 延迟 2 秒重试
       └─ error   → 返回错误码中断
```

### 5.3 核心业务流程

ThesisArchitect v4.0 的核心业务流程从 V2.1 的线性六步工作流升级为**五阶段闭环导航流**，每个阶段对应 `core/scripts/` 下可执行脚本或运行时联网检索能力，所有平台产物均按此顺序执行：

1. **阶段一：信息确权与双时域联网勘探**：解析用户输入后不直接生成论题，先按 `input_schema.json` 校验学位与谱系信息，再依据 `search_strategies.json` 生成检索式，联网搜索近2年文献并展示摘要。**强制中断等待用户确认**（Rule 7 信息确权门禁）后，方解锁阶段二的四维创意生成。若用户跳过确认直接要求生成，触发 Rule 8 时间窗口交互兜底。
2. **阶段二：谱系解析与四维创意生成**：调用 `lineage_parser.py` 的 `parse_lineage(text)` 构建 `LineageGraph`（实体抽取 + 边缘探测），并将阶段一检索到的热点文献作为 `search_feeds` 种子语料注入 `idea_generator.py` 的 `generate_ideas(lineage_graph, strategy, degree, search_feeds)`，并行执行四策略生成候选，按 `scoring_weights.json` 自评分过滤 < 6 分方向，保留 Top 3–5。
3. **阶段三：重复度评估与硬约束修复**：调用 `constraint_checker.py` 新增的 `check_novelty(candidate_title, time_window)` 方法，基于候选标题联网检索近5年硕博论文与期刊，输出新颖性风险评级（low/medium/high）与差异化空档；随后执行 `check_and_repair(proposal)` 对标题格式、学术日历、文献基线、逻辑自洽四类硬约束做确定性修复。
4. **阶段四：多粒度开题生成与降重脱敏**：调用 `report_generator.py` 的 `generate_report(proposal, granularity, style_neutral)`，按 `output_granularity.yaml` 配置渲染精简/标准/详实三级 Markdown 深度；输出后强制执行 `style_normalizer.py` 的 `remove_ai_traces(text)` 去 AI 痕迹（Rule 9 降重去 AI 化优先级，禁用词替换、句首过滤、语态互换）。
5. **阶段五：深度辅助与实验映射闭环**：报告输出后渲染导航菜单，调用 `deep_helper.py` 的 `literature_deep_reader()` / `experiment_designer()` / `thesis_defense_simulator()` 三件套，进入 Rule 10 后置交互循环，提供文献精读工作簿、实验预研映射、答辩模拟直至用户主动结束。

### 5.4 I/O 多态自适应

#### 输入路由（按优先级）

| 优先级 | 输入模式 | 触发条件 | 处理方式 |
| --- | --- | --- | --- |
| 1 | 文件输入 | 用户指令含 `@input/` 或运行时检测到 `/input/profile.json` 与 `/input/lineage.md` | 优先读取文件内容作为基础上下文 |
| 2 | 对话输入 | 未提供文件 | 通过对话引导获取学位、学科、导师项目、同门论文摘要 |
| 3 | 混合输入 | 文件 + 对话追加指令 | 以文件为背景底座，叠加对话中的临时修正（如"换方向做大模型"） |
| 4 | 缺失信息引导 | 关键信息缺失 | 在生成提案前用简短提问补齐，不凭空假设 |

#### 输出路由

| 输出模式 | 触发条件 | 产物 |
| --- | --- | --- |
| 对话输出（默认） | 默认模式或用户未明确要求保存 | 高可读性 Markdown 直接打印在对话框 |
| 文件输出 | 用户指令含"保存""生成文件""输出到本地""写入"等意图 | `output/proposals_<timestamp>.json` 与 `output/draft_<timestamp>.md`，并在对话回复路径摘要 |

### 5.5 四维创意引擎

#### 四个策略

| 策略 | 核心思路 | 示例 |
| --- | --- | --- |
| 导师项目延伸 | 将大项目拆解为可在规定学制内完成的子课题 | "医疗大模型研发" → "特定科室的问询微调" |
| 同门成果继承 | 基于边缘探测的局限点，引入新变量或迁移至新场景 | 同门在英文问诊做微调 → 继承到中文小样本场景 |
| 跨域联想 | 识别多个不相关学科概念，生成"A 领域方法解 B 领域问题"候选 | 用强化学习反馈机制优化医疗问诊的安全对齐 |
| 矛盾驱动挖掘 | 检测"现有方法能力边界"与"实际需求"的语义矛盾，基于矛盾生成论题 | 需要高精度但现有方法在噪声下失效 → 噪声鲁棒性论题 |

#### 自评分机制

每个候选生成后，按以下公式打分（满分 10 分，权重来自 `core/references/scoring_weights.json`）：

```text
总分 = 可行性 × 0.4 + 创新度 × 0.3 + 谱系贴合度 × 0.3
```

- **可行性**：学制内可完成度、数据/算力可获得性、技术成熟度
- **创新度**：与同门已有工作的差异化程度、方法新颖性
- **谱系贴合度**：与导师项目目标的对齐程度、对边缘点的承接程度

**过滤规则**：总分低于 6 分的候选直接丢弃，不向用户展示；最终保留 Top 3–5 个方向。

### 5.6 硬约束校验与自动修复

约束规则集中定义于 `core/references/constraints.json`，由 `constraint_checker.py` 的 `check_and_repair(proposal)` 执行：

| 约束类型 | 约束规则 | 自动修复方式 |
| --- | --- | --- |
| 标题格式 | ≤20 字（中文按 1 字计）；不以"研究/分析/探讨/设计/构建/实现"等主动动词开头；不匹配"基于 X 的 Y 研究"套路 | 超长标题执行依存句法截取核心名词短语；动词前置结构转换为名词性短语（"研究 X" → "X 的研究"）；"基于 X 的 Y 研究"模式改写为突出核心贡献的名词短语 |
| 学术日历 | 研究周期硕士 ≤12 个月，博士 ≤24 个月 | 超期不熔断，在"研究内容"中自动注入"分阶段并行执行"的降级策略提示，并调整进度安排 |
| 文献基线 | 综述大纲至少规划硕士 30 篇 / 博士 50 篇文献的检索方向 | 规划不足时自动补充子方向检索词与数据库建议，直至达到基线 |
| 逻辑自洽 | "研究内容"与"研究目标"语义重合度 ≤70% | 重合度 > 70% 时标记 `WARNING: 内容与目标重合度过高`，提示用户区分"做什么"与"达成什么" |

### 5.7 五阶段闭环导航流详解

V4.0 将 V2.1 的线性六步流重构为五阶段闭环导航流，完整数据流转全景图详见 `ThesisMinerSkills设计文档V4.0.md`。各阶段关键节点如下：

#### 阶段一：信息确权门禁（Rule 7 / Rule 8）

- **门禁触发**：解析输入后不直接进入创意生成，先按 `search_strategies.json` 的 `inspiration_window`（默认近2年）生成检索式，由运行时联网检索并展示文献摘要。
- **强制中断**：展示摘要后**必须中断**，等待用户确认（"继续"/"调整检索式"/"换方向"）后才解锁阶段二。此为 Rule 7 信息确权门禁的硬性要求。
- **时间窗口交互**（Rule 8）：若用户跳过确认直接要求生成论题，运行时不直接拒绝，而是按 Rule 8 时间窗口交互兜底——先回放已检索摘要并提示"未确认将基于默认热点生成"，再进入阶段二。

#### 阶段二：search_feeds 注入

- 阶段一确认后，将检索到的热点文献标题/摘要封装为 `search_feeds` 列表。
- `idea_generator.py` 的 `generate_ideas(lineage_graph, strategy, degree, search_feeds)` 接收 `search_feeds` 作为种子语料，与 `LineageGraph` 的边缘探测点一起作为四策略的输入源，提升候选论题的时效性与差异化程度。
- `search_feeds=None` 时退化为 V2.1 行为（仅基于谱系图生成），保证向后兼容。

#### 阶段三：check_novelty 重复度评估

- 对每个候选标题调用 `constraint_checker.py` 新增的 `check_novelty(candidate_title, time_window)` 方法。
- `time_window` 默认取 `search_strategies.json` 的 `novelty_window`（默认近5年），覆盖硕博论文与期刊两个来源。
- 输出 `novelty_risk`（low/medium/high）与 `differentiation_gaps`（差异化空档列表）。`high` 风险候选会被降权或要求用户确认后保留。
- 评估完成后继续执行 `check_and_repair(proposal)` 做硬约束修复。

#### 阶段四：多粒度生成 + style_normalizer 去 AI 痕迹（Rule 9）

- `report_generator.py` 的 `generate_report(proposal, granularity, style_neutral)` 按 `output_granularity.yaml` 渲染：
  - `concise`（精简）：markdown_depth=2，仅保留核心模块与关键论点。
  - `standard`（标准）：markdown_depth=3，对齐 V2.1 默认模板深度。
  - `detailed`（详实）：markdown_depth=4，追加风险矩阵、预期成果等 #### 级子节。
- **Rule 9 降重去 AI 化优先级**：`style_neutral=True` 时，`generate_report` 内部先渲染 Markdown，再调用 `style_normalizer.remove_ai_traces(text)` 执行禁用词替换（200+条，来自 `forbidden_ai_phrases.json`）、句首过滤、语态互换。style_normalizer 优先级高于排版，但仅替换文本内容，不破坏 Markdown 结构。

#### 阶段五：深度辅助三件套（Rule 10 后置交互循环）

- 报告输出后渲染导航菜单，进入 Rule 10 后置交互循环，提供三个深度辅助入口：
  - `literature_deep_reader(research_status, count)`：基于研究现状生成文献精读工作簿（含阅读顺序、关键问题、对比矩阵）。
  - `experiment_designer(research_content, discipline)`：基于研究内容与学科生成实验预研映射（含变量、对照组、数据集建议）。
  - `thesis_defense_simulator(key_problems, rounds)`：基于关键问题生成答辩模拟轮次（含评委视角提问、参考回答、追问预案）。
- 循环不主动结束，用户可反复调用任一入口或返回上一阶段，直至用户主动结束对话。

### 5.8 阻断性规则（Rule 7–10）

V4.0 在 V2.1 既有规则基础上新增四条阻断性规则，确保五阶段闭环导航流不被绕过：

| 规则 | 名称 | 触发条件 | 阻断行为 |
| --- | --- | --- | --- |
| **Rule 7** | 信息确权门禁 | 解析输入后未执行联网检索、未展示文献摘要、未等待用户确认即进入创意生成 | 阻断阶段二执行，回退到阶段一补全检索与摘要展示，强制等待用户确认 |
| **Rule 8** | 时间窗口交互 | 用户跳过确认直接要求生成，或检索时间窗口未按 `search_strategies.json` 配置（灵感2年/查重5年） | 不直接拒绝，先回放已检索摘要并提示"未确认将基于默认热点生成"，再按配置时间窗口补全检索 |
| **Rule 9** | 降重去 AI 化优先级 | `generate_report` 输出后未调用 `style_normalizer.remove_ai_traces`，或 style_normalizer 优先级低于排版 | 阻断最终输出，强制在 Markdown 渲染后调用 remove_ai_traces，确保 200+禁用词替换、句首过滤、语态互换执行完毕 |
| **Rule 10** | 后置交互循环 | 报告输出后直接结束对话，未渲染深度辅助导航菜单 | 阻断对话结束，强制渲染文献精读/实验预研/答辩模拟三件套导航菜单，进入后置交互循环等待用户选择 |

---

## 6. Skill 接口/调用清单

### 6.1 五平台 Skill 总览（含三层结构）

| 平台 | 元数据层 | 指令层 | 资源层 | 部署位置 | 触发方式 |
| --- | --- | --- | --- | --- | --- |
| Claude | `claude-skill/SKILL.md`（YAML frontmatter） | `claude-skill/INSTRUCTION.md` | `../core/` | `~/.claude/skills/thesis-architect/`（含 `SKILL.md`+`INSTRUCTION.md`），`core/` 置于同级 `~/.claude/skills/core/` | 运行时按 `description` 语义匹配自动激活 |
| OpenAI Custom GPT | `openai-skill/skill.json` | `openai-skill/gpt-instructions.md` | `../core/` | GPT Builder 的 Instructions 字段粘贴 `gpt-instructions.md` 全文；`skill.json` 为团队协作参考 | 用户在 ChatGPT 中与 GPT 对话即触发 |
| Cursor | `cursor-skill/thesis-architect.mdc` frontmatter | `cursor-skill/thesis-architect.mdc` 正文 | `../core/` | 项目根目录 `.cursor/rules/thesis-architect.mdc`，`core/` 置于项目根目录 | 按 `description` 语义 + `globs` 文件模式匹配，`alwaysApply: false` 按需触发 |
| Trae IDE | `trae-skill/SKILL.md`（YAML frontmatter） | `trae-skill/INSTRUCTION.md` | `../core/` | `<项目根目录>/.trae/skills/thesis-architect/`（含 `SKILL.md`+`INSTRUCTION.md`），`core/` 置于项目根目录 | Trae 启动时扫描 `.trae/skills/` 自动加载，按语义触发 |
| GitHub Copilot | `copilot-skill/skill.json` | `copilot-skill/copilot-instructions.md` | `../core/` | 项目根目录 `.github/copilot-instructions.md`，`core/` 置于项目根目录 | 工作区存在该文件时，Copilot Chat 自动注入为系统上下文 |

### 6.2 core/ 脚本接口表

| 脚本 | 函数 | 输入 | 输出 |
| --- | --- | --- | --- |
| `core/scripts/lineage_parser.py` | `parse_lineage(text)` | 非结构化谱系文本（导师项目 + 同门论文描述） | `LineageGraph`：`{advisor_projects, peer_papers, edge_opportunities}` |
| `core/scripts/idea_generator.py` | `generate_ideas(lineage_graph, strategy, degree, search_feeds)` | `LineageGraph` + 策略（advisor_extension/peer_inheritance/cross_domain/contradiction_driven/all）+ 学位（master/phd）+ `search_feeds`（阶段一检索热点，可选，默认 None） | 候选提案列表（含 `title`/`score` 等字段，已过滤 < 6 分） |
| `core/scripts/constraint_checker.py` | `check_and_repair(proposal)` / `check_novelty(candidate_title, time_window)` | 单个提案 dict / 候选标题 + 时间窗口（默认近5年） | 修复后提案 + `WARNING` 标记 / 新颖性风险评级（low/medium/high）+ 差异化空档 |
| `core/scripts/report_generator.py` | `generate_report(proposal, granularity, style_neutral)` | 最优提案 dict + 颗粒度（concise/standard/detailed）+ 是否降重（True/False） | 开题报告 Markdown（五大模块，按粒度渲染）+ 文件输出路径（文件模式下） |
| `core/scripts/style_normalizer.py` | `remove_ai_traces(text)` | 待处理文本 | 标准化输出（normalized_text + replacements_count + high_risk_sections） |
| `core/scripts/deep_helper.py` | `literature_deep_reader(research_status, count)` / `experiment_designer(research_content, discipline)` / `thesis_defense_simulator(key_problems, rounds)` | 研究现状/内容/关键问题 | 文献精读工作簿/实验预研方案/答辩模拟轮次 |

> 所有脚本均内置 `timeout(30)` 超时装饰器与 `validate_write_path` 沙盒写入校验（仅允许写 `output/`），异常时返回符合 `output_schema.json` 的结构化错误。

### 6.3 各平台调用示例

#### Claude（Claude Code 运行时）

```text
用户：我是硕士生，导师在做医疗大模型，同门做的是问诊微调。帮我生成3个论题。
SKILL 动作：解析对话提取谱系 → 调用 idea_generator 执行四维创意 → 对话框直接输出 3 个结构化提案。

用户：读取 @input/profile.json 和 @input/lineage.md，基于这些信息帮我生成开题报告草稿，直接发给我。
SKILL 动作：读取 /input/ 文件 → parse_lineage 解析谱系 → 生成提案并选最优 → generate_report 直出完整 Markdown 开题报告。

用户：读取 @input/ 里的背景，但我现在想结合最新的 RAG 技术做跨域联想。生成5个提案，保存到本地。
SKILL 动作：读取文件底座 + 追加 RAG 跨域指令 → 生成提案 → 写入 /output/proposals_<timestamp>.json 与 draft_<timestamp>.md，回复"已保存至该路径"。
```

#### OpenAI Custom GPT（ChatGPT）

```text
用户：我是硕士生，导师在做医疗大模型，帮我生成3个论题。
GPT 动作：解析对话提取谱系 → 执行四维创意 → 对话框输出 3 个结构化提案。

用户：读取我上传的导师项目书和同门论文，生成开题报告草稿。
GPT 动作：读取上传文件解析谱系 → 生成提案并选最优 → 对话框直出完整 Markdown 开题报告（若启用 Code Interpreter 可生成可下载文件）。

用户：基于我粘贴的谱系信息，用跨域联想策略生成5个提案并保存为文件。
GPT 动作：解析粘贴谱系 → 跨域联想生成 5 个提案 → 通过 Code Interpreter 生成 proposals_<timestamp>.json 供下载。
```

#### Cursor（编辑器内对话）

```text
用户：我是硕士生，导师在做医疗大模型，同门做的是问诊微调。帮我生成 3 个论题。
规则动作：解析对话提取谱系 → 执行四维创意 → 对话框直接输出 3 个结构化提案。

用户：读取 @input/profile.json 和 @input/lineage.md，基于这些信息帮我生成开题报告草稿，直接发给我。
规则动作：读取工作区文件解析谱系 → 生成提案并选最优 → 对话框直出完整 Markdown 开题报告。

用户：读取 @input/ 里的背景，但我现在想结合最新的 RAG 技术做跨域联想。生成 5 个提案，保存到本地。
规则动作：读取工作区文件底座 + 追加 RAG 跨域指令 → 生成提案 → 写入 output/proposals_<日期>.json 与 output/draft_<日期>.md，回复"已保存至该路径"。
```

#### Trae IDE（编辑器内对话）

```text
用户：我是硕士生，导师在做医疗大模型，同门做的是问诊微调。帮我生成3个论题。
技能动作：解析对话提取谱系 → 执行四维创意 → 对话框直接输出 3 个结构化提案。

用户：读取 @input/profile.json 和 @input/lineage.md，基于这些信息帮我生成开题报告草稿，直接发给我。
技能动作：读取文件解析谱系 → 生成提案并选最优 → 对话框直出完整 Markdown 开题报告。

用户：读取 @input/ 里的背景，但我现在想结合最新的 RAG 技术做跨域联想。生成5个提案，保存到本地。
技能动作：读取文件底座 + 追加 RAG 跨域指令 → 生成提案 → 写入 /output/proposals_<timestamp>.json，回复"已保存至该路径"。
```

#### GitHub Copilot Chat

```text
用户：我是硕士生，导师在做医疗大模型，同门做的是问诊微调。帮我生成 3 个论题。
Copilot 动作：解析对话提取谱系 → 执行四维创意 → Chat 中直接输出 3 个结构化提案。

用户：读取 @input/profile.json 和 @input/lineage.md，基于这些信息帮我生成开题报告草稿，直接发给我。
Copilot 动作：读取工作区文件解析谱系 → 生成提案并选最优 → Chat 中直出完整 Markdown 开题报告。

用户：读取 @input/ 里的背景，但我现在想结合最新的 RAG 技术做跨域联想。生成 5 个提案，保存到本地。
Copilot 动作：读取工作区文件底座 + 追加 RAG 跨域指令 → 生成提案 → 写入 output/proposals_YYYYMMDD.md，回复"已保存至该路径"。
```

---

## 7. 配置与环境变量

本项目不含传统环境变量配置（无 `.env`、无运行时配置文件）。各平台 Skill 的配置方式如下：

### 7.1 OpenAI Custom GPT — `config.json`

`openai-skill/config.json` 是 GPT 元信息记录文件（**非 OpenAI 官方导入文件**，Custom GPT Builder 不提供 JSON 批量导入入口），供团队协作时统一配置口径。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | string | GPT 名称（如 `ThesisArchitect`） |
| `description` | string | 简短描述（粘贴至 GPT Builder 的 Description 字段） |
| `capabilities` | string[] | 能力清单：`谱系解析`、`四维创意生成`、`硬约束校验`、`开题报告直出` |
| `suggested_starters` | string[] | 3–5 个建议开场白，可粘贴至 Conversation starters |

### 7.2 元数据层字段（skill.json / SKILL.md / .mdc frontmatter）

各平台元数据层字段统一精简，`description` 收紧至 ≤120 字符：

| 平台 | 文件 | 字段 |
| --- | --- | --- |
| Claude / Trae | `SKILL.md` frontmatter | `name`、`version`、`description`（≤120 字符） |
| OpenAI / Copilot | `skill.json` | `name`、`version`、`description`、`triggers`（触发词数组）、`instruction_file`、`resources`（指向 `../core/` 的脚本/参考/Schema 路径） |
| Cursor | `thesis-architect.mdc` frontmatter | `description`、`globs`（`**/*.md`）、`alwaysApply`（`false`） |

### 7.3 运行时目录约定（非配置文件）

各平台 Skill 在运行时依赖以下约定目录（由用户在使用时创建，已纳入 `.gitignore` 忽略）：

| 目录 | 用途 | 创建时机 |
| --- | --- | --- |
| `/input/` | 放置谱系输入文件（`profile.json`、`lineage.md`） | 用户按需创建 |
| `/output/` | 文件输出落盘目录（`proposals_<timestamp>.json`、`draft_<timestamp>.md`），沙盒唯一允许写入路径 | Skill 在文件输出模式下自动创建 |

---

## 8. 自测

`tests/` 目录对 `core/scripts/` 下 6 个脚本、`core/schema/` 下 2 个 Schema 与 `core/references/` 下检索策略配置进行自测，共 **63 个测试用例**，覆盖核心计算路径与边界场景。

### 8.1 测试文件清单

| 测试文件 | 覆盖目标 | 用例数 |
| --- | --- | --- |
| `tests/test_lineage_parser.py` | `parse_lineage()`：导师项目抽取、同门论文抽取、边缘探测、空输入、标准输出 | 5 |
| `tests/test_idea_generator.py` | `generate_ideas()`：四策略各 1 例 + 自评分过滤 + all 策略 + search_feeds 注入（V4.0 新增 3 例） | 9 |
| `tests/test_constraint_checker.py` | `check_and_repair()`：标题超长/动词前置/套路模式、学术日历、文献基线、逻辑自洽 + `check_novelty()` 重复度评估（V4.0 新增 4 例） | 10 |
| `tests/test_report_generator.py` | `generate_report()`：五大模块、模板填充、文件输出、标准输出 + granularity 多粒度与 style_neutral 降重（V4.0 新增 6 例） | 10 |
| `tests/test_schema.py` | `input_schema.json` / `output_schema.json`：合法性、必填字段、枚举值、status 枚举、样例数据校验 + V4.0 字段验证（新增 5 例） | 12 |
| `tests/test_style_normalizer.py` | `remove_ai_traces()`：禁用词替换、句首过滤、语态互换、high_risk_sections 标记、Markdown 结构保留 | 8 |
| `tests/test_deep_helper.py` | `literature_deep_reader()` / `experiment_designer()` / `thesis_defense_simulator()` 三函数输出结构与字段校验 | 6 |
| `tests/test_search_strategies.py` | `search_strategies.json`：灵感2年/查重5年默认窗、布尔运算符、可调节步长配置合法性 | 3 |

### 8.2 运行方式

在项目根目录执行（需 Python 3 + pytest）：

```bash
python -m pytest tests/ -v
```

预期输出：63 个用例全部通过（`63 passed`）。测试不依赖第三方包以外的网络与外部服务，脚本沙盒写入仅落在临时 `output/` 目录。

---

## 9. 部署与运行

> **关键原则（三层结构）**：每个平台部署时需**同时复制 skill 目录与 `core/` 目录**，并保持两者同级，以确保指令层中 `../core/` 相对路径有效。`core/` 为 5 个平台共享，只需部署一份。

### 9.1 Claude Skill 部署

1. 将 `claude-skill/` 目录（含 `SKILL.md` + `INSTRUCTION.md`）与 `core/` 目录**一同**复制到 Claude 运行时的 `/skills/` 目录下，保持两者同级：
   - 用户级：`~/.claude/skills/thesis-architect/`（skill）+ `~/.claude/skills/core/`（资源层）
   - 项目级：`<项目根目录>/.claude/skills/thesis-architect/` + `<项目根目录>/.claude/skills/core/`
2. 重启 Claude 运行时，使其在启动时自动加载 `SKILL.md` 的 frontmatter（`name`/`version`/`description`）。`INSTRUCTION.md` 与 `core/` 资源按需加载，不在开场全量注入。
3. 加载成功后，当用户请求涉及"生成论文选题 / 开题报告 / 分析导师项目谱系 / 同门论文"等意图时，Claude 将按 `description` 中的触发条件自动激活本技能。

### 9.2 OpenAI Custom GPT 部署

1. 登录 ChatGPT，进入 **Explore GPTs** → **+ Create** 进入 GPT Builder。
2. 在 **Configure** 标签页填写：
   - **Name**：`ThesisArchitect`
   - **Description**：`研究生开题智能导师，解析谱系、四维创意、硬约束修复、开题直出`
3. 将 `gpt-instructions.md` 的**全部内容**复制粘贴至 **Instructions** 文本框（本文件已是纯 Markdown 指令，可直接粘贴）。
4. **Conversation starters**：从 `config.json` 的 `suggested_starters` 字段中挑选 3–5 条粘贴进去。
5. 若需要文件读写能力，在 **Actions** 中按需配置文件服务 OpenAPI；若仅需生成可下载文件，启用 **Code Interpreter** 即可。
6. 点击 **Save** → 选择发布范围（Only me / Anyone with link / Public）。
7. `skill.json` 为团队协作参考（非官方导入文件），`core/` 资源层在 ChatGPT 环境下通过 Code Interpreter 或 Actions 间接调用，部署时记录其相对路径口径即可。

### 9.3 Cursor Rules 部署

1. 在目标项目中创建（或确认已存在）`.cursor/rules/` 目录。
2. 将 `thesis-architect.mdc` 复制到 `.cursor/rules/thesis-architect.mdc`。
3. 将 `core/` 目录复制到项目根目录，保持 `../core/` 相对路径有效（即 `.cursor/rules/thesis-architect.mdc` 引用的 `../core/` 指向项目根目录的 `core/`）。
4. 重启 Cursor 或等待其自动加载规则文件。规则加载后会在状态栏 / Rules 面板中可见。
5. 因 `alwaysApply: false`，规则按需触发，不会在每次对话都强制注入，避免污染无关代码任务。

### 9.4 Trae Skill 部署

1. 将 `trae-skill/` 目录内容（含 `SKILL.md` + `INSTRUCTION.md`）复制到 Trae IDE 工作区 Skill 目录，`core/` 复制到项目根目录，保持两者同级：
   ```
   <项目根目录>/
   ├── .trae/skills/thesis-architect/
   │   ├── SKILL.md              # 元数据层
   │   └── INSTRUCTION.md        # 指令层
   └── core/                     # 资源层（共享，../core/ 相对路径有效）
   ```
2. **自动加载**：Trae IDE 在启动时会扫描 `.trae/skills/` 目录，自动加载其中的 `SKILL.md`，解析 frontmatter 中的 `name` 与 `description` 字段。`INSTRUCTION.md` 与 `core/` 资源按需加载。无需手动注册或重启编辑器之外的步骤。
3. **验证加载**：启动 Trae IDE 后，在对话窗口中输入与开题相关的指令（如"帮我生成3个论题"），若技能被正确加载，模型会按 ThesisArchitect 工作流执行。

### 9.5 GitHub Copilot Chat 部署

**方式一：项目级自定义指令（推荐）**

1. 在项目根目录创建 `.github/` 目录（若不存在）。
2. 将 `copilot-instructions.md` 的全部内容复制到 `.github/copilot-instructions.md`。
3. 将 `core/` 目录复制到项目根目录，保持 `../core/` 相对路径有效。
4. GitHub Copilot Chat 会**自动读取**该文件作为项目级自定义指令，无需任何额外配置。
5. 在 Copilot Chat 中讨论论文选题/开题时，ThesisArchitect 行为自动激活。

**方式二：VS Code 设置级指令**

若希望指令在所有项目中生效，可通过 VS Code 设置配置：

1. 打开 VS Code 设置（`Ctrl+,` / `Cmd+,`）。
2. 搜索 `github.copilot.chat.codeGeneration.instructions`。
3. 点击"在 settings.json 中编辑"，按以下格式添加指令项：

```json
{
  "github.copilot.chat.codeGeneration.instructions": [
    {
      "text": "<将 copilot-instructions.md 全文粘贴于此>"
    }
  ]
}
```

---

## 10. 扩展性设计

### 10.1 如何添加新平台 Skill 格式

当需要将 ThesisArchitect 能力扩展到新的 AI 平台（如 Windsurf、Continue、Cline 等）时，按以下步骤操作：

1. **创建独立目录**：在项目根目录创建 `<平台名>-skill/` 目录（如 `windsurf-skill/`），与现有 5 个平台目录平级，采用三层结构（元数据层 + 指令层 + README）。
2. **研究目标平台格式规范**：确认该平台 Skill 的原生格式要求（是否需要 frontmatter、frontmatter 字段名、文件命名约定、部署路径）。
3. **转译能力正文**：以 `ThesisMinerSkills设计文档.md` 为唯一能力源头，将五大核心能力（谱系解析、四维创意引擎、硬约束修复、开题直出、I/O 多态自适应）转译为目标平台格式，保持能力等价性。指令层引用 `../core/` 资源，不内联死知识。
4. **适配 I/O 通道**：根据目标平台原生交互能力调整 I/O 路由描述（如该平台是否支持文件读写、是否支持上传文件），输入输出仍遵循 `core/schema/` 的 JSON Schema。
5. **编写部署说明**：在 `<平台名>-skill/README.md` 中说明部署路径（含 `core/` 同级复制）、触发机制与调用示例。
6. **更新本 README**：在第 2.1 节目录树、第 4 节技术栈表格、第 6.1 节 Skill 总览表格中补充新平台条目。
7. **更新 spec**：在 `.trae/specs/skill-arch-refactor/spec.md` 中补充新平台的三层结构 Requirement 与 Scenario。

### 10.2 如何更新核心能力

当需要修改 ThesisArchitect 的核心能力（如新增创意策略、调整硬约束规则、修改开题模板）时，按以下顺序操作，确保所有平台产物同步演进：

1. **修改设计文档**：在 `ThesisMinerSkills设计文档.md` 中更新能力定义（这是唯一的能力源头）。
2. **更新 core/ 资源层**：若涉及约束规则、评分权重、模板或脚本逻辑，先更新 `core/references/` 数据与 `core/scripts/` 脚本（这是 5 个平台共享的单一数据源）。
3. **逐平台重新转译指令层**：依次更新 5 个平台目录下的指令层文件（`claude-skill/INSTRUCTION.md`、`openai-skill/gpt-instructions.md`、`cursor-skill/thesis-architect.mdc`、`trae-skill/INSTRUCTION.md`、`copilot-skill/copilot-instructions.md`），保持能力等价性。
4. **更新自测**：在 `tests/` 下同步更新对应测试用例，运行 `python -m pytest tests/ -v` 确认通过。
5. **更新平台 README**：若能力变化影响部署或调用示例，同步更新各平台目录下的 `README.md`。
6. **更新本 README**：在第 5 节核心机制、第 6 节调用示例中同步更新。
7. **更新 spec 验收清单**：在 `.trae/specs/skill-arch-refactor/` 下更新对应 Requirement 与 Scenario，确保验收依据与实际能力一致。

> **关键原则**：任何能力变更必须先改设计文档与 `core/` 资源层，再同步转译到所有平台指令层，禁止直接修改单个平台产物而绕过设计文档与共享资源层，以避免跨平台能力漂移。

---

## 11. 常见问题与故障排除（FAQ）

| 问题 | 可能原因 | 解决方案 |
| --- | --- | --- |
| Claude 运行时未识别 Skill | `SKILL.md` 未放置在 `/skills/` 目录下，或 frontmatter 缺少 `name`/`description` 字段 | 确认部署路径为 `~/.claude/skills/thesis-architect/SKILL.md` 或项目级 `.claude/skills/thesis-architect/SKILL.md`；检查 frontmatter 字段完整且 `description` ≤120 字符 |
| 指令层引用 `../core/` 失效 | 部署时未将 `core/` 与 skill 目录同级复制 | 三层结构要求 skill 目录与 `core/` 同级部署，确保 `../core/` 相对路径有效；参见第 9 节各平台部署说明 |
| OpenAI Custom GPT 粘贴 Instructions 后格式错乱 | 误将 YAML frontmatter 一起粘贴进 Instructions 字段 | `gpt-instructions.md` 已是纯 Markdown 指令，无 frontmatter，直接全文粘贴即可；不要粘贴 `skill.json` / `config.json` 内容到 Instructions |
| Cursor 规则不触发 | `alwaysApply: false` 导致按需触发未命中，或 `globs` 模式不匹配当前文件 | 确认用户指令涉及开题话题（论文选题/导师项目/同门论文等）；确认当前工作文件匹配 `**/*.md`；若需强制触发可临时改为 `alwaysApply: true` 测试 |
| Trae IDE 未加载 Skill | `SKILL.md` 未放置在 `.trae/skills/thesis-architect/` 路径下 | 确认最终路径为 `<项目根目录>/.trae/skills/thesis-architect/SKILL.md`；`core/` 置于项目根目录；重启 Trae IDE 触发重新扫描 |
| Copilot Chat 未生效 | `.github/copilot-instructions.md` 路径错误或文件名拼写错误 | 确认路径为项目根目录 `.github/copilot-instructions.md`（注意是 `.github` 不是 `github`）；确认文件无 YAML frontmatter；`core/` 置于项目根目录 |
| 脚本执行超时 | 单步脚本执行超过 30 秒 | `core/scripts/` 内置 `timeout(30)` 装饰器；检查输入数据规模是否异常，或谱系文本过长导致解析耗时；超时返回 `status: error` + `error_message: "执行超时"` |
| API 调用失败中断 | 大模型 API 偶发失败 | 自愈逻辑返回 `status: retry`，延迟 2 秒重试；连续失败转为 `status: error` 并回传 `error_message` |
| 文件输出未生成 | 用户未明确表达"保存/生成文件/输出到本地"意图，或 `output/` 目录无写入权限 | 文件输出需用户指令包含明确保存意图；沙盒仅允许写 `output/`，确认运行时有文件写入能力（Claude/Cursor/Trae/Copilot 工作区原生支持，OpenAI 需启用 Code Interpreter） |
| 生成的论题标题超过 20 字 | 硬约束自动修复未执行或运行时未按指令执行 | 检查用户指令是否明确触发 ThesisArchitect 行为；确认 `constraint_checker.py` 的 `check_and_repair()` 被调用；标题超长时应由依存句法截取核心名词短语自动修复 |
| 候选论题未给自评分 | 运行时未按四维创意引擎工作流执行 | 确认指令层已加载；自评分为内部步骤，每个候选必须给出 `score` 字段（满分 10 分，<6 分过滤），权重来自 `core/references/scoring_weights.json` |
| 跨平台能力不一致 | 直接修改了单个平台产物而绕过设计文档与 `core/` 资源层 | 任何能力变更必须先改 `ThesisMinerSkills设计文档.md` 与 `core/` 资源层，再同步转译到所有平台指令层；参见第 10.2 节 |
| 文献综述出现伪造引用 | 运行时未遵守"不伪造文献"约束 | 文献综述只规划"检索方向"与"数量基线"（硕士 ≥30 / 博士 ≥50），不伪造具体作者、年份、期刊；若需真实文献需接入学术搜索 API（如 Semantic Scholar、arXiv） |
| 学位信息缺失时默认硕士 | 运行时未执行"缺失信息引导"步骤 | 学位信息缺失时必须先提问补齐，不得默认硕士；`input_schema.json` 将 `degree` 列为必填，校验不通过应触发提问补齐 |
| 自测失败 | `core/` 脚本或 Schema 被改动后未同步更新测试 | 在项目根目录运行 `python -m pytest tests/ -v`，定位失败用例；修复脚本/Schema 后重新运行，确保 63 个用例全部通过 |
| 联网检索未执行或未展示文献摘要 | Rule 7 信息确权门禁被绕过，运行时直接进入创意生成 | 检查指令层是否按五阶段闭环导航流执行；阶段一必须依据 `search_strategies.json` 生成检索式并联网检索近2年文献，展示摘要后强制中断等待用户确认，未确认不得进入阶段二 |
| 报告输出后对话直接结束 | Rule 10 后置交互循环未执行，未渲染深度辅助导航菜单 | 检查阶段五是否被跳过；报告输出后必须渲染文献精读/实验预研/答辩模拟三件套导航菜单，进入后置交互循环等待用户选择，不得主动结束对话 |
| AI 检测率过高 | style_normalizer 未执行或被排版逻辑覆盖（Rule 9 未生效） | 检查 `generate_report` 的 `style_neutral` 参数是否为 `True`；确认 `remove_ai_traces(text)` 在 Markdown 渲染后被调用，执行 200+禁用词替换、句首过滤、语态互换；Rule 9 规定 style_normalizer 优先级高于排版 |
| 多粒度输出未生效 | `generate_report` 的 `granularity` 参数未传入或取值非法 | 检查 `granularity` 是否为 `concise`/`standard`/`detailed` 三者之一；确认 `output_granularity.yaml` 的 `markdown_depth` 配置被 `_adjust_heading_depth()` 与 `_adjust_subsections()` 读取并应用 |
