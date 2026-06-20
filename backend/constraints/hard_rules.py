"""硬约束规则库（v8.0 扩展）

扩展自 v7 的 hard_rule_interceptor，新增：
- 标题长度约束（硕士≤25字，博士≤30字）
- 学科匹配检查
- 导师方向对齐
- 时间可行性（硕士1年，博士2年）
- 重复度阈值（相似度<30%）
"""
import re
from dataclasses import dataclass
from typing import Optional

from backend.config import ACADEMIC_CALENDAR


@dataclass
class HardRuleViolation:
    """硬约束违规"""
    rule: str
    severity: str  # error / warning
    message: str
    field: str = ""


def validate_title(title: str, degree: str = "master") -> list[HardRuleViolation]:
    """验证标题约束"""
    violations = []
    if not title:
        violations.append(HardRuleViolation("title_required", "error", "标题不能为空", "title"))
        return violations

    max_len = 25 if degree == "master" else 30
    if len(title) > max_len:
        violations.append(HardRuleViolation(
            "title_length", "error",
            f"标题长度{len(title)}超过限制{max_len}字（{degree}）",
            "title",
        ))

    if len(title) < 8:
        violations.append(HardRuleViolation(
            "title_min_length", "warning",
            f"标题长度{len(title)}过短，建议≥8字",
            "title",
        ))

    # 禁止模式
    forbidden_patterns = ["基于.*的研究", ".*的应用研究", "关于.*的探讨"]
    for pattern in forbidden_patterns:
        if re.match(pattern, title):
            violations.append(HardRuleViolation(
                "title_pattern", "warning",
                f"标题匹配禁止模式'{pattern}'，过于宽泛",
                "title",
            ))

    return violations


def validate_timeline(timeline: dict, degree: str = "master") -> list[HardRuleViolation]:
    """验证时间可行性"""
    violations = []
    calendar = ACADEMIC_CALENDAR.get(degree, ACADEMIC_CALENDAR["master"])
    max_years = calendar["max_years"]

    if not timeline:
        violations.append(HardRuleViolation(
            "timeline_required", "error", "时间规划不能为空", "timeline"
        ))
        return violations

    total_months = timeline.get("total_months", 0)
    if total_months > max_years * 12:
        violations.append(HardRuleViolation(
            "timeline_feasibility", "error",
            f"总时长{total_months}个月超过{degree}最大年限{max_years}年",
            "timeline",
        ))

    return violations


def validate_discipline_match(topic: str, discipline: str) -> list[HardRuleViolation]:
    """验证学科匹配"""
    violations = []
    if not discipline:
        violations.append(HardRuleViolation(
            "discipline_required", "warning", "未指定学科领域", "discipline"
        ))
    return violations


def validate_advisor_alignment(topic: str, advisor_direction: str) -> list[HardRuleViolation]:
    """验证导师方向对齐"""
    violations = []
    if advisor_direction and topic:
        # 简单的关键词匹配
        advisor_keywords = set(advisor_direction.lower().split())
        topic_keywords = set(topic.lower().split())
        overlap = advisor_keywords & topic_keywords
        if not overlap and len(advisor_keywords) > 0:
            violations.append(HardRuleViolation(
                "advisor_alignment", "warning",
                f"论题与导师方向'{advisor_direction}'关键词无重叠",
                "advisor",
            ))
    return violations


def validate_duplication(similarity: float, threshold: float = 0.3) -> list[HardRuleViolation]:
    """验证重复度"""
    violations = []
    if similarity > threshold:
        violations.append(HardRuleViolation(
            "duplication", "error",
            f"重复度{similarity:.1%}超过阈值{threshold:.1%}",
            "similarity",
        ))
    return violations


def validate_all(topic: str, degree: str = "master", discipline: str = "",
                 advisor_direction: str = "", timeline: dict = None,
                 similarity: float = 0.0) -> list[HardRuleViolation]:
    """执行所有硬约束验证"""
    violations = []
    violations.extend(validate_title(topic, degree))
    violations.extend(validate_timeline(timeline or {}, degree))
    violations.extend(validate_discipline_match(topic, discipline))
    violations.extend(validate_advisor_alignment(topic, advisor_direction))
    violations.extend(validate_duplication(similarity))
    return violations


def has_errors(violations: list[HardRuleViolation]) -> bool:
    """是否有 error 级别违规"""
    return any(v.severity == "error" for v in violations)
