"""标题格式校验与自动重写模块

学术标题应使用名词性短语，避免主动动词与超长表述。
本模块提供标题校验、自动重写及一体化校验重写能力。
"""
import re

# 标题最大长度（中文字符数）
MAX_TITLE_LENGTH = 20

# 中文标题中应避免的主动动词
# 学术标题应使用名词性短语，而非以动词开头的陈述句式
ACTIVE_VERBS = [
    "研究",
    "分析",
    "探讨",
    "调查",
    "实现",
    "构建",
    "设计",
    "开发",
    "优化",
    "改进",
    "评估",
    "验证",
]

# "基于X的Y研究" 模式的正则：以"基于"开头且以主动动词结尾
_BASED_PATTERN = re.compile(r"^基于.+的.*(研究|分析|探讨|调查|实现|构建|设计|开发|优化|改进|评估|验证)$")


def _starts_with_active_verb(title: str) -> bool:
    """判断标题是否以主动动词开头。"""
    for verb in ACTIVE_VERBS:
        if title.startswith(verb):
            return True
    return False


def _matches_based_pattern(title: str) -> bool:
    """判断标题是否匹配"基于X的Y研究"模式。"""
    return bool(_BASED_PATTERN.match(title))


def validate_title(title: str) -> dict:
    """校验标题格式是否符合学术规范。

    校验规则：
        1. 长度不超过 MAX_TITLE_LENGTH（20 字）。
        2. 不以主动动词开头。
        3. 不匹配"基于X的Y研究"模式。

    Args:
        title: 待校验的标题字符串。

    Returns:
        校验结果字典：
        - 合法：{"valid": True, "original": title}
        - 非法：{"valid": False, "reason": 原因, "original": title}
    """
    # 长度校验
    if len(title) > MAX_TITLE_LENGTH:
        return {"valid": False, "reason": "标题超过20字", "original": title}

    # 主动动词校验
    if _starts_with_active_verb(title):
        return {"valid": False, "reason": "标题含主动动词", "original": title}

    # "基于X的Y研究" 模式校验
    if _matches_based_pattern(title):
        return {"valid": False, "reason": "标题含主动动词", "original": title}

    return {"valid": True, "original": title}


def rewrite_title(title: str) -> str:
    """对不合规标题进行自动重写。

    重写策略：
        - 超长标题：截取前 20 字，并去除末尾的主动动词词缀。
        - 含主动动词标题：将"研究X"等动词前置结构转换为"X的研究"名词性短语。

    Args:
        title: 待重写的标题字符串。

    Returns:
        重写后的标题字符串。
    """
    # 超长处理：截取核心关键词拼装
    if len(title) > MAX_TITLE_LENGTH:
        # 保留前 20 字
        truncated = title[:MAX_TITLE_LENGTH]
        # 去除末尾的主动动词词缀
        for verb in ACTIVE_VERBS:
            if truncated.endswith(verb):
                truncated = truncated[: -len(verb)]
                break
        return truncated

    # 含主动动词处理：转换为名词性短语
    # 情形一：以主动动词开头，如"研究X" → "X的研究"
    for verb in ACTIVE_VERBS:
        if title.startswith(verb):
            rest = title[len(verb):]
            return f"{rest}的{verb}"

    # 情形二：匹配"基于X的Y研究"模式，提取核心并重组
    match = _BASED_PATTERN.match(title)
    if match:
        # 去除开头的"基于"与结尾的主动动词，重组为名词性短语
        core = title
        if core.startswith("基于"):
            core = core[2:]
        for verb in ACTIVE_VERBS:
            if core.endswith(verb):
                core = core[: -len(verb)]
                break
        # 去除末尾可能残留的"的"
        if core.endswith("的"):
            core = core[:-1]
        return f"{core}研究"

    # 兜底：原样返回
    return title


def validate_and_rewrite(title: str) -> dict:
    """一体化校验与自动重写。

    先调用 validate_title 校验，若不合规则调用 rewrite_title 重写。

    Args:
        title: 待校验的标题字符串。

    Returns:
        包含以下字段的字典：
        - title: 最终标题（合规则为原标题，否则为重写后标题）。
        - auto_rewritten: 是否经过自动重写。
        - original: 原标题。
        - reason: 重写原因（合规时为 None）。
    """
    result = validate_title(title)
    if result["valid"]:
        return {
            "title": title,
            "auto_rewritten": False,
            "original": title,
            "reason": None,
        }

    rewritten = rewrite_title(title)
    return {
        "title": rewritten,
        "auto_rewritten": True,
        "original": title,
        "reason": result["reason"],
    }
