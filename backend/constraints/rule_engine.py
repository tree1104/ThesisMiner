"""规则引擎

提供规则定义、规则评估、规则链、冲突解决能力。
内置 50+ 论文验证规则。

核心组件：
    - Rule: 规则数据结构
    - RuleResult: 规则评估结果
    - RuleEngine: 规则引擎主类
    - RuleChain: 规则链
    - ConflictResolver: 冲突解决器
    - PREDEFINED_RULES: 预定义规则集

设计原则：
    1. 声明式：规则以数据结构声明，评估逻辑通用
    2. 可组合：规则可组合为规则链
    3. 可扩展：支持动态注册自定义规则
    4. 可观测：评估过程可追踪
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ===== 规则严重级别 =====


class Severity(str, Enum):
    """规则严重级别"""
    INFO = "info"          # 提示
    WARNING = "warning"    # 警告
    ERROR = "error"        # 错误
    CRITICAL = "critical"  # 严重


class RuleType(str, Enum):
    """规则类型"""
    FORMAT = "format"        # 格式校验
    CONTENT = "content"      # 内容校验
    STRUCTURE = "structure"  # 结构校验
    SEMANTIC = "semantic"    # 语义校验
    COMPLIANCE = "compliance"  # 合规校验
    ACADEMIC = "academic"    # 学术规范
    BUDGET = "budget"        # 预算校验
    SECURITY = "security"    # 安全校验


@dataclass
class RuleResult:
    """规则评估结果"""
    rule_id: str
    passed: bool
    severity: str = Severity.INFO.value
    message: str = ""
    field: str = ""
    value: Any = None
    suggestion: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
            "field": self.field,
            "value": self.value,
            "suggestion": self.suggestion,
            "metadata": self.metadata,
        }


@dataclass
class Rule:
    """规则定义

    一条规则包含：
        - 标识信息（id, name, description）
        - 类型与严重级别
        - 评估函数
        - 适用条件
    """
    id: str
    name: str
    description: str
    rule_type: str = RuleType.FORMAT.value
    severity: str = Severity.WARNING.value
    evaluator: Callable = None
    enabled: bool = True
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def evaluate(self, data: dict) -> RuleResult:
        """评估规则。

        Args:
            data: 待评估数据。

        Returns:
            RuleResult 实例。
        """
        if not self.enabled:
            return RuleResult(
                rule_id=self.id,
                passed=True,
                message="规则已禁用",
            )
        if self.evaluator is None:
            return RuleResult(
                rule_id=self.id,
                passed=True,
                message="规则无评估函数",
            )
        try:
            result = self.evaluator(data)
            if isinstance(result, bool):
                return RuleResult(
                    rule_id=self.id,
                    passed=result,
                    severity=self.severity,
                    message=self.description if not result else "校验通过",
                )
            if isinstance(result, dict):
                return RuleResult(
                    rule_id=self.id,
                    passed=result.get("passed", False),
                    severity=result.get("severity", self.severity),
                    message=result.get("message", self.description),
                    field=result.get("field", ""),
                    value=result.get("value"),
                    suggestion=result.get("suggestion", ""),
                    metadata=result.get("metadata", {}),
                )
            if isinstance(result, RuleResult):
                result.rule_id = self.id
                return result
            return RuleResult(
                rule_id=self.id,
                passed=bool(result),
                severity=self.severity,
            )
        except Exception as e:
            return RuleResult(
                rule_id=self.id,
                passed=False,
                severity=Severity.ERROR.value,
                message=f"规则评估异常: {e}",
            )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type,
            "severity": self.severity,
            "enabled": self.enabled,
            "tags": self.tags,
        }


# ===== 预定义评估函数 =====


def _check_title_length(data: dict) -> dict:
    """检查标题长度（≤20字）"""
    title = data.get("title", "")
    if not title:
        return {"passed": False, "message": "标题为空", "field": "title"}
    if len(title) > 20:
        return {
            "passed": False,
            "message": f"标题长度 {len(title)} 超过 20 字限制",
            "field": "title",
            "value": title,
            "suggestion": "请精简标题至 20 字以内",
        }
    return {"passed": True}


def _check_title_no_active_verb(data: dict) -> dict:
    """检查标题不以主动动词开头"""
    title = data.get("title", "")
    verbs = ["研究", "分析", "探讨", "调查", "实现", "构建", "设计", "开发", "优化", "改进", "评估", "验证"]
    for verb in verbs:
        if title.startswith(verb):
            return {
                "passed": False,
                "message": f"标题以主动动词 '{verb}' 开头",
                "field": "title",
                "value": title,
                "suggestion": f"改为名词性短语，如 '{title}的研究'",
            }
    return {"passed": True}


def _check_title_no_based_pattern(data: dict) -> dict:
    """检查标题不匹配'基于X的Y研究'模式"""
    title = data.get("title", "")
    pattern = re.compile(r"^基于.+的.*(研究|分析|探讨|调查|实现|构建|设计|开发|优化|改进|评估|验证)$")
    if pattern.match(title):
        return {
            "passed": False,
            "message": "标题匹配'基于X的Y研究'模式",
            "field": "title",
            "value": title,
            "suggestion": "重组为核心名词性短语",
        }
    return {"passed": True}


def _check_title_not_empty(data: dict) -> dict:
    """检查标题非空"""
    title = data.get("title", "")
    if not title or not title.strip():
        return {"passed": False, "message": "标题不能为空", "field": "title"}
    return {"passed": True}


def _check_abstract_length(data: dict) -> dict:
    """检查摘要长度"""
    abstract = data.get("abstract", "")
    if not abstract:
        return {"passed": False, "message": "摘要为空", "field": "abstract"}
    if len(abstract) < 100:
        return {
            "passed": False,
            "message": f"摘要长度 {len(abstract)} 不足 100 字",
            "field": "abstract",
            "value": len(abstract),
            "suggestion": "请扩充摘要至 100 字以上",
        }
    if len(abstract) > 1000:
        return {
            "passed": False,
            "message": f"摘要长度 {len(abstract)} 超过 1000 字",
            "field": "abstract",
            "value": len(abstract),
            "suggestion": "请精简摘要至 1000 字以内",
        }
    return {"passed": True}


def _check_degree_valid(data: dict) -> dict:
    """检查学位层次有效"""
    degree = data.get("degree", "")
    valid = ["master", "doctor", "bachelor", "postdoc"]
    if degree not in valid:
        return {
            "passed": False,
            "message": f"学位层次 '{degree}' 无效，有效值: {valid}",
            "field": "degree",
            "value": degree,
        }
    return {"passed": True}


def _check_discipline_not_empty(data: dict) -> dict:
    """检查学科方向非空"""
    discipline = data.get("discipline", "")
    if not discipline or not discipline.strip():
        return {"passed": False, "message": "学科方向不能为空", "field": "discipline"}
    return {"passed": True}


def _check_research_content_not_empty(data: dict) -> dict:
    """检查研究内容非空"""
    content = data.get("research_content", [])
    if not content or (isinstance(content, list) and len(content) == 0):
        return {"passed": False, "message": "研究内容不能为空", "field": "research_content"}
    return {"passed": True}


def _check_confidence_score_range(data: dict) -> dict:
    """检查置信度分数范围"""
    score = data.get("confidence_score", 0)
    try:
        score = float(score)
    except (ValueError, TypeError):
        return {"passed": False, "message": "置信度分数不是有效数字", "field": "confidence_score"}
    if score < 0 or score > 1:
        return {
            "passed": False,
            "message": f"置信度分数 {score} 超出 [0, 1] 范围",
            "field": "confidence_score",
            "value": score,
        }
    return {"passed": True}


def _check_timeframe_master(data: dict) -> dict:
    """检查硕士研究周期（≤12个月）"""
    degree = data.get("degree", "")
    if degree != "master":
        return {"passed": True}
    months = data.get("timeframe_months", 0)
    if months > 12:
        return {
            "passed": False,
            "message": f"硕士研究周期 {months} 个月超过 12 个月限制",
            "field": "timeframe_months",
            "value": months,
            "suggestion": "硕士研究周期应在 12 个月以内",
        }
    return {"passed": True}


def _check_timeframe_doctor(data: dict) -> dict:
    """检查博士研究周期（≤24个月）"""
    degree = data.get("degree", "")
    if degree != "doctor":
        return {"passed": True}
    months = data.get("timeframe_months", 0)
    if months > 24:
        return {
            "passed": False,
            "message": f"博士研究周期 {months} 个月超过 24 个月限制",
            "field": "timeframe_months",
            "value": months,
            "suggestion": "博士研究周期应在 24 个月以内",
        }
    return {"passed": True}


def _check_literature_master(data: dict) -> dict:
    """检查硕士文献基线（≥30篇）"""
    degree = data.get("degree", "")
    if degree != "master":
        return {"passed": True}
    count = data.get("literature_count", 0)
    if count < 30:
        return {
            "passed": False,
            "message": f"硕士文献数量 {count} 不足 30 篇基线",
            "field": "literature_count",
            "value": count,
            "suggestion": "硕士文献应不少于 30 篇",
        }
    return {"passed": True}


def _check_literature_doctor(data: dict) -> dict:
    """检查博士文献基线（≥50篇）"""
    degree = data.get("degree", "")
    if degree != "doctor":
        return {"passed": True}
    count = data.get("literature_count", 0)
    if count < 50:
        return {
            "passed": False,
            "message": f"博士文献数量 {count} 不足 50 篇基线",
            "field": "literature_count",
            "value": count,
            "suggestion": "博士文献应不少于 50 篇",
        }
    return {"passed": True}


def _check_no_html_in_title(data: dict) -> dict:
    """检查标题不含 HTML 标签"""
    title = data.get("title", "")
    if re.search(r"<[^>]+>", title):
        return {
            "passed": False,
            "message": "标题包含 HTML 标签",
            "field": "title",
            "value": title,
        }
    return {"passed": True}


def _check_no_html_in_abstract(data: dict) -> dict:
    """检查摘要不含 HTML 标签"""
    abstract = data.get("abstract", "")
    if re.search(r"<[^>]+>", abstract):
        return {
            "passed": False,
            "message": "摘要包含 HTML 标签",
            "field": "abstract",
        }
    return {"passed": True}


def _check_no_xss_in_title(data: dict) -> dict:
    """检查标题不含 XSS 特征"""
    title = data.get("title", "")
    patterns = [r"<script", r"javascript:", r"on\w+\s*=", r"<iframe"]
    for pattern in patterns:
        if re.search(pattern, title, re.IGNORECASE):
            return {
                "passed": False,
                "message": f"标题包含潜在 XSS 内容: {pattern}",
                "field": "title",
                "severity": Severity.CRITICAL.value,
            }
    return {"passed": True}


def _check_no_sql_injection(data: dict) -> dict:
    """检查不含 SQL 注入特征"""
    for field_name in ["title", "abstract", "discipline", "mentor_info"]:
        value = data.get(field_name, "")
        if not isinstance(value, str):
            continue
        patterns = [r"'\s*OR\s*", r"UNION\s+SELECT", r"DROP\s+TABLE", r";\s*DROP"]
        for pattern in patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return {
                    "passed": False,
                    "message": f"字段 {field_name} 包含潜在 SQL 注入内容",
                    "field": field_name,
                    "severity": Severity.CRITICAL.value,
                }
    return {"passed": True}


def _check_inspiration_source_not_empty(data: dict) -> dict:
    """检查灵感来源非空"""
    source = data.get("inspiration_source", "")
    if not source or not source.strip():
        return {"passed": False, "message": "灵感来源不能为空", "field": "inspiration_source"}
    return {"passed": True}


def _check_research_significance_not_empty(data: dict) -> dict:
    """检查研究意义非空"""
    significance = data.get("research_significance", "")
    if not significance:
        return {"passed": False, "message": "研究意义不能为空", "field": "research_significance"}
    if isinstance(significance, dict):
        if not significance.get("theoretical") and not significance.get("practical"):
            return {"passed": False, "message": "研究意义的理论与实践意义均为空", "field": "research_significance"}
    return {"passed": True}


def _check_differentiation_not_empty(data: dict) -> dict:
    """检查差异化声明非空"""
    diff = data.get("differentiation", "")
    if not diff or not diff.strip():
        return {"passed": False, "message": "差异化声明不能为空", "field": "differentiation"}
    return {"passed": True}


def _check_feasibility_has_method(data: dict) -> dict:
    """检查可行性分析包含方法"""
    feasibility = data.get("feasibility", {})
    if not isinstance(feasibility, dict):
        return {"passed": False, "message": "可行性分析格式错误", "field": "feasibility"}
    methodology = feasibility.get("methodology", "")
    if not methodology or not methodology.strip():
        return {
            "passed": False,
            "message": "可行性分析缺少研究方法",
            "field": "feasibility.methodology",
            "suggestion": "请说明拟采用的研究方法",
        }
    return {"passed": True}


def _check_feasibility_has_resources(data: dict) -> dict:
    """检查可行性分析包含资源"""
    feasibility = data.get("feasibility", {})
    if not isinstance(feasibility, dict):
        return {"passed": True}
    resources = feasibility.get("resources", "")
    if not resources or not resources.strip():
        return {
            "passed": False,
            "message": "可行性分析缺少资源说明",
            "field": "feasibility.resources",
        }
    return {"passed": True}


def _check_title_chinese_ratio(data: dict) -> dict:
    """检查标题中文占比（学术标题应以中文为主）"""
    title = data.get("title", "")
    if not title:
        return {"passed": True}
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", title))
    total = len(title)
    if total > 0 and chinese_chars / total < 0.3:
        return {
            "passed": False,
            "message": f"标题中文占比 {chinese_chars/total:.0%} 过低",
            "field": "title",
            "suggestion": "学术标题应以中文为主",
        }
    return {"passed": True}


def _check_no_personal_info(data: dict) -> dict:
    """检查不含个人隐私信息"""
    import re
    for field_name in ["title", "abstract", "mentor_info"]:
        value = data.get(field_name, "")
        if not isinstance(value, str):
            continue
        # 手机号
        if re.search(r"1[3-9]\d{9}", value):
            return {
                "passed": False,
                "message": f"字段 {field_name} 包含手机号",
                "field": field_name,
                "severity": Severity.WARNING.value,
            }
        # 身份证号
        if re.search(r"\d{17}[\dXx]", value):
            return {
                "passed": False,
                "message": f"字段 {field_name} 包含身份证号",
                "field": field_name,
                "severity": Severity.WARNING.value,
            }
        # 邮箱
        if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", value):
            return {
                "passed": False,
                "message": f"字段 {field_name} 包含邮箱地址",
                "field": field_name,
                "severity": Severity.WARNING.value,
            }
    return {"passed": True}


def _check_keywords_count(data: dict) -> dict:
    """检查关键词数量（3-5个）"""
    keywords = data.get("keywords", [])
    if not isinstance(keywords, list):
        return {"passed": True}
    if len(keywords) < 3:
        return {
            "passed": False,
            "message": f"关键词数量 {len(keywords)} 不足 3 个",
            "field": "keywords",
        }
    if len(keywords) > 5:
        return {
            "passed": False,
            "message": f"关键词数量 {len(keywords)} 超过 5 个",
            "field": "keywords",
        }
    return {"passed": True}


def _check_citations_count(data: dict) -> dict:
    """检查引用数量"""
    citations = data.get("citations", [])
    degree = data.get("degree", "master")
    min_count = 30 if degree == "master" else 50
    if len(citations) < min_count:
        return {
            "passed": False,
            "message": f"引用数量 {len(citations)} 不足 {min_count} 篇",
            "field": "citations",
        }
    return {"passed": True}


def _check_no_duplicate_keywords(data: dict) -> dict:
    """检查关键词无重复"""
    keywords = data.get("keywords", [])
    if not isinstance(keywords, list):
        return {"passed": True}
    seen = set()
    for kw in keywords:
        kw_lower = kw.lower() if isinstance(kw, str) else str(kw)
        if kw_lower in seen:
            return {
                "passed": False,
                "message": f"关键词重复: {kw}",
                "field": "keywords",
            }
        seen.add(kw_lower)
    return {"passed": True}


def _check_title_no_special_chars(data: dict) -> dict:
    """检查标题不含特殊字符"""
    title = data.get("title", "")
    if re.search(r"[<>\"'&\\]", title):
        return {
            "passed": False,
            "message": "标题包含特殊字符",
            "field": "title",
        }
    return {"passed": True}


def _check_abstract_has_background(data: dict) -> dict:
    """检查摘要包含研究背景"""
    abstract = data.get("abstract", "")
    if not abstract:
        return {"passed": True}
    background_keywords = ["背景", "近年来", "随着", "目前", "当前", "近年来", "近年来"]
    has_background = any(kw in abstract for kw in background_keywords)
    if not has_background:
        return {
            "passed": False,
            "message": "摘要缺少研究背景描述",
            "field": "abstract",
            "suggestion": "建议在摘要开头说明研究背景",
        }
    return {"passed": True}


def _check_abstract_has_method(data: dict) -> dict:
    """检查摘要包含研究方法"""
    abstract = data.get("abstract", "")
    if not abstract:
        return {"passed": True}
    method_keywords = ["方法", "采用", "利用", "基于", "通过", "运用", "使用", "借助"]
    has_method = any(kw in abstract for kw in method_keywords)
    if not has_method:
        return {
            "passed": False,
            "message": "摘要缺少研究方法描述",
            "field": "abstract",
        }
    return {"passed": True}


def _check_abstract_has_result(data: dict) -> dict:
    """检查摘要包含研究结果"""
    abstract = data.get("abstract", "")
    if not abstract:
        return {"passed": True}
    result_keywords = ["结果", "发现", "表明", "显示", "证明", "得出", "实现"]
    has_result = any(kw in abstract for kw in result_keywords)
    if not has_result:
        return {
            "passed": False,
            "message": "摘要缺少研究结果描述",
            "field": "abstract",
        }
    return {"passed": True}


def _check_research_content_count(data: dict) -> dict:
    """检查研究内容条目数（≥3）"""
    content = data.get("research_content", [])
    if not isinstance(content, list):
        return {"passed": True}
    if len(content) < 3:
        return {
            "passed": False,
            "message": f"研究内容条目 {len(content)} 不足 3 条",
            "field": "research_content",
        }
    return {"passed": True}


def _check_budget_within_limit(data: dict) -> dict:
    """检查预算在限额内"""
    cost = data.get("estimated_cost", 0)
    limit = data.get("budget_limit", 100)
    if cost > limit:
        return {
            "passed": False,
            "message": f"预估费用 {cost} 超出预算限额 {limit}",
            "field": "estimated_cost",
            "severity": Severity.WARNING.value,
        }
    return {"passed": True}


def _check_model_configured(data: dict) -> dict:
    """检查模型已配置"""
    model = data.get("model", "")
    if not model:
        return {
            "passed": False,
            "message": "模型未配置",
            "field": "model",
            "severity": Severity.ERROR.value,
        }
    return {"passed": True}


def _check_api_key_configured(data: dict) -> dict:
    """检查 API 密钥已配置"""
    api_key = data.get("api_key", "")
    if not api_key:
        return {
            "passed": False,
            "message": "API 密钥未配置",
            "field": "api_key",
            "severity": Severity.ERROR.value,
        }
    return {"passed": True}


def _check_session_id_valid(data: dict) -> dict:
    """检查会话 ID 有效"""
    session_id = data.get("session_id", "")
    if session_id and not re.match(r"^[a-zA-Z0-9\-_]+$", session_id):
        return {
            "passed": False,
            "message": "会话 ID 格式无效",
            "field": "session_id",
        }
    return {"passed": True}


def _check_granularity_valid(data: dict) -> dict:
    """检查生成粒度有效"""
    granularity = data.get("granularity", "")
    valid = ["topic", "outline", "paragraph", "section", "full"]
    if granularity and granularity not in valid:
        return {
            "passed": False,
            "message": f"生成粒度 '{granularity}' 无效",
            "field": "granularity",
        }
    return {"passed": True}


def _check_mode_valid(data: dict) -> dict:
    """检查生成模式有效"""
    mode = data.get("mode", "")
    valid = ["quick", "deep", "balanced"]
    if mode and mode not in valid:
        return {
            "passed": False,
            "message": f"生成模式 '{mode}' 无效",
            "field": "mode",
        }
    return {"passed": True}


def _check_count_range(data: dict) -> dict:
    """检查生成数量范围"""
    count = data.get("count", 3)
    if count < 1 or count > 10:
        return {
            "passed": False,
            "message": f"生成数量 {count} 超出 [1, 10] 范围",
            "field": "count",
        }
    return {"passed": True}


def _check_mentor_info_length(data: dict) -> dict:
    """检查导师信息长度"""
    info = data.get("mentor_info", "")
    if len(info) > 5000:
        return {
            "passed": False,
            "message": f"导师信息长度 {len(info)} 超过 5000 字",
            "field": "mentor_info",
        }
    return {"passed": True}


def _check_no_sensitive_words(data: dict) -> dict:
    """检查不含敏感词"""
    sensitive_words = ["政治敏感", "违法", "色情", "暴力"]
    for field_name in ["title", "abstract", "research_content"]:
        value = data.get(field_name, "")
        if isinstance(value, str):
            for word in sensitive_words:
                if word in value:
                    return {
                        "passed": False,
                        "message": f"字段 {field_name} 包含敏感词: {word}",
                        "field": field_name,
                        "severity": Severity.CRITICAL.value,
                    }
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    for word in sensitive_words:
                        if word in item:
                            return {
                                "passed": False,
                                "message": f"字段 {field_name} 包含敏感词: {word}",
                                "field": field_name,
                                "severity": Severity.CRITICAL.value,
                            }
    return {"passed": True}


def _check_title_not_too_short(data: dict) -> dict:
    """检查标题不过短（≥4字）"""
    title = data.get("title", "")
    if len(title) < 4:
        return {
            "passed": False,
            "message": f"标题长度 {len(title)} 过短，应至少 4 字",
            "field": "title",
        }
    return {"passed": True}


def _check_research_content_not_too_long(data: dict) -> dict:
    """检查研究内容不过长"""
    content = data.get("research_content", [])
    if isinstance(content, list) and len(content) > 10:
        return {
            "passed": False,
            "message": f"研究内容条目 {len(content)} 过多，建议不超过 10 条",
            "field": "research_content",
            "severity": Severity.WARNING.value,
        }
    return {"passed": True}


def _check_has_literature_review(data: dict) -> dict:
    """检查包含文献综述"""
    review = data.get("literature_review", "")
    if not review or not review.strip():
        return {
            "passed": False,
            "message": "缺少文献综述",
            "field": "literature_review",
            "severity": Severity.WARNING.value,
        }
    return {"passed": True}


def _check_feasibility_has_timeline(data: dict) -> dict:
    """检查可行性分析包含时间安排"""
    feasibility = data.get("feasibility", {})
    if not isinstance(feasibility, dict):
        return {"passed": True}
    timeline = feasibility.get("time", feasibility.get("timeline", ""))
    if not timeline or not str(timeline).strip():
        return {
            "passed": False,
            "message": "可行性分析缺少时间安排",
            "field": "feasibility.time",
        }
    return {"passed": True}


def _check_confidence_score_threshold(data: dict) -> dict:
    """检查置信度分数达标（≥0.5）"""
    score = data.get("confidence_score", 0)
    try:
        score = float(score)
    except (ValueError, TypeError):
        return {"passed": True}
    if score < 0.5:
        return {
            "passed": False,
            "message": f"置信度分数 {score} 低于 0.5 阈值",
            "field": "confidence_score",
            "severity": Severity.WARNING.value,
        }
    return {"passed": True}


def _check_title_uniqueness(data: dict) -> dict:
    """检查标题唯一性（与已有论题对比）"""
    title = data.get("title", "")
    existing_titles = data.get("existing_titles", [])
    if title in existing_titles:
        return {
            "passed": False,
            "message": f"标题 '{title}' 已存在",
            "field": "title",
            "severity": Severity.WARNING.value,
        }
    return {"passed": True}


def _check_currency_valid(data: dict) -> dict:
    """检查货币类型有效"""
    currency = data.get("currency", "CNY")
    if currency not in ("CNY", "USD"):
        return {
            "passed": False,
            "message": f"货币类型 '{currency}' 无效",
            "field": "currency",
        }
    return {"passed": True}


def _check_temperature_range(data: dict) -> dict:
    """检查温度参数范围"""
    temp = data.get("temperature", 0.7)
    try:
        temp = float(temp)
    except (ValueError, TypeError):
        return {"passed": False, "message": "温度参数不是有效数字", "field": "temperature"}
    if temp < 0 or temp > 2:
        return {
            "passed": False,
            "message": f"温度参数 {temp} 超出 [0, 2] 范围",
            "field": "temperature",
        }
    return {"passed": True}


def _check_max_tokens_range(data: dict) -> dict:
    """检查最大 token 数范围"""
    max_tokens = data.get("max_tokens", 4096)
    try:
        max_tokens = int(max_tokens)
    except (ValueError, TypeError):
        return {"passed": False, "message": "最大 token 数不是有效整数", "field": "max_tokens"}
    if max_tokens < 1 or max_tokens > 1000000:
        return {
            "passed": False,
            "message": f"最大 token 数 {max_tokens} 超出 [1, 1000000] 范围",
            "field": "max_tokens",
        }
    return {"passed": True}


def _check_pagination_limit(data: dict) -> dict:
    """检查分页 limit 参数"""
    limit = data.get("limit", 20)
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        return {"passed": False, "message": "limit 不是有效整数", "field": "limit"}
    if limit < 1 or limit > 100:
        return {
            "passed": False,
            "message": f"limit {limit} 超出 [1, 100] 范围",
            "field": "limit",
        }
    return {"passed": True}


def _check_pagination_offset(data: dict) -> dict:
    """检查分页 offset 参数"""
    offset = data.get("offset", 0)
    try:
        offset = int(offset)
    except (ValueError, TypeError):
        return {"passed": False, "message": "offset 不是有效整数", "field": "offset"}
    if offset < 0:
        return {
            "passed": False,
            "message": f"offset {offset} 不能为负数",
            "field": "offset",
        }
    return {"passed": True}


def _check_search_query_length(data: dict) -> dict:
    """检查搜索查询长度"""
    query = data.get("query", "")
    if not query or not query.strip():
        return {"passed": False, "message": "搜索查询不能为空", "field": "query"}
    if len(query) > 500:
        return {
            "passed": False,
            "message": f"搜索查询长度 {len(query)} 超过 500 字",
            "field": "query",
        }
    return {"passed": True}


def _check_search_years_range(data: dict) -> dict:
    """检查检索年限范围"""
    years = data.get("years", 2)
    try:
        years = int(years)
    except (ValueError, TypeError):
        return {"passed": False, "message": "检索年限不是有效整数", "field": "years"}
    if years < 1 or years > 10:
        return {
            "passed": False,
            "message": f"检索年限 {years} 超出 [1, 10] 范围",
            "field": "years",
        }
    return {"passed": True}


def _check_model_id_format(data: dict) -> dict:
    """检查模型 ID 格式"""
    model_id = data.get("model_id", "")
    if not model_id:
        return {"passed": True}
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9.\-]*$", model_id):
        return {
            "passed": False,
            "message": "模型 ID 格式无效",
            "field": "model_id",
        }
    return {"passed": True}


def _check_base_url_format(data: dict) -> dict:
    """检查 base_url 格式"""
    url = data.get("base_url", "")
    if not url:
        return {"passed": True}
    if not re.match(r"^https?://", url):
        return {
            "passed": False,
            "message": "base_url 必须以 http:// 或 https:// 开头",
            "field": "base_url",
        }
    return {"passed": True}


def _check_pricing_non_negative(data: dict) -> dict:
    """检查定价非负"""
    pricing = data.get("pricing", {})
    if not isinstance(pricing, dict):
        return {"passed": True}
    for key, value in pricing.items():
        try:
            if float(value) < 0:
                return {
                    "passed": False,
                    "message": f"定价字段 {key} 为负数",
                    "field": f"pricing.{key}",
                }
        except (ValueError, TypeError):
            return {
                "passed": False,
                "message": f"定价字段 {key} 不是有效数字",
                "field": f"pricing.{key}",
            }
    return {"passed": True}


def _check_max_context_positive(data: dict) -> dict:
    """检查最大上下文为正数"""
    max_context = data.get("max_context", 128000)
    try:
        max_context = int(max_context)
    except (ValueError, TypeError):
        return {"passed": False, "message": "max_context 不是有效整数", "field": "max_context"}
    if max_context < 1000:
        return {
            "passed": False,
            "message": f"max_context {max_context} 过小，应至少 1000",
            "field": "max_context",
        }
    return {"passed": True}


def _check_release_year_range(data: dict) -> dict:
    """检查发布年份范围"""
    year = data.get("release_year", 2026)
    try:
        year = int(year)
    except (ValueError, TypeError):
        return {"passed": False, "message": "release_year 不是有效整数", "field": "release_year"}
    if year < 2000 or year > 2100:
        return {
            "passed": False,
            "message": f"release_year {year} 超出 [2000, 2100] 范围",
            "field": "release_year",
        }
    return {"passed": True}


def _check_session_status_valid(data: dict) -> dict:
    """检查会话状态有效"""
    status = data.get("status", "")
    valid = ["active", "closed", "completed", "archived"]
    if status and status not in valid:
        return {
            "passed": False,
            "message": f"会话状态 '{status}' 无效",
            "field": "status",
        }
    return {"passed": True}


def _check_no_circular_reference(data: dict) -> dict:
    """检查无循环引用"""
    references = data.get("references", {})
    if not isinstance(references, dict):
        return {"passed": True}
    visited = set()

    def has_cycle(node, path):
        if node in path:
            return True
        if node in visited:
            return False
        visited.add(node)
        path.add(node)
        for neighbor in references.get(node, []):
            if has_cycle(neighbor, path):
                return True
        path.remove(node)
        return False

    for node in references:
        if has_cycle(node, set()):
            return {
                "passed": False,
                "message": f"检测到循环引用: {node}",
                "field": "references",
                "severity": Severity.WARNING.value,
            }
    return {"passed": True}


def _check_graph_node_count(data: dict) -> dict:
    """检查图谱节点数量"""
    nodes = data.get("nodes", [])
    if len(nodes) > 10000:
        return {
            "passed": False,
            "message": f"图谱节点数 {len(nodes)} 过多",
            "field": "nodes",
            "severity": Severity.WARNING.value,
        }
    return {"passed": True}


def _check_edge_weight_range(data: dict) -> dict:
    """检查边权重范围"""
    edges = data.get("edges", [])
    for edge in edges:
        if isinstance(edge, dict):
            weight = edge.get("weight", 1.0)
            try:
                weight = float(weight)
                if weight < 0 or weight > 1:
                    return {
                        "passed": False,
                        "message": f"边权重 {weight} 超出 [0, 1] 范围",
                        "field": "edges",
                    }
            except (ValueError, TypeError):
                return {
                    "passed": False,
                    "message": "边权重不是有效数字",
                    "field": "edges",
                }
    return {"passed": True}


# ===== 预定义规则集 =====


PREDEFINED_RULES: list[Rule] = [
    # 标题校验规则
    Rule(id="title.not_empty", name="标题非空", description="标题不能为空",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_title_not_empty, tags=["title"]),
    Rule(id="title.length", name="标题长度", description="标题长度不超过20字",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_title_length, tags=["title"]),
    Rule(id="title.not_too_short", name="标题不过短", description="标题至少4字",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_title_not_too_short, tags=["title"]),
    Rule(id="title.no_active_verb", name="标题无主动动词", description="标题不以主动动词开头",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_title_no_active_verb, tags=["title"]),
    Rule(id="title.no_based_pattern", name="标题无基于模式", description="标题不匹配'基于X的Y研究'模式",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_title_no_based_pattern, tags=["title"]),
    Rule(id="title.no_html", name="标题无HTML", description="标题不含HTML标签",
         rule_type=RuleType.SECURITY.value, severity=Severity.ERROR.value,
         evaluator=_check_no_html_in_title, tags=["title", "security"]),
    Rule(id="title.no_xss", name="标题无XSS", description="标题不含XSS特征",
         rule_type=RuleType.SECURITY.value, severity=Severity.CRITICAL.value,
         evaluator=_check_no_xss_in_title, tags=["title", "security"]),
    Rule(id="title.no_special_chars", name="标题无特殊字符", description="标题不含特殊字符",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_title_no_special_chars, tags=["title"]),
    Rule(id="title.chinese_ratio", name="标题中文占比", description="标题中文占比不低于30%",
         rule_type=RuleType.ACADEMIC.value, severity=Severity.WARNING.value,
         evaluator=_check_title_chinese_ratio, tags=["title"]),
    Rule(id="title.uniqueness", name="标题唯一性", description="标题不与已有论题重复",
         rule_type=RuleType.COMPLIANCE.value, severity=Severity.WARNING.value,
         evaluator=_check_title_uniqueness, tags=["title"]),

    # 摘要校验规则
    Rule(id="abstract.length", name="摘要长度", description="摘要长度100-1000字",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_abstract_length, tags=["abstract"]),
    Rule(id="abstract.no_html", name="摘要无HTML", description="摘要不含HTML标签",
         rule_type=RuleType.SECURITY.value, severity=Severity.ERROR.value,
         evaluator=_check_no_html_in_abstract, tags=["abstract", "security"]),
    Rule(id="abstract.has_background", name="摘要含背景", description="摘要包含研究背景",
         rule_type=RuleType.ACADEMIC.value, severity=Severity.WARNING.value,
         evaluator=_check_abstract_has_background, tags=["abstract"]),
    Rule(id="abstract.has_method", name="摘要含方法", description="摘要包含研究方法",
         rule_type=RuleType.ACADEMIC.value, severity=Severity.WARNING.value,
         evaluator=_check_abstract_has_method, tags=["abstract"]),
    Rule(id="abstract.has_result", name="摘要含结果", description="摘要包含研究结果",
         rule_type=RuleType.ACADEMIC.value, severity=Severity.WARNING.value,
         evaluator=_check_abstract_has_result, tags=["abstract"]),

    # 学位与学科规则
    Rule(id="degree.valid", name="学位有效", description="学位层次有效",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_degree_valid, tags=["degree"]),
    Rule(id="discipline.not_empty", name="学科非空", description="学科方向非空",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_discipline_not_empty, tags=["discipline"]),

    # 研究内容规则
    Rule(id="research_content.not_empty", name="研究内容非空", description="研究内容非空",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_research_content_not_empty, tags=["research_content"]),
    Rule(id="research_content.count", name="研究内容条目数", description="研究内容至少3条",
         rule_type=RuleType.STRUCTURE.value, severity=Severity.WARNING.value,
         evaluator=_check_research_content_count, tags=["research_content"]),
    Rule(id="research_content.not_too_long", name="研究内容不过长", description="研究内容不超过10条",
         rule_type=RuleType.STRUCTURE.value, severity=Severity.WARNING.value,
         evaluator=_check_research_content_not_too_long, tags=["research_content"]),

    # 可行性规则
    Rule(id="feasibility.has_method", name="可行性含方法", description="可行性分析包含研究方法",
         rule_type=RuleType.ACADEMIC.value, severity=Severity.WARNING.value,
         evaluator=_check_feasibility_has_method, tags=["feasibility"]),
    Rule(id="feasibility.has_resources", name="可行性含资源", description="可行性分析包含资源说明",
         rule_type=RuleType.ACADEMIC.value, severity=Severity.WARNING.value,
         evaluator=_check_feasibility_has_resources, tags=["feasibility"]),
    Rule(id="feasibility.has_timeline", name="可行性含时间", description="可行性分析包含时间安排",
         rule_type=RuleType.ACADEMIC.value, severity=Severity.WARNING.value,
         evaluator=_check_feasibility_has_timeline, tags=["feasibility"]),

    # 时间约束规则
    Rule(id="timeframe.master", name="硕士周期", description="硕士研究周期≤12个月",
         rule_type=RuleType.COMPLIANCE.value, severity=Severity.ERROR.value,
         evaluator=_check_timeframe_master, tags=["timeframe", "master"]),
    Rule(id="timeframe.doctor", name="博士周期", description="博士研究周期≤24个月",
         rule_type=RuleType.COMPLIANCE.value, severity=Severity.ERROR.value,
         evaluator=_check_timeframe_doctor, tags=["timeframe", "doctor"]),

    # 文献基线规则
    Rule(id="literature.master", name="硕士文献基线", description="硕士文献≥30篇",
         rule_type=RuleType.COMPLIANCE.value, severity=Severity.WARNING.value,
         evaluator=_check_literature_master, tags=["literature", "master"]),
    Rule(id="literature.doctor", name="博士文献基线", description="博士文献≥50篇",
         rule_type=RuleType.COMPLIANCE.value, severity=Severity.WARNING.value,
         evaluator=_check_literature_doctor, tags=["literature", "doctor"]),
    Rule(id="citations.count", name="引用数量", description="引用数量达标",
         rule_type=RuleType.COMPLIANCE.value, severity=Severity.WARNING.value,
         evaluator=_check_citations_count, tags=["citations"]),

    # 置信度规则
    Rule(id="confidence.range", name="置信度范围", description="置信度在[0,1]范围",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_confidence_score_range, tags=["confidence"]),
    Rule(id="confidence.threshold", name="置信度阈值", description="置信度≥0.5",
         rule_type=RuleType.ACADEMIC.value, severity=Severity.WARNING.value,
         evaluator=_check_confidence_score_threshold, tags=["confidence"]),

    # 安全规则
    Rule(id="security.no_sql_injection", name="无SQL注入", description="不含SQL注入特征",
         rule_type=RuleType.SECURITY.value, severity=Severity.CRITICAL.value,
         evaluator=_check_no_sql_injection, tags=["security"]),
    Rule(id="security.no_personal_info", name="无个人隐私", description="不含个人隐私信息",
         rule_type=RuleType.SECURITY.value, severity=Severity.WARNING.value,
         evaluator=_check_no_personal_info, tags=["security"]),
    Rule(id="security.no_sensitive_words", name="无敏感词", description="不含敏感词",
         rule_type=RuleType.SECURITY.value, severity=Severity.CRITICAL.value,
         evaluator=_check_no_sensitive_words, tags=["security"]),

    # 关键词规则
    Rule(id="keywords.count", name="关键词数量", description="关键词3-5个",
         rule_type=RuleType.STRUCTURE.value, severity=Severity.WARNING.value,
         evaluator=_check_keywords_count, tags=["keywords"]),
    Rule(id="keywords.no_duplicate", name="关键词无重复", description="关键词无重复",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_no_duplicate_keywords, tags=["keywords"]),

    # 其他内容规则
    Rule(id="inspiration.not_empty", name="灵感来源非空", description="灵感来源非空",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_inspiration_source_not_empty, tags=["inspiration"]),
    Rule(id="significance.not_empty", name="研究意义非空", description="研究意义非空",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_research_significance_not_empty, tags=["significance"]),
    Rule(id="differentiation.not_empty", name="差异化非空", description="差异化声明非空",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_differentiation_not_empty, tags=["differentiation"]),
    Rule(id="literature_review.not_empty", name="文献综述非空", description="包含文献综述",
         rule_type=RuleType.ACADEMIC.value, severity=Severity.WARNING.value,
         evaluator=_check_has_literature_review, tags=["literature_review"]),

    # 预算规则
    Rule(id="budget.within_limit", name="预算限额", description="预算在限额内",
         rule_type=RuleType.BUDGET.value, severity=Severity.WARNING.value,
         evaluator=_check_budget_within_limit, tags=["budget"]),

    # 配置规则
    Rule(id="config.model_configured", name="模型已配置", description="模型已配置",
         rule_type=RuleType.COMPLIANCE.value, severity=Severity.ERROR.value,
         evaluator=_check_model_configured, tags=["config"]),
    Rule(id="config.api_key_configured", name="API密钥已配置", description="API密钥已配置",
         rule_type=RuleType.COMPLIANCE.value, severity=Severity.ERROR.value,
         evaluator=_check_api_key_configured, tags=["config"]),
    Rule(id="config.currency_valid", name="货币有效", description="货币类型有效",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_currency_valid, tags=["config"]),
    Rule(id="config.temperature_range", name="温度范围", description="温度在[0,2]范围",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_temperature_range, tags=["config"]),
    Rule(id="config.max_tokens_range", name="token数范围", description="最大token数在有效范围",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_max_tokens_range, tags=["config"]),
    Rule(id="config.model_id_format", name="模型ID格式", description="模型ID格式有效",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_model_id_format, tags=["config"]),
    Rule(id="config.base_url_format", name="URL格式", description="base_url格式有效",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_base_url_format, tags=["config"]),
    Rule(id="config.pricing_non_negative", name="定价非负", description="定价非负",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_pricing_non_negative, tags=["config"]),
    Rule(id="config.max_context_positive", name="上下文为正", description="max_context为正数",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_max_context_positive, tags=["config"]),
    Rule(id="config.release_year_range", name="年份范围", description="发布年份在有效范围",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_release_year_range, tags=["config"]),

    # 会话规则
    Rule(id="session.id_valid", name="会话ID有效", description="会话ID格式有效",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_session_id_valid, tags=["session"]),
    Rule(id="session.status_valid", name="会话状态有效", description="会话状态有效",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_session_status_valid, tags=["session"]),

    # 生成参数规则
    Rule(id="generate.granularity_valid", name="粒度有效", description="生成粒度有效",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_granularity_valid, tags=["generate"]),
    Rule(id="generate.mode_valid", name="模式有效", description="生成模式有效",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_mode_valid, tags=["generate"]),
    Rule(id="generate.count_range", name="数量范围", description="生成数量在[1,10]范围",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_count_range, tags=["generate"]),
    Rule(id="generate.mentor_info_length", name="导师信息长度", description="导师信息长度≤5000字",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_mentor_info_length, tags=["generate"]),

    # 分页规则
    Rule(id="pagination.limit", name="limit范围", description="limit在[1,100]范围",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_pagination_limit, tags=["pagination"]),
    Rule(id="pagination.offset", name="offset非负", description="offset非负",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_pagination_offset, tags=["pagination"]),

    # 搜索规则
    Rule(id="search.query_length", name="查询长度", description="搜索查询长度有效",
         rule_type=RuleType.FORMAT.value, severity=Severity.ERROR.value,
         evaluator=_check_search_query_length, tags=["search"]),
    Rule(id="search.years_range", name="年限范围", description="检索年限在[1,10]范围",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_search_years_range, tags=["search"]),

    # 图谱规则
    Rule(id="graph.no_circular", name="无循环引用", description="图谱无循环引用",
         rule_type=RuleType.STRUCTURE.value, severity=Severity.WARNING.value,
         evaluator=_check_no_circular_reference, tags=["graph"]),
    Rule(id="graph.node_count", name="节点数量", description="图谱节点数量合理",
         rule_type=RuleType.STRUCTURE.value, severity=Severity.WARNING.value,
         evaluator=_check_graph_node_count, tags=["graph"]),
    Rule(id="graph.edge_weight", name="边权重范围", description="边权重在[0,1]范围",
         rule_type=RuleType.FORMAT.value, severity=Severity.WARNING.value,
         evaluator=_check_edge_weight_range, tags=["graph"]),
]


# ===== 规则引擎 =====


class RuleEngine:
    """规则引擎

    管理规则集，执行规则评估，汇总评估结果。
    """

    def __init__(self):
        self._rules: dict[str, Rule] = {}
        self._lock = None
        self._load_predefined()

    def _load_predefined(self) -> None:
        """加载预定义规则。"""
        for rule in PREDEFINED_RULES:
            self._rules[rule.id] = rule

    def add_rule(self, rule: Rule) -> None:
        """添加规则。"""
        self._rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则。"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """获取规则。"""
        return self._rules.get(rule_id)

    def enable_rule(self, rule_id: str) -> bool:
        """启用规则。"""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则。"""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = False
            return True
        return False

    def list_rules(self, tag: Optional[str] = None, rule_type: Optional[str] = None) -> list:
        """列出规则。"""
        rules = list(self._rules.values())
        if tag:
            rules = [r for r in rules if tag in r.tags]
        if rule_type:
            rules = [r for r in rules if r.rule_type == rule_type]
        return [r.to_dict() for r in rules]

    def evaluate(self, data: dict, rule_ids: Optional[list] = None, tags: Optional[list] = None) -> list:
        """评估规则。

        Args:
            data: 待评估数据。
            rule_ids: 可选，指定评估的规则 ID 列表。
            tags: 可选，按标签过滤规则。

        Returns:
            RuleResult 列表。
        """
        results = []
        for rule_id, rule in self._rules.items():
            if rule_ids and rule_id not in rule_ids:
                continue
            if tags and not any(t in rule.tags for t in tags):
                continue
            result = rule.evaluate(data)
            results.append(result)
        return results

    def evaluate_all(self, data: dict) -> dict:
        """评估所有规则并返回汇总。

        Returns:
            {"passed": bool, "results": [...], "summary": {...}}
        """
        results = self.evaluate(data)
        passed = all(r.passed for r in results)
        errors = [r for r in results if not r.passed and r.severity == Severity.ERROR.value]
        warnings = [r for r in results if not r.passed and r.severity == Severity.WARNING.value]
        criticals = [r for r in results if not r.passed and r.severity == Severity.CRITICAL.value]
        return {
            "passed": passed and len(criticals) == 0 and len(errors) == 0,
            "results": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.passed),
                "failed": sum(1 for r in results if not r.passed),
                "errors": len(errors),
                "warnings": len(warnings),
                "criticals": len(criticals),
            },
        }

    def evaluate_by_tag(self, data: dict, tag: str) -> list:
        """按标签评估规则。"""
        return self.evaluate(data, tags=[tag])

    def evaluate_by_type(self, data: dict, rule_type: str) -> list:
        """按类型评估规则。"""
        results = []
        for rule in self._rules.values():
            if rule.rule_type == rule_type:
                results.append(rule.evaluate(data))
        return results

    def get_failed_rules(self, data: dict) -> list:
        """获取评估失败的规则。"""
        results = self.evaluate(data)
        return [r for r in results if not r.passed]

    def get_critical_issues(self, data: dict) -> list:
        """获取严重问题。"""
        results = self.evaluate(data)
        return [
            r for r in results
            if not r.passed and r.severity == Severity.CRITICAL.value
        ]

    def get_stats(self) -> dict:
        """获取规则引擎统计。"""
        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "disabled_rules": sum(1 for r in self._rules.values() if not r.enabled),
            "by_type": {
                t: sum(1 for r in self._rules.values() if r.rule_type == t)
                for t in RuleType.values()
            },
            "by_severity": {
                s: sum(1 for r in self._rules.values() if r.severity == s)
                for s in Severity.values()
            },
        }


