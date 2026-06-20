"""硬约束拦截器模块

在论题落库前执行硬约束校验，不合规时抛出 HTTP 422 异常。
与 constraints/format_validator.py 的软校验不同，硬拦截器直接拒绝并要求重新生成。
"""
import math
import re

from fastapi import HTTPException

from backend.config import ACADEMIC_CALENDAR
from backend.constraints.format_validator import ACTIVE_VERBS, MAX_TITLE_LENGTH


# 硬拦截的主动动词正则（标题开头）
_ACTIVE_VERB_START_PATTERN = re.compile(
    r"^(" + "|".join(ACTIVE_VERBS) + ")"
)

# "基于X的Y研究" 模式
_BASED_PATTERN = re.compile(
    r"^基于.+的.*(" + "|".join(ACTIVE_VERBS) + r")$"
)


def validate_title_hard(title: str) -> None:
    """硬校验标题格式，不合规时抛出 HTTP 422。

    校验规则：
    1. 标题非空
    2. 长度不超过 20 字
    3. 不以主动动词开头（研究/分析/探讨等）
    4. 不匹配"基于X的Y研究"模式

    Args:
        title: 待校验的标题

    Raises:
        HTTPException: 422 当标题不合规
    """
    if not title or not title.strip():
        raise HTTPException(status_code=422, detail="标题不能为空")

    if len(title) > MAX_TITLE_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"标题超过{MAX_TITLE_LENGTH}字限制（当前{len(title)}字）"
        )

    if _ACTIVE_VERB_START_PATTERN.match(title):
        raise HTTPException(
            status_code=422,
            detail=f"标题以主动动词开头，请使用名词性短语：{title}"
        )

    if _BASED_PATTERN.match(title):
        raise HTTPException(
            status_code=422,
            detail=f"标题匹配'基于X的Y研究'模式，请使用名词性短语：{title}"
        )


def validate_timeline_hard(research_content: list, degree: str) -> None:
    """硬校验研究内容时间节点，总周期超学制时抛出 HTTP 422。

    从 research_content 文本中提取时间节点（如"3个月"、"半年"、"1年"等），
    累加后与学位学制限制比较。

    Args:
        research_content: 研究内容条目列表
        degree: 学位类型（master/doctor）

    Raises:
        HTTPException: 422 当研究周期超过学制限制
    """
    calendar = ACADEMIC_CALENDAR.get(degree)
    if calendar is None:
        raise HTTPException(status_code=422, detail=f"未知学位类型：{degree}")

    max_months = calendar["max_years"] * 12

    # 从研究内容中提取时间节点
    total_months = _extract_total_months(research_content)

    if total_months > max_months:
        raise HTTPException(
            status_code=422,
            detail=f"研究周期{total_months}个月超过{degree}生{calendar['max_years']}年限制（{max_months}个月）"
        )


def _extract_total_months(research_content: list) -> int:
    """从研究内容文本中提取并累加时间节点（月数）。

    支持的格式：
    - "X个月" / "X 月" → X
    - "X年" / "X 年" → X * 12
    - "半年" → 6
    - "X周" / "X 周" → X / 4 (向上取整)

    Args:
        research_content: 研究内容条目列表

    Returns:
        累加的总月数
    """
    total = 0
    # 匹配 "数字+单位" 的时间表达
    patterns = [
        (re.compile(r"(\d+)\s*个?\s*月"), lambda m: int(m.group(1))),
        (re.compile(r"(\d+)\s*年"), lambda m: int(m.group(1)) * 12),
        (re.compile(r"半年"), lambda m: 6),
        (re.compile(r"(\d+)\s*周"), lambda m: math.ceil(int(m.group(1)) / 4)),
    ]

    for content in research_content:
        if not isinstance(content, str):
            continue
        for pattern, converter in patterns:
            for match in pattern.finditer(content):
                total += converter(match)

    return total


def validate_proposal_hard(proposal: dict, degree: str) -> None:
    """一体化硬校验：标题 + 时间节点。

    Args:
        proposal: 论题提案字典，应包含 title 与 research_content 字段
        degree: 学位类型

    Raises:
        HTTPException: 422 当任一校验不通过
    """
    title = proposal.get("title", "")
    research_content = proposal.get("research_content", [])

    validate_title_hard(title)
    validate_timeline_hard(research_content, degree)
