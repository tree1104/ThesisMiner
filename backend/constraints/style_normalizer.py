"""去 AI 痕迹风格规范化器

替换模板词、调整句式长度分布、去除过度对仗。
"""
import re
from typing import Optional


# 模板词替换规则
TEMPLATE_REPLACEMENTS = [
    (r"^首先[，,]?", ""),
    (r"^其次[，,]?", "接着，"),
    (r"^再次[，,]?", "然后，"),
    (r"^最后[，,]?", "最终，"),
    (r"综上所述[，,]?", "总的来看，"),
    (r"总而言之[，,]?", "整体而言，"),
    (r"由此可见[，,]?", "可以看出，"),
    (r"值得注意的是[，,]?", "需要留意的是，"),
    (r"众所周知[，,]?", ""),
    (r"毋庸置疑[，,]?", ""),
    (r"不言而喻[，,]?", "显然，"),
    (r"一方面.*另一方面", "既...又"),  # 简化对仗
    (r"不仅.*而且", "同时"),
    (r"既.*又.*还", "同时"),
]

# 过度对仗模式
PARALLEL_PATTERNS = [
    r"(?:^|\n)\s*([^，。；\n]{5,20})[，,]\s*\1[^，。；\n]{5,20}[，,]\s*\1",
]


def normalize(text: str) -> str:
    """去 AI 痕迹规范化

    Args:
        text: 原始文本

    Returns:
        规范化后的文本
    """
    if not text:
        return text

    result = text

    # 1. 替换模板词
    for pattern, replacement in TEMPLATE_REPLACEMENTS:
        result = re.sub(pattern, replacement, result, flags=re.MULTILINE)

    # 2. 去除过度对仗
    for pattern in PARALLEL_PATTERNS:
        result = re.sub(pattern, lambda m: m.group(1) + "等", result)

    # 3. 调整句式长度（拆分过长句子）
    result = _split_long_sentences(result)

    # 4. 去除连续的过渡词
    result = _reduce_transition_words(result)

    return result


def _split_long_sentences(text: str, max_length: int = 50) -> str:
    """拆分过长的句子"""
    sentences = text.split("。")
    result = []
    for sent in sentences:
        if len(sent) > max_length:
            # 在逗号处拆分
            parts = sent.split("，")
            current = ""
            for part in parts:
                if len(current) + len(part) > max_length and current:
                    result.append(current)
                    current = part
                else:
                    current = current + "，" + part if current else part
            if current:
                result.append(current)
        else:
            result.append(sent)
    return "。".join(result)


def _reduce_transition_words(text: str, max_per_1000: int = 5) -> str:
    """减少过渡词频率"""
    transition_words = ["因此", "所以", "然而", "但是", "此外", "另外", "同时", "并且"]
    # 统计并减少
    for word in transition_words:
        count = text.count(word)
        if count > 3:
            # 保留前2个，替换其余
            replaced = 0
            def replacer(m):
                nonlocal replaced
                replaced += 1
                return "" if replaced > 2 else m.group(0)
            text = re.sub(re.escape(word), replacer, text)
    return text


def get_ai_trace_score(text: str) -> int:
    """计算 AI 痕迹评分（0-100，越低越像 AI 生成）"""
    if not text:
        return 100

    score = 100
    deductions = 0

    # 检查模板词
    for pattern, _ in TEMPLATE_REPLACEMENTS:
        if re.search(pattern, text, re.MULTILINE):
            deductions += 5

    # 检查对仗结构
    for pattern in PARALLEL_PATTERNS:
        if re.search(pattern, text):
            deductions += 10

    # 检查句式长度分布
    sentences = [s for s in text.split("。") if s.strip()]
    if sentences:
        lengths = [len(s) for s in sentences]
        avg_len = sum(lengths) / len(lengths)
        # AI 生成的句子长度往往很均匀
        if len(lengths) > 3:
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            std = variance ** 0.5
            if std < 5:  # 句子长度过于均匀
                deductions += 15

    return max(0, score - deductions)


def normalize_with_diff(text: str) -> dict:
    """规范化并返回差异对比

    Returns:
        {"original": str, "normalized": str, "changes": int, "ai_score_before": int, "ai_score_after": int}
    """
    original = text
    normalized = normalize(text)
    score_before = get_ai_trace_score(original)
    score_after = get_ai_trace_score(normalized)

    # 简单计算变化数
    changes = sum(1 for a, b in zip(original, normalized) if a != b) + abs(len(original) - len(normalized))

    return {
        "original": original,
        "normalized": normalized,
        "changes": changes,
        "ai_score_before": score_before,
        "ai_score_after": score_after,
    }