# ===== 规则链 =====


class RuleChain:
    """规则链

    将多个规则串联执行，前一个规则通过才执行下一个。
    """

    def __init__(self, name: str = ""):
        self.name = name
        self._rules: list[Rule] = []
        self._stop_on_failure: bool = True

    def add(self, rule: Rule) -> "RuleChain":
        """添加规则到链。"""
        self._rules.append(rule)
        return self

    def set_stop_on_failure(self, stop: bool) -> "RuleChain":
        """设置失败时是否停止。"""
        self._stop_on_failure = stop
        return self

    def evaluate(self, data: dict) -> list:
        """按顺序评估规则链。"""
        results = []
        for rule in self._rules:
            result = rule.evaluate(data)
            results.append(result)
            if not result.passed and self._stop_on_failure:
                break
        return results

    def get_rules(self) -> list:
        """获取链中所有规则。"""
        return [r.to_dict() for r in self._rules]


# ===== 冲突解决器 =====


class ConflictResolver:
    """冲突解决器

    当多个规则对同一字段给出冲突结果时，按优先级解决冲突。
    """

    # 严重级别优先级（数值越高优先级越高）
    SEVERITY_PRIORITY = {
        Severity.CRITICAL.value: 4,
        Severity.ERROR.value: 3,
        Severity.WARNING.value: 2,
        Severity.INFO.value: 1,
    }

    def resolve(self, results: list) -> list:
        """解决冲突。

        对同一字段的多个失败结果，保留最高优先级的结果。

        Args:
            results: RuleResult 列表。

        Returns:
            解决冲突后的结果列表。
        """
        # 按字段分组
        by_field: dict[str, list] = {}
        no_field = []
        for result in results:
            if result.field:
                by_field.setdefault(result.field, []).append(result)
            else:
                no_field.append(result)

        resolved = list(no_field)
        for field, field_results in by_field.items():
            # 仅对失败结果解决冲突
            failed = [r for r in field_results if not r.passed]
            passed = [r for r in field_results if r.passed]
            if not failed:
                resolved.extend(passed)
                continue
            # 按优先级排序，保留最高优先级的失败结果
            failed.sort(
                key=lambda r: self.SEVERITY_PRIORITY.get(r.severity, 0),
                reverse=True,
            )
            resolved.append(failed[0])

        return resolved


# ===== 全局实例 =====

_global_engine = RuleEngine()


def get_rule_engine() -> RuleEngine:
    """获取全局规则引擎。"""
    return _global_engine


def evaluate_data(data: dict, **kwargs) -> dict:
    """便捷函数：评估数据。"""
    return _global_engine.evaluate_all(data, **kwargs)


def get_predefined_rules() -> list:
    """获取预定义规则列表。"""
    return [r.to_dict() for r in PREDEFINED_RULES]
