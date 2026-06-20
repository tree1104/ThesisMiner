# ThesisMiner v8.0 去 AI 痕迹风格规范规则

> **版本**：v8.0
> **日期**：2026-06-19
> **适用范围**：`backend/agents/style_normalizer.py`、`backend/agents/proposal_writer.py`
> **关联配置**：`config/constraints/style_rules.yaml`

---

## 目录

1. [去 AI 痕迹总览](#1-去-ai-痕迹总览)
2. [模板词替换规则](#2-模板词替换规则)
3. [句长分布目标](#3-句长分布目标)
4. [并列结构检测与打破](#4-并列结构检测与打破)
5. [过渡词频率限制](#5-过渡词频率限制)
6. [被动语态比例目标](#6-被动语态比例目标)
7. [句首过滤规则](#7-句首过滤规则)
8. [语态互换规则](#8-语态互换规则)
9. [规则优先级与冲突处理](#9-规则优先级与冲突处理)
10. [规则执行流程](#10-规则执行流程)
11. [规则效果评估](#11-规则效果评估)
12. [附录](#12-附录)

---

## 1. 去 AI 痕迹总览

### 1.1 设计目标

AI 生成的文本常带有明显的「AI 痕迹」，如模板化开头、过度使用过渡词、句长单一、被动语态泛滥等。ThesisMiner v8.0 通过 `style_normalizer` 模块对生成的开题报告执行去 AI 痕迹处理，确保输出文本符合人类学术写作风格。设计目标：

1. **模板词替换**：替换 200+ AI 化术语为人类常用表达。
2. **句长分布**：调整句长分布，目标均值 15-25 字，标准差 8-12。
3. **并列结构打破**：检测连续 ≥3 个并列结构并打破。
4. **过渡词限制**：限制过渡词频率，每 1000 字 ≤5 次。
5. **被动语态控制**：被动语态比例 ≤20%。
6. **句首过滤**：删除以「首先/其次/再次/最后」开头的句子。

### 1.2 与 v7 的差异

| 维度 | v7 | v8 |
|------|-----|-----|
| 禁用词数量 | 无 | 200+ |
| 句长控制 | 无 | 均值 15-25，标准差 8-12 |
| 并列结构 | 无 | 检测并打破连续 ≥3 个 |
| 过渡词限制 | 无 | 每 1000 字 ≤5 次 |
| 被动语态 | 无 | 比例 ≤20% |
| 句首过滤 | 无 | 删除模板化开头 |

---

## 2. 模板词替换规则

### 2.1 替换规则模板

每条替换规则包含以下字段：

```yaml
- pattern: "匹配模式（字符串或正则）"
  replacement: "替换文本"
  context: "应用场景（paragraph_start | sentence_start | anywhere）"
  rationale: "替换理由"
  priority: "优先级（high | medium | low）"
```

### 2.2 高频替换规则（50+ 条）

| 原文 | 替换 | 场景 | 理由 |
|------|------|------|------|
| 首先 | （删除） | paragraph_start | AI 模板化开头 |
| 其次 | 接着 | anywhere | AI 模板化过渡 |
| 再次 | 另外 | anywhere | AI 模板化过渡 |
| 最后 | 最终 | anywhere | AI 模板化过渡 |
| 综上所述 | 总的来看 | anywhere | AI 模板化总结 |
| 总而言之 | 总的来看 | anywhere | AI 模板化总结 |
| 由此可见 | 可见 | anywhere | AI 模板化推导 |
| 值得注意的是 | （删除） | anywhere | AI 模板化强调 |
| 需要指出的是 | （删除） | anywhere | AI 模板化强调 |
| 需要注意的是 | （删除） | anywhere | AI 模板化强调 |
| 众所周知 | （删除） | anywhere | AI 模板化常识 |
| 不可否认 | （删除） | anywhere | AI 模板化让步 |
| 毋庸置疑 | （删除） | anywhere | AI 模板化让步 |
| 显而易见 | 明显 | anywhere | AI 模板化推导 |
| 不难发现 | 可见 | anywhere | AI 模板化推导 |
| 不难看出 | 可见 | anywhere | AI 模板化推导 |
| 在某种程度上 | 部分 | anywhere | AI 模板化限定 |
| 在一定程度上 | 部分 | anywhere | AI 模板化限定 |
| 与此同时 | 同时 | anywhere | AI 模板化并列 |
| 在这个过程中 | 过程中 | anywhere | AI 模板化描述 |
| 在这个意义上 | 据此 | anywhere | AI 模板化推导 |
| 从这个角度来看 | 据此看 | anywhere | AI 模板化推导 |
| 从这个意义上说 | 据此 | anywhere | AI 模板化推导 |
| 在此基础上 | 基于此 | anywhere | AI 模板化承接 |
| 在此背景下 | 此背景下 | anywhere | AI 模板化背景 |
| 在这一背景下 | 此背景下 | anywhere | AI 模板化背景 |
| 基于以上分析 | 据上述分析 | anywhere | AI 模板化推导 |
| 基于上述讨论 | 据上述讨论 | anywhere | AI 模板化推导 |
| 通过以上分析 | 经上述分析 | anywhere | AI 模板化推导 |
| 通过上述讨论 | 经上述讨论 | anywhere | AI 模板化推导 |
| 正如前面所述 | 如前所述 | anywhere | AI 模板化回指 |
| 正如前文所述 | 如前所述 | anywhere | AI 模板化回指 |
| 如前所述 | 前文已述 | anywhere | AI 模板化回指 |
| 如上所述 | 上文已述 | anywhere | AI 模板化回指 |
| 如下所示 | 如下 | anywhere | AI 模板化引导 |
| 具体而言 | 具体说 | anywhere | AI 模板化细化 |
| 具体来说 | 具体说 | anywhere | AI 模板化细化 |
| 换句话说 | 即 | anywhere | AI 模板化解释 |
| 简而言之 | 简言之 | anywhere | AI 模板化总结 |
| 总的来说 | 总的看 | anywhere | AI 模板化总结 |
| 总体而言 | 总体看 | anywhere | AI 模板化总结 |
| 整体而言 | 整体看 | anywhere | AI 模板化总结 |
| 一般而言 | 通常 | anywhere | AI 模板化泛化 |
| 通常来说 | 通常 | anywhere | AI 模板化泛化 |
| 一般情况下 | 通常 | anywhere | AI 模板化泛化 |
| 在大多数情况下 | 多数情况下 | anywhere | AI 模板化泛化 |
| 在多数情况下 | 多数情况下 | anywhere | AI 模板化泛化 |
| 在某些情况下 | 有时 | anywhere | AI 模板化限定 |
| 在某些方面 | 部分方面 | anywhere | AI 模板化限定 |
| 在某些领域 | 部分领域 | anywhere | AI 模板化限定 |
| 一方面 | 其一 | anywhere | AI 模板化并列 |
| 另一方面 | 其二 | anywhere | AI 模板化并列 |
| 与此相对 | 相对地 | anywhere | AI 模板化对比 |
| 与此相反 | 相反地 | anywhere | AI 模板化对比 |
| 相比之下 | 相比而言 | anywhere | AI 模板化对比 |
| 与此同时 | 同时 | anywhere | AI 模板化并列 |
| 不仅如此 | 进而 | anywhere | AI 模板化递进 |
| 更为重要的是 | 更重要地 | anywhere | AI 模板化递进 |
| 更为关键的是 | 更关键地 | anywhere | AI 模板化递进 |
| 更为严重的是 | 更严重地 | anywhere | AI 模板化递进 |
| 尤为重要的是 | 尤其 | anywhere | AI 模板化强调 |
| 尤为突出的是 | 突出地 | anywhere | AI 模板化强调 |
| 尤为明显的是 | 明显地 | anywhere | AI 模板化强调 |

### 2.3 替换实现

```python
def apply_replacements(text: str, rules: list) -> tuple:
    """应用模板词替换规则。"""
    replacements_count = 0
    for rule in rules:
        pattern = rule["pattern"]
        replacement = rule["replacement"]
        context = rule.get("context", "anywhere")

        if context == "paragraph_start":
            # 仅在段落开头替换
            text, count = replace_at_paragraph_start(text, pattern, replacement)
        elif context == "sentence_start":
            # 仅在句子开头替换
            text, count = replace_at_sentence_start(text, pattern, replacement)
        else:
            # 任意位置替换
            text, count = replace_anywhere(text, pattern, replacement)

        replacements_count += count

    return text, replacements_count
```

---

## 3. 句长分布目标

### 3.1 目标值

| 指标 | 目标值 | 容差 |
|------|--------|------|
| 句长均值 | 15-25 字 | ±2 字 |
| 句长标准差 | 8-12 字 | ±2 字 |
| 最大句长 | ≤50 字 | - |
| 最小句长 | ≥5 字 | - |

### 3.2 句长调整策略

```text
1. 计算当前句长分布（均值、标准差、最大、最小）
2. 若均值 > 25 字：
   - 识别长句（>30 字）
   - 在合适位置拆分为短句
3. 若均值 < 15 字：
   - 识别短句（<10 字）
   - 合并相邻短句
4. 若标准差 < 8 字：
   - 句长过于单一，主动拆分长句或合并短句
5. 若标准差 > 12 字：
   - 句长差异过大，调整极端句子
```

### 3.3 句长调整实现

```python
import statistics

def adjust_sentence_length(text: str) -> str:
    """调整句长分布。"""
    sentences = split_sentences(text)
    lengths = [len(s) for s in sentences]

    mean_len = statistics.mean(lengths)
    std_len = statistics.stdev(lengths) if len(lengths) > 1 else 0

    # 均值过长，拆分长句
    if mean_len > 25:
        sentences = split_long_sentences(sentences, max_len=25)

    # 均值过短，合并短句
    if mean_len < 15:
        sentences = merge_short_sentences(sentences, min_len=15)

    return "。".join(sentences) + "。"
```

---

## 4. 并列结构检测与打破

### 4.1 检测规则

```text
检测连续 ≥3 个并列结构：
  - 模式 1：A、B、C（顿号并列）
  - 模式 2：首先 A，其次 B，最后 C（序数并列）
  - 模式 3：一方面 A，另一方面 B，再者 C（方面并列）
  - 模式 4：A，同时 B，并且 C（连词并列）
```

### 4.2 打破策略

| 模式 | 打破策略 |
|------|----------|
| 顿号并列 ≥3 | 拆分为多个短句，部分用「以及」「与」连接 |
| 序数并列 ≥3 | 删除序数词，改为自然过渡 |
| 方面并列 ≥3 | 删除「一方面/另一方面」，改为独立句子 |
| 连词并列 ≥3 | 删除部分连词，改为独立句子 |

### 4.3 实现示例

```python
import re

def break_parallel_structures(text: str) -> str:
    """打破连续并列结构。"""
    # 检测顿号并列 ≥3
    pattern = r"([^，。；！？]+)、([^，。；！？]+)、([^，。；！？]+)"
    matches = re.findall(pattern, text)
    for match in matches:
        if all(len(m) > 2 for m in match):
            # 拆分为短句
            old = "、".join(match)
            new = f"{match[0]}，{match[1]}，以及{match[2]}"
            text = text.replace(old, new, 1)

    # 检测序数并列
    pattern = r"首先([^，。]+)，其次([^，。]+)，最后([^，。]+)"
    text = re.sub(pattern, r"\1，\2，\3", text)

    return text
```

---

## 5. 过渡词频率限制

### 5.1 频率目标

| 指标 | 目标值 |
|------|--------|
| 过渡词总频率 | 每 1000 字 ≤5 次 |
| 单个过渡词频率 | 每 1000 字 ≤2 次 |

### 5.2 受限过渡词清单

```text
因此、所以、然而、但是、不过、此外、另外、而且、并且、
于是、然后、接着、随后、最终、最终、总之、综上、
相比之下、与此相对、与此相反、不仅如此、更为重要的是、
尤为重要的是、尤为突出的是、尤为明显的是
```

### 5.3 频率限制实现

```python
def limit_transition_words(text: str) -> str:
    """限制过渡词频率。"""
    transitions = ["因此", "所以", "然而", "但是", "不过", "此外", "另外",
                   "而且", "并且", "于是", "然后", "接着", "随后", "最终"]

    word_count = len(text)
    max_total = (word_count // 1000) * 5 + 5  # 每 1000 字 5 次，余数加 5

    # 统计过渡词出现次数
    counts = {t: text.count(t) for t in transitions}
    total = sum(counts.values())

    # 超限时删除多余的过渡词
    if total > max_total:
        for t in transitions:
            while counts[t] > 2 and total > max_total:
                # 删除最后一个出现
                idx = text.rfind(t)
                if idx != -1:
                    text = text[:idx] + text[idx + len(t):]
                    counts[t] -= 1
                    total -= 1

    return text
```

---

## 6. 被动语态比例目标

### 6.1 目标值

| 指标 | 目标值 |
|------|--------|
| 被动语态比例 | ≤20% |

### 6.2 被动语态识别

```text
中文被动语态标志：
  - 被...
  - 受...
  - 遭...
  - 让...
  - 叫...
  - 给...
  - 为...所...
```

### 6.3 主动化转换

```python
import re

def convert_passive_to_active(text: str) -> str:
    """将被动语态转换为主动语态。"""
    # 检测被动语态比例
    passive_count = len(re.findall(r"被[^，。；！？]+", text))
    sentence_count = text.count("。") + 1
    passive_ratio = passive_count / sentence_count

    if passive_ratio <= 0.2:
        return text  # 比例达标，无需转换

    # 转换被动语态
    # "X 被 Y" → "Y X"（简化转换，实际需依存句法分析）
    pattern = r"([^，。；！？]+)被([^，。；！？]+)"
    matches = re.findall(pattern, text)
    for patient, agent in matches:
        old = f"{patient}被{agent}"
        new = f"{agent}{patient}"
        text = text.replace(old, new, 1)

    return text
```

---

## 7. 句首过滤规则

### 7.1 过滤清单

删除以以下词开头的句子：

```text
首先、其次、再次、最后、此外、另外、而且、并且、
不仅如此、更为重要的是、尤为重要的是、
值得注意的是、需要指出的是、需要注意的是、
众所周知、不可否认、毋庸置疑、显而易见
```

### 7.2 实现示例

```python
SENTENCE_START_FILTERS = [
    "首先", "其次", "再次", "最后", "此外", "另外", "而且", "并且",
    "不仅如此", "更为重要的是", "尤为重要的是",
    "值得注意的是", "需要指出的是", "需要注意的是",
    "众所周知", "不可否认", "毋庸置疑", "显而易见"
]

def filter_sentence_start(text: str) -> str:
    """过滤模板化句首。"""
    sentences = split_sentences(text)
    filtered = []
    for s in sentences:
        s_stripped = s.strip()
        should_filter = False
        for filter_word in SENTENCE_START_FILTERS:
            if s_stripped.startswith(filter_word):
                should_filter = True
                break
        if not should_filter:
            filtered.append(s)

    return "。".join(filtered) + "。"
```

---

## 8. 语态互换规则

### 8.1 互换场景

在合适场景下，将被动语态转换为主动语态：

| 被动 | 主动 |
|------|------|
| 实验被执行 | 执行实验 |
| 数据被收集 | 收集数据 |
| 模型被训练 | 训练模型 |
| 结果被记录 | 记录结果 |

### 8.2 互换原则

1. **保持语义**：互换后语义不变。
2. **保持流畅**：互换后句子流畅自然。
3. **避免歧义**：互换后不产生歧义。
4. **适度互换**：不强制互换所有被动语态，仅互换明显 AI 化的。

---

## 9. 规则优先级与冲突处理

### 9.1 优先级

```text
规则优先级（从高到低）：
  1. 句首过滤（最高，先执行）
  2. 模板词替换
  3. 并列结构打破
  4. 过渡词频率限制
  5. 被动语态转换
  6. 句长分布调整（最低，最后执行）
```

### 9.2 冲突处理

| 冲突场景 | 处理方式 |
|----------|----------|
| 模板词替换与句长调整冲突 | 先替换，后调整句长 |
| 并列结构打破与过渡词限制冲突 | 先打破并列，后限制过渡词 |
| 被动语态转换与句长调整冲突 | 先转换语态，后调整句长 |

---

## 10. 规则执行流程

### 10.1 流程图

```text
┌─────────────────┐
│  原始文本        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 1. 句首过滤      │ ──► 删除模板化句首
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. 模板词替换    │ ──► 替换 200+ AI 化术语
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. 并列结构打破  │ ──► 打破连续 ≥3 个并列
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. 过渡词限制    │ ──► 限制每 1000 字 ≤5 次
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. 被动语态转换  │ ──► 比例 ≤20%
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 6. 句长分布调整  │ ──► 均值 15-25，标准差 8-12
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  标准化输出      │
│  - normalized_text
│  - replacements_count
│  - high_risk_sections
└─────────────────┘
```

### 10.2 实现入口

```python
def remove_ai_traces(text: str) -> dict:
    """去 AI 痕迹主入口。"""
    # 1. 句首过滤
    text = filter_sentence_start(text)

    # 2. 模板词替换
    rules = load_style_rules()
    text, replacements_count = apply_replacements(text, rules)

    # 3. 并列结构打破
    text = break_parallel_structures(text)

    # 4. 过渡词限制
    text = limit_transition_words(text)

    # 5. 被动语态转换
    text = convert_passive_to_active(text)

    # 6. 句长分布调整
    text = adjust_sentence_length(text)

    # 识别高风险段落
    high_risk_sections = identify_high_risk_sections(text)

    return {
        "normalized_text": text,
        "replacements_count": replacements_count,
        "high_risk_sections": high_risk_sections
    }
```

---

## 11. 规则效果评估

### 11.1 评估指标

| 指标 | 目标值 | 评估方式 |
|------|--------|----------|
| AI 检测率 | < 30% | 第三方 AI 检测工具 |
| 模板词替换数 | ≥20 次/千字 | replacements_count |
| 句长均值 | 15-25 字 | 统计计算 |
| 句长标准差 | 8-12 字 | 统计计算 |
| 过渡词频率 | ≤5 次/千字 | 统计计算 |
| 被动语态比例 | ≤20% | 统计计算 |

### 11.2 高风险段落识别

```python
def identify_high_risk_sections(text: str) -> list:
    """识别高风险段落（AI 痕迹较多的段落）。"""
    sections = split_sections(text)
    high_risk = []
    for section in sections:
        risk_score = 0
        # 检查模板词密度
        template_count = count_template_words(section)
        if template_count > 5:
            risk_score += 1
        # 检查句长分布
        lengths = get_sentence_lengths(section)
        if statistics.stdev(lengths) < 5:
            risk_score += 1
        # 检查被动语态比例
        if get_passive_ratio(section) > 0.3:
            risk_score += 1

        if risk_score >= 2:
            high_risk.append(section)

    return high_risk
```

---

## 12. 附录

### 12.1 完整规则配置

详见 `config/constraints/style_rules.yaml`。

### 12.2 术语表

| 术语 | 定义 |
|------|------|
| AI 痕迹 | AI 生成文本的模板化特征 |
| 模板词 | AI 常用的模板化术语 |
| 句长分布 | 句子长度的统计分布 |
| 并列结构 | 多个并列成分的语法结构 |
| 过渡词 | 连接句子或段落的词语 |
| 被动语态 | 主语是动作承受者的语态 |
| 句首过滤 | 删除模板化句首的规则 |
| 高风险段落 | AI 痕迹较多的段落 |

### 12.3 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v8.0 | 2026-06-19 | 初始版本，定义 200+ 替换规则 |
| v8.1 | （规划中） | 新增自适应规则强度 |
| v8.2 | （规划中） | 新增学科专属规则 |

---

> 文档版本 v8.0 · 最后更新 2026-06-19 · 维护者：ThesisMiner 团队
