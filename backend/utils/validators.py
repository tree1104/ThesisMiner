"""输入验证工具集

提供全面的输入验证能力，覆盖 ThesisMiner 各业务场景所需的字段校验。
包括：邮箱、URL、电话、日期、学位、学科、标题、摘要、论题等验证器。

核心组件：
    - 自定义异常类：ValidationError 及其子类
    - 基础验证器：字符串、数字、日期、枚举等通用验证
    - 业务验证器：学位、学科、标题、摘要、论题等业务特定验证
    - Pydantic 模型：所有 API 输入的 Pydantic 模型定义
    - 验证器注册表：支持动态注册自定义验证器

设计原则：
    1. 纯函数：所有验证器为无副作用纯函数，返回验证结果
    2. 可组合：验证器可通过 validate_all 组合使用
    3. 详细错误：验证失败返回结构化错误信息（字段、规则、消息）
    4. 零依赖：仅使用 Python 标准库与 pydantic（项目已有依赖）
"""
import re
import os
import sys
from datetime import datetime, date
from enum import Enum
from typing import Any, Callable, Optional, Union

# 延迟导入 pydantic，避免循环依赖
try:
    from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
    from pydantic import EmailStr as _PydanticEmailStr  # noqa: F401
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    # 提供 BaseModel 的最小化替代，使模块可独立导入
    class BaseModel:  # type: ignore
        pass

    def Field(default=None, **kwargs):
        return default

    def field_validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def model_validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def ConfigDict(**kwargs):
        return {}


# ===== 自定义异常类 =====


class ValidationError(Exception):
    """验证异常基类

    所有验证失败的异常都继承自此基类。
    包含字段名、错误码与详细消息，便于前端展示与日志记录。
    """

    def __init__(self, message: str, field: str = "", code: str = "validation_error", details: Optional[dict] = None):
        super().__init__(message)
        self.field = field
        self.code = code
        self.details = details or {}
        self.message = message

    def to_dict(self) -> dict:
        """转换为字典表示。"""
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        if self.field:
            return f"[{self.field}] {self.message} (code: {self.code})"
        return f"{self.message} (code: {self.code})"


class RequiredFieldError(ValidationError):
    """必填字段缺失异常"""

    def __init__(self, field: str, message: str = ""):
        super().__init__(
            message or f"字段 '{field}' 为必填项",
            field=field,
            code="required_field_missing",
        )


class InvalidFormatError(ValidationError):
    """格式无效异常"""

    def __init__(self, field: str, value: str, expected_format: str = ""):
        message = f"字段 '{field}' 的值 '{value}' 格式无效"
        if expected_format:
            message += f"，期望格式: {expected_format}"
        super().__init__(message, field=field, code="invalid_format")
        self.value = value
        self.expected_format = expected_format


class OutOfRangeError(ValidationError):
    """超出范围异常"""

    def __init__(self, field: str, value: Any, min_value: Any = None, max_value: Any = None):
        message = f"字段 '{field}' 的值 {value} 超出范围"
        if min_value is not None and max_value is not None:
            message += f"，有效范围: [{min_value}, {max_value}]"
        elif min_value is not None:
            message += f"，最小值: {min_value}"
        elif max_value is not None:
            message += f"，最大值: {max_value}"
        super().__init__(message, field=field, code="out_of_range")
        self.value = value
        self.min_value = min_value
        self.max_value = max_value


class InvalidLengthError(ValidationError):
    """长度无效异常"""

    def __init__(self, field: str, actual_length: int, min_length: int = 0, max_length: int = 0):
        message = f"字段 '{field}' 的长度 {actual_length} 无效"
        if min_length and max_length:
            message += f"，有效长度: [{min_length}, {max_length}]"
        elif min_length:
            message += f"，最小长度: {min_length}"
        elif max_length:
            message += f"，最大长度: {max_length}"
        super().__init__(message, field=field, code="invalid_length")
        self.actual_length = actual_length
        self.min_length = min_length
        self.max_length = max_length


class InvalidEnumValueError(ValidationError):
    """枚举值无效异常"""

    def __init__(self, field: str, value: str, valid_values: list):
        message = f"字段 '{field}' 的值 '{value}' 无效，有效值: {valid_values}"
        super().__init__(message, field=field, code="invalid_enum_value")
        self.value = value
        self.valid_values = valid_values


class SecurityValidationError(ValidationError):
    """安全验证异常

    用于输入中包含潜在恶意内容（XSS、SQL 注入等）的情况。
    """

    def __init__(self, field: str, message: str = ""):
        super().__init__(
            message or f"字段 '{field}' 包含不安全的内容",
            field=field,
            code="security_violation",
        )


# ===== 验证结果类 =====


class ValidationResult:
    """验证结果

    封装验证器的返回值，包含是否通过、错误列表与净化后的值。
    """

    def __init__(self, is_valid: bool, value: Any = None, errors: Optional[list] = None):
        self.is_valid = is_valid
        self.value = value
        self.errors = errors or []

    def add_error(self, error: ValidationError) -> None:
        """添加错误。"""
        self.errors.append(error)
        self.is_valid = False

    def to_dict(self) -> dict:
        """转换为字典表示。"""
        return {
            "is_valid": self.is_valid,
            "value": self.value,
            "errors": [e.to_dict() if isinstance(e, ValidationError) else e for e in self.errors],
        }

    def __bool__(self) -> bool:
        return self.is_valid


# ===== 常量定义 =====

# 学位层次枚举
VALID_DEGREES = ["master", "doctor", "bachelor", "postdoc"]

# 学位中文映射
DEGREE_LABELS = {
    "master": "硕士",
    "doctor": "博士",
    "bachelor": "本科",
    "postdoc": "博士后",
}

# 标题最大长度（中文字符数）
MAX_TITLE_LENGTH = 20

# 摘要长度范围
ABSTRACT_MIN_LENGTH = 50
ABSTRACT_MAX_LENGTH = 1000

# 标题长度范围
TITLE_MIN_LENGTH = 4

# 学科分类（一级学科代码示例）
VALID_DISCIPLINES = [
    # 哲学
    "philosophy", "marxism", "logic", "ethics", "aesthetics", "religion",
    # 经济学
    "economics", "theoretical_economics", "applied_economics",
    # 法学
    "law", "jurisprudence", "constitutional_law", "criminal_law", "civil_law",
    # 教育学
    "education", "pedagogy", "psychology", "physical_education",
    # 文学
    "literature", "chinese_literature", "foreign_literature", "linguistics",
    # 历史学
    "history", "archaeology", "world_history",
    # 理学
    "mathematics", "physics", "chemistry", "biology", "astronomy", "geography",
    # 工学
    "engineering", "mechanical_engineering", "electrical_engineering",
    "computer_science", "civil_engineering", "chemical_engineering",
    "materials_science", "environmental_engineering", "software_engineering",
    "artificial_intelligence", "data_science", "cybersecurity",
    # 农学
    "agriculture", "agronomy", "veterinary_medicine", "forestry",
    # 医学
    "medicine", "basic_medicine", "clinical_medicine", "public_health",
    "chinese_medicine", "pharmacy",
    # 管理学
    "management", "business_administration", "public_administration",
    "information_management", "project_management",
    # 艺术学
    "arts", "music", "fine_arts", "design", "drama", "film_studies",
]

# 生成粒度
VALID_GRANULARITIES = ["topic", "outline", "paragraph", "section", "full"]

# 会话状态
VALID_SESSION_STATUSES = ["active", "closed", "completed", "archived"]

# 生成模式
VALID_MODES = ["quick", "deep", "balanced"]

# 货币类型
VALID_CURRENCIES = ["CNY", "USD"]

# 中文标题中应避免的主动动词
ACTIVE_VERBS = [
    "研究", "分析", "探讨", "调查", "实现", "构建",
    "设计", "开发", "优化", "改进", "评估", "验证",
]

# 邮箱正则（RFC 5322 简化版）
EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)

# URL 正则
URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:\S+(?::\S*)?@)?"
    r"(?:(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])"
    r"(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){3}"
    r"|"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)"
    r")"
    r"(?::\d{2,5})?"
    r"(?:[/?]\S*)?$"
)

# 中国手机号正则
PHONE_CN_PATTERN = re.compile(r"^1[3-9]\d{9}$")

# 国际电话号码正则（E.164 格式）
PHONE_E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")

# 日期格式列表
DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y年%m月%d日",
    "%Y%m%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
]

# UUID 正则
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# 潜在 XSS / SQL 注入特征
XSS_PATTERNS = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"<iframe[^>]*>", re.IGNORECASE),
    re.compile(r"<object[^>]*>", re.IGNORECASE),
    re.compile(r"<embed[^>]*>", re.IGNORECASE),
]

SQL_INJECTION_PATTERNS = [
    re.compile(r"'\s*OR\s*'?\d*'?\s*=\s*'?\d*", re.IGNORECASE),
    re.compile(r"'\s*OR\s*'?'?\s*=\s*'?'?", re.IGNORECASE),
    re.compile(r"UNION\s+SELECT", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"DELETE\s+FROM", re.IGNORECASE),
    re.compile(r"INSERT\s+INTO", re.IGNORECASE),
    re.compile(r"--\s*$", re.IGNORECASE),
    re.compile(r";\s*DROP", re.IGNORECASE),
]


# ===== 基础验证器 =====


def validate_required(value: Any, field: str = "field") -> ValidationResult:
    """验证必填字段不为空。

    Args:
        value: 待验证的值。
        field: 字段名（用于错误消息）。

    Returns:
        ValidationResult 实例。
    """
    result = ValidationResult(is_valid=True, value=value)
    if value is None:
        result.add_error(RequiredFieldError(field))
        return result
    if isinstance(value, str) and value.strip() == "":
        result.add_error(RequiredFieldError(field))
        return result
    if isinstance(value, (list, dict)) and len(value) == 0:
        result.add_error(RequiredFieldError(field))
        return result
    return result


def validate_string(
    value: Any,
    field: str = "field",
    min_length: int = 0,
    max_length: int = 0,
    allow_empty: bool = False,
    pattern: Optional[str] = None,
) -> ValidationResult:
    """验证字符串字段。

    Args:
        value: 待验证的值。
        field: 字段名。
        min_length: 最小长度（0 表示不限制）。
        max_length: 最大长度（0 表示不限制）。
        allow_empty: 是否允许空字符串。
        pattern: 可选，正则模式。

    Returns:
        ValidationResult 实例。
    """
    result = ValidationResult(is_valid=True)

    if value is None:
        if allow_empty:
            result.value = ""
            return result
        result.add_error(RequiredFieldError(field))
        return result

    if not isinstance(value, str):
        result.add_error(InvalidFormatError(field, str(value), "字符串"))
        return result

    if not allow_empty and value.strip() == "":
        result.add_error(RequiredFieldError(field))
        return result

    length = len(value)
    if min_length and length < min_length:
        result.add_error(InvalidLengthError(field, length, min_length=min_length))
    if max_length and length > max_length:
        result.add_error(InvalidLengthError(field, length, max_length=max_length))

    if pattern:
        if not re.match(pattern, value):
            result.add_error(InvalidFormatError(field, value, f"匹配模式 {pattern}"))

    if result.is_valid:
        result.value = value.strip() if not allow_empty else value
    return result


def validate_integer(
    value: Any,
    field: str = "field",
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    allow_none: bool = False,
) -> ValidationResult:
    """验证整数字段。

    Args:
        value: 待验证的值。
        field: 字段名。
        min_value: 最小值。
        max_value: 最大值。
        allow_none: 是否允许 None。

    Returns:
        ValidationResult 实例。
    """
    result = ValidationResult(is_valid=True)

    if value is None:
        if allow_none:
            result.value = None
            return result
        result.add_error(RequiredFieldError(field))
        return result

    # 尝试转换为整数
    try:
        if isinstance(value, bool):
            raise ValueError("布尔值不是有效整数")
        int_value = int(value)
        if isinstance(value, str) and value.strip() != str(int_value):
            raise ValueError("字符串无法转换为整数")
    except (ValueError, TypeError):
        result.add_error(InvalidFormatError(field, str(value), "整数"))
        return result

    if min_value is not None and int_value < min_value:
        result.add_error(OutOfRangeError(field, int_value, min_value=min_value))
    if max_value is not None and int_value > max_value:
        result.add_error(OutOfRangeError(field, int_value, max_value=max_value))

    if result.is_valid:
        result.value = int_value
    return result


def validate_float(
    value: Any,
    field: str = "field",
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    allow_none: bool = False,
) -> ValidationResult:
    """验证浮点数字段。"""
    result = ValidationResult(is_valid=True)

    if value is None:
        if allow_none:
            result.value = None
            return result
        result.add_error(RequiredFieldError(field))
        return result

    try:
        if isinstance(value, bool):
            raise ValueError("布尔值不是有效浮点数")
        float_value = float(value)
    except (ValueError, TypeError):
        result.add_error(InvalidFormatError(field, str(value), "浮点数"))
        return result

    if min_value is not None and float_value < min_value:
        result.add_error(OutOfRangeError(field, float_value, min_value=min_value))
    if max_value is not None and float_value > max_value:
        result.add_error(OutOfRangeError(field, float_value, max_value=max_value))

    if result.is_valid:
        result.value = float_value
    return result


def validate_boolean(value: Any, field: str = "field", allow_none: bool = False) -> ValidationResult:
    """验证布尔字段。

    支持真正的布尔值以及字符串 "true"/"false"/"1"/"0"/"yes"/"no"。
    """
    result = ValidationResult(is_valid=True)

    if value is None:
        if allow_none:
            result.value = None
            return result
        result.add_error(RequiredFieldError(field))
        return result

    if isinstance(value, bool):
        result.value = value
        return result

    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ("true", "1", "yes", "on"):
            result.value = True
            return result
        if lower in ("false", "0", "no", "off"):
            result.value = False
            return result

    if isinstance(value, (int, float)):
        if value == 1:
            result.value = True
            return result
        if value == 0:
            result.value = False
            return result

    result.add_error(InvalidFormatError(field, str(value), "布尔值"))
    return result


def validate_enum(
    value: Any,
    valid_values: list,
    field: str = "field",
    case_sensitive: bool = True,
    allow_none: bool = False,
) -> ValidationResult:
    """验证枚举值字段。"""
    result = ValidationResult(is_valid=True)

    if value is None:
        if allow_none:
            result.value = None
            return result
        result.add_error(RequiredFieldError(field))
        return result

    check_value = value if case_sensitive else str(value).lower()
    check_values = valid_values if case_sensitive else [str(v).lower() for v in valid_values]

    if check_value not in check_values:
        result.add_error(InvalidEnumValueError(field, str(value), valid_values))
        return result

    result.value = value
    return result


def validate_list(
    value: Any,
    field: str = "field",
    min_length: int = 0,
    max_length: int = 0,
    item_validator: Optional[Callable] = None,
    allow_none: bool = False,
) -> ValidationResult:
    """验证列表字段。

    Args:
        value: 待验证的值。
        field: 字段名。
        min_length: 最小元素数。
        max_length: 最大元素数。
        item_validator: 可选，对每个元素调用的验证器。
        allow_none: 是否允许 None。
    """
    result = ValidationResult(is_valid=True)

    if value is None:
        if allow_none:
            result.value = None
            return result
        result.add_error(RequiredFieldError(field))
        return result

    if not isinstance(value, list):
        result.add_error(InvalidFormatError(field, str(value), "列表"))
        return result

    length = len(value)
    if min_length and length < min_length:
        result.add_error(InvalidLengthError(field, length, min_length=min_length))
    if max_length and length > max_length:
        result.add_error(InvalidLengthError(field, length, max_length=max_length))

    if item_validator and result.is_valid:
        validated_items = []
        for i, item in enumerate(value):
            item_result = item_validator(item, f"{field}[{i}]")
            if not item_result.is_valid:
                result.errors.extend(item_result.errors)
                result.is_valid = False
            else:
                validated_items.append(item_result.value)
        if result.is_valid:
            result.value = validated_items
    elif result.is_valid:
        result.value = value

    return result


def validate_dict(
    value: Any,
    field: str = "field",
    required_keys: Optional[list] = None,
    optional_keys: Optional[list] = None,
    allow_none: bool = False,
) -> ValidationResult:
    """验证字典字段。"""
    result = ValidationResult(is_valid=True)

    if value is None:
        if allow_none:
            result.value = None
            return result
        result.add_error(RequiredFieldError(field))
        return result

    if not isinstance(value, dict):
        result.add_error(InvalidFormatError(field, str(value), "字典"))
        return result

    if required_keys:
        for key in required_keys:
            if key not in value:
                result.add_error(RequiredFieldError(f"{field}.{key}"))

    if result.is_valid:
        result.value = value
    return result


# ===== 业务验证器 =====


def validate_email(email: str, field: str = "email") -> ValidationResult:
    """验证邮箱地址格式。

    Args:
        email: 待验证的邮箱字符串。
        field: 字段名。

    Returns:
        ValidationResult 实例。
    """
    result = validate_required(email, field)
    if not result:
        return result

    email = email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        result.add_error(InvalidFormatError(field, email, "邮箱地址"))
        return result

    # 额外检查：长度限制
    if len(email) > 254:
        result.add_error(InvalidLengthError(field, len(email), max_length=254))
        return result

    # 检查域名部分
    domain = email.split("@")[1] if "@" in email else ""
    if not domain or "." not in domain:
        result.add_error(InvalidFormatError(field, email, "有效邮箱域名"))
        return result

    result.value = email
    return result


def validate_url(url: str, field: str = "url", allowed_schemes: Optional[list] = None) -> ValidationResult:
    """验证 URL 格式。

    Args:
        url: 待验证的 URL 字符串。
        field: 字段名。
        allowed_schemes: 允许的协议列表（默认 http/https）。
    """
    result = validate_required(url, field)
    if not result:
        return result

    url = url.strip()
    if not URL_PATTERN.match(url):
        result.add_error(InvalidFormatError(field, url, "URL"))
        return result

    if allowed_schemes is None:
        allowed_schemes = ["http", "https"]

    scheme = url.split("://")[0].lower() if "://" in url else ""
    if scheme not in allowed_schemes:
        result.add_error(
            InvalidEnumValueError(field, scheme, allowed_schemes)
        )
        return result

    # 长度检查
    if len(url) > 2048:
        result.add_error(InvalidLengthError(field, len(url), max_length=2048))
        return result

    result.value = url
    return result


def validate_phone(phone: str, field: str = "phone", region: str = "CN") -> ValidationResult:
    """验证电话号码格式。

    Args:
        phone: 待验证的电话号码字符串。
        field: 字段名。
        region: 地区（CN 中国 / E164 国际格式）。
    """
    result = validate_required(phone, field)
    if not result:
        return result

    phone = phone.strip()

    if region.upper() == "CN":
        if not PHONE_CN_PATTERN.match(phone):
            result.add_error(InvalidFormatError(field, phone, "中国手机号（1[3-9]xxxxxxxxx）"))
            return result
    elif region.upper() == "E164":
        if not PHONE_E164_PATTERN.match(phone):
            result.add_error(InvalidFormatError(field, phone, "E.164 国际格式（+国家码号码）"))
            return result
    else:
        # 通用验证：仅检查是否只包含数字、+、-、空格、括号
        if not re.match(r"^[\d+\-\s()]+$", phone):
            result.add_error(InvalidFormatError(field, phone, "电话号码"))
            return result

    result.value = phone
    return result


def validate_date(
    value: Any,
    field: str = "date",
    formats: Optional[list] = None,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
    allow_none: bool = False,
) -> ValidationResult:
    """验证日期字段。

    Args:
        value: 待验证的值（字符串或 date/datetime 对象）。
        field: 字段名。
        formats: 可选，尝试的日期格式列表。
        min_date: 最小日期。
        max_date: 最大日期。
        allow_none: 是否允许 None。
    """
    result = ValidationResult(is_valid=True)

    if value is None:
        if allow_none:
            result.value = None
            return result
        result.add_error(RequiredFieldError(field))
        return result

    if isinstance(value, datetime):
        parsed_date = value.date()
    elif isinstance(value, date):
        parsed_date = value
    elif isinstance(value, str):
        parsed_date = None
        for fmt in (formats or DATE_FORMATS):
            try:
                parsed_date = datetime.strptime(value.strip(), fmt).date()
                break
            except ValueError:
                continue
        if parsed_date is None:
            result.add_error(InvalidFormatError(field, value, f"日期格式（如 {formats or DATE_FORMATS[0]}）"))
            return result
    else:
        result.add_error(InvalidFormatError(field, str(value), "日期"))
        return result

    if min_date and parsed_date < min_date:
        result.add_error(OutOfRangeError(field, str(parsed_date), min_value=str(min_date)))
    if max_date and parsed_date > max_date:
        result.add_error(OutOfRangeError(field, str(parsed_date), max_value=str(max_date)))

    if result.is_valid:
        result.value = parsed_date
    return result


def validate_degree(degree: str, field: str = "degree") -> ValidationResult:
    """验证学位层次。

    Args:
        degree: 学位标识字符串。
        field: 字段名。

    Returns:
        ValidationResult 实例。
    """
    result = validate_enum(degree, VALID_DEGREES, field=field, case_sensitive=False)
    if result:
        result.value = degree.lower()
    return result


def validate_discipline(discipline: str, field: str = "discipline") -> ValidationResult:
    """验证学科方向。

    Args:
        discipline: 学科标识字符串。
        field: 字段名。
    """
    result = validate_required(discipline, field)
    if not result:
        return result

    discipline = discipline.strip().lower()
    if discipline not in VALID_DISCIPLINES:
        result.add_error(InvalidEnumValueError(field, discipline, VALID_DISCIPLINES))
        return result

    result.value = discipline
    return result


def validate_title(title: str, field: str = "title") -> ValidationResult:
    """验证论题标题格式。

    校验规则：
        1. 长度在 [TITLE_MIN_LENGTH, MAX_TITLE_LENGTH] 范围内。
        2. 不以主动动词开头。
        3. 不匹配"基于X的Y研究"模式。
        4. 不包含 HTML 标签。

    Args:
        title: 待验证的标题字符串。
        field: 字段名。
    """
    result = validate_string(
        title, field=field,
        min_length=TITLE_MIN_LENGTH,
        max_length=MAX_TITLE_LENGTH,
    )
    if not result:
        return result

    title = title.strip()

    # 检查主动动词开头
    for verb in ACTIVE_VERBS:
        if title.startswith(verb):
            result.add_error(
                InvalidFormatError(field, title, f"不以主动动词 '{verb}' 开头")
            )
            break

    # 检查"基于X的Y研究"模式
    based_pattern = re.compile(
        r"^基于.+的.*(研究|分析|探讨|调查|实现|构建|设计|开发|优化|改进|评估|验证)$"
    )
    if based_pattern.match(title):
        result.add_error(
            InvalidFormatError(field, title, "不匹配'基于X的Y研究'模式")
        )

    # 检查 HTML 标签
    if re.search(r"<[^>]+>", title):
        result.add_error(SecurityValidationError(field, "标题包含 HTML 标签"))

    if result.is_valid:
        result.value = title
    return result


def validate_abstract(abstract: str, field: str = "abstract") -> ValidationResult:
    """验证摘要字段。

    校验规则：
        1. 长度在 [ABSTRACT_MIN_LENGTH, ABSTRACT_MAX_LENGTH] 范围内。
        2. 不包含 HTML 标签。
        3. 不包含潜在 XSS 内容。

    Args:
        abstract: 待验证的摘要字符串。
        field: 字段名。
    """
    result = validate_string(
        abstract, field=field,
        min_length=ABSTRACT_MIN_LENGTH,
        max_length=ABSTRACT_MAX_LENGTH,
    )
    if not result:
        return result

    abstract = abstract.strip()

    # 检查 HTML 标签
    if re.search(r"<[^>]+>", abstract):
        result.add_error(SecurityValidationError(field, "摘要包含 HTML 标签"))

    # 检查 XSS 模式
    for pattern in XSS_PATTERNS:
        if pattern.search(abstract):
            result.add_error(SecurityValidationError(field, "摘要包含潜在 XSS 内容"))
            break

    if result.is_valid:
        result.value = abstract
    return result


def validate_granularity(granularity: str, field: str = "granularity") -> ValidationResult:
    """验证生成粒度。"""
    return validate_enum(granularity, VALID_GRANULARITIES, field=field, case_sensitive=False)


def validate_session_status(status: str, field: str = "status") -> ValidationResult:
    """验证会话状态。"""
    return validate_enum(status, VALID_SESSION_STATUSES, field=field, case_sensitive=False)


def validate_mode(mode: str, field: str = "mode") -> ValidationResult:
    """验证生成模式。"""
    return validate_enum(mode, VALID_MODES, field=field, case_sensitive=False)


def validate_currency(currency: str, field: str = "currency") -> ValidationResult:
    """验证货币类型。"""
    return validate_enum(currency, VALID_CURRENCIES, field=field, case_sensitive=True)


def validate_uuid(uuid_str: str, field: str = "id") -> ValidationResult:
    """验证 UUID 格式。"""
    result = validate_required(uuid_str, field)
    if not result:
        return result

    uuid_str = uuid_str.strip()
    if not UUID_PATTERN.match(uuid_str):
        result.add_error(InvalidFormatError(field, uuid_str, "UUID 格式"))
        return result

    result.value = uuid_str.lower()
    return result


def validate_model_id(model_id: str, field: str = "model_id") -> ValidationResult:
    """验证模型 ID 格式。

    模型 ID 应只包含字母、数字、点、连字符。
    """
    result = validate_required(model_id, field)
    if not result:
        return result

    model_id = model_id.strip()
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9.\-]*$", model_id):
        result.add_error(InvalidFormatError(field, model_id, "模型 ID（字母数字点连字符）"))
        return result

    if len(model_id) > 100:
        result.add_error(InvalidLengthError(field, len(model_id), max_length=100))
        return result

    result.value = model_id
    return result


def validate_api_key(api_key: str, field: str = "api_key") -> ValidationResult:
    """验证 API 密钥格式。

    API 密钥应只包含字母、数字、连字符、下划线，长度在 10-200 之间。
    """
    result = validate_required(api_key, field)
    if not result:
        return result

    if not re.match(r"^[a-zA-Z0-9\-_]+$", api_key):
        result.add_error(InvalidFormatError(field, "***", "API 密钥（字母数字连字符下划线）"))
        return result

    if len(api_key) < 10:
        result.add_error(InvalidLengthError(field, len(api_key), min_length=10))
        return result

    if len(api_key) > 200:
        result.add_error(InvalidLengthError(field, len(api_key), max_length=200))
        return result

    result.value = api_key
    return result


def validate_base_url(url: str, field: str = "base_url") -> ValidationResult:
    """验证 AI 服务商 base_url。"""
    return validate_url(url, field=field, allowed_schemes=["http", "https"])


def validate_temperature(temp: Any, field: str = "temperature") -> ValidationResult:
    """验证温度参数（0.0 - 2.0）。"""
    return validate_float(temp, field=field, min_value=0.0, max_value=2.0)


def validate_max_tokens(tokens: Any, field: str = "max_tokens") -> ValidationResult:
    """验证最大 token 数（1 - 1000000）。"""
    return validate_integer(tokens, field=field, min_value=1, max_value=1000000)


def validate_mentor_info(mentor_info: str, field: str = "mentor_info") -> ValidationResult:
    """验证导师信息字段。

    导师信息可包含导师项目与同门论文，以换行分隔。
    """
    result = validate_string(mentor_info, field=field, max_length=5000, allow_empty=False)
    if not result:
        return result

    if mentor_info:
        # 检查 XSS
        for pattern in XSS_PATTERNS:
            if pattern.search(mentor_info):
                result.add_error(SecurityValidationError(field, "导师信息包含潜在 XSS 内容"))
                break

    if result.is_valid:
        result.value = mentor_info.strip() if mentor_info else ""
    return result


def validate_search_query(query: str, field: str = "query") -> ValidationResult:
    """验证搜索查询字符串。"""
    result = validate_string(query, field=field, min_length=1, max_length=500)
    if not result:
        return result

    query = query.strip()
    # 检查 SQL 注入特征
    for pattern in SQL_INJECTION_PATTERNS:
        if pattern.search(query):
            result.add_error(SecurityValidationError(field, "查询包含潜在 SQL 注入内容"))
            break

    if result.is_valid:
        result.value = query
    return result


def validate_pricing(pricing: dict, field: str = "pricing") -> ValidationResult:
    """验证模型定价配置。"""
    result = validate_dict(
        pricing, field=field,
        required_keys=["input_cny_per_million", "output_cny_per_million"],
    )
    if not result:
        return result

    input_price = pricing.get("input_cny_per_million")
    output_price = pricing.get("output_cny_per_million")

    input_result = validate_float(input_price, f"{field}.input_cny_per_million", min_value=0.0)
    if not input_result:
        result.errors.extend(input_result.errors)
        result.is_valid = False

    output_result = validate_float(output_price, f"{field}.output_cny_per_million", min_value=0.0)
    if not output_result:
        result.errors.extend(output_result.errors)
        result.is_valid = False

    if result.is_valid:
        result.value = pricing
    return result


def validate_model_config(config: dict, field: str = "model_config") -> ValidationResult:
    """验证完整模型配置。"""
    result = validate_dict(
        config, field=field,
        required_keys=["id", "label", "base_url", "pricing"],
    )
    if not result:
        return result

    # 验证各字段
    id_result = validate_model_id(config.get("id", ""), f"{field}.id")
    if not id_result:
        result.errors.extend(id_result.errors)
        result.is_valid = False

    label_result = validate_string(config.get("label", ""), f"{field}.label", min_length=1, max_length=100)
    if not label_result:
        result.errors.extend(label_result.errors)
        result.is_valid = False

    url_result = validate_base_url(config.get("base_url", ""), f"{field}.base_url")
    if not url_result:
        result.errors.extend(url_result.errors)
        result.is_valid = False

    pricing_result = validate_pricing(config.get("pricing", {}), f"{field}.pricing")
    if not pricing_result:
        result.errors.extend(pricing_result.errors)
        result.is_valid = False

    # 可选字段
    if "max_context" in config:
        ctx_result = validate_integer(config["max_context"], f"{field}.max_context", min_value=1000)
        if not ctx_result:
            result.errors.extend(ctx_result.errors)
            result.is_valid = False

    if "default_temperature" in config:
        temp_result = validate_temperature(config["default_temperature"], f"{field}.default_temperature")
        if not temp_result:
            result.errors.extend(temp_result.errors)
            result.is_valid = False

    if result.is_valid:
        result.value = config
    return result


def validate_pagination(
    page: Any = None, limit: Any = None, max_limit: int = 100, offset: Any = None,
) -> ValidationResult:
    """验证分页参数。

    支持两种调用方式：
        validate_pagination(page=1, limit=20)
        validate_pagination(limit=20, offset=0)
    """
    result = ValidationResult(is_valid=True)

    # 如果 page 提供，验证 page >= 1
    if page is not None:
        page_result = validate_integer(page, "page", min_value=1)
        if not page_result:
            result.errors.extend(page_result.errors)
            result.is_valid = False
    elif offset is not None:
        offset_result = validate_integer(offset, "offset", min_value=0)
        if not offset_result:
            result.errors.extend(offset_result.errors)
            result.is_valid = False

    if limit is not None:
        limit_result = validate_integer(limit, "limit", min_value=1, max_value=max_limit)
        if not limit_result:
            result.errors.extend(limit_result.errors)
            result.is_valid = False

    if result.is_valid:
        value: dict = {}
        if page is not None:
            value["page"] = int(page)
        if limit is not None:
            value["limit"] = int(limit)
        if offset is not None:
            value["offset"] = int(offset)
        result.value = value
    return result


def validate_all(*validators: Callable) -> ValidationResult:
    """组合多个验证器，全部通过才返回有效结果。

    Args:
        *validators: 验证器调用（无参 Callable，返回 ValidationResult）。

    Returns:
        合并后的 ValidationResult。
    """
    combined = ValidationResult(is_valid=True, value={})
    for validator in validators:
        single_result = validator()
        if not single_result.is_valid:
            combined.errors.extend(single_result.errors)
            combined.is_valid = False
        else:
            combined.value.update(single_result.value if isinstance(single_result.value, dict) else {})
    return combined


# ===== 安全检查函数 =====


def check_xss(value: str, field: str = "field") -> bool:
    """检查字符串是否包含 XSS 攻击特征。

    Args:
        value: 待检查的字符串。
        field: 字段名。

    Returns:
        True 表示安全，False 表示包含 XSS 特征。
    """
    if not isinstance(value, str):
        return True
    for pattern in XSS_PATTERNS:
        if pattern.search(value):
            return False
    return True


def check_sql_injection(value: str, field: str = "field") -> bool:
    """检查字符串是否包含 SQL 注入特征。

    Args:
        value: 待检查的字符串。
        field: 字段名。

    Returns:
        True 表示安全，False 表示包含 SQL 注入特征。
    """
    if not isinstance(value, str):
        return True
    for pattern in SQL_INJECTION_PATTERNS:
        if pattern.search(value):
            return False
    return True


def sanitize_html(value: str) -> str:
    """移除字符串中的 HTML 标签。

    Args:
        value: 原始字符串。

    Returns:
        移除 HTML 标签后的纯文本。
    """
    if not isinstance(value, str):
        return value
    # 移除所有 HTML 标签
    cleaned = re.sub(r"<[^>]+>", "", value)
    # 解码常见 HTML 实体
    entities = {
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
        "&nbsp;": " ",
    }
    for entity, char in entities.items():
        cleaned = cleaned.replace(entity, char)
    return cleaned


# ===== Pydantic 模型定义 =====
# 以下模型用于 API 请求体校验，与 FastAPI 路由配合使用。


if HAS_PYDANTIC:

    class ProposalGenerateRequest(BaseModel):
        """论题生成请求模型"""
        model_config = ConfigDict(extra="forbid")

        degree: str = Field(..., description="学位层次（master/doctor）")
        discipline: str = Field(..., description="学科方向")
        mentor_info: str = Field("", description="导师与同门信息")
        mode: str = Field("balanced", description="生成模式")
        count: int = Field(3, ge=1, le=10, description="生成数量")
        session_id: str = Field("", description="会话 ID")

        @field_validator("degree")
        @classmethod
        def validate_degree_field(cls, v):
            result = validate_degree(v)
            if not result:
                raise ValueError(str(result.errors[0]))
            return result.value

        @field_validator("mode")
        @classmethod
        def validate_mode_field(cls, v):
            result = validate_mode(v)
            if not result:
                raise ValueError(str(result.errors[0]))
            return result.value

        @field_validator("discipline")
        @classmethod
        def validate_discipline_field(cls, v):
            v = v.strip().lower()
            if not v:
                raise ValueError("学科方向不能为空")
            return v

        @field_validator("mentor_info")
        @classmethod
        def validate_mentor_info_field(cls, v):
            if v and not check_xss(v):
                raise ValueError("导师信息包含不安全内容")
            return v

    class ConfigUpdateRequest(BaseModel):
        """配置更新请求模型"""
        model_config = ConfigDict(extra="allow")

        ai_api_key: Optional[str] = Field(None, description="AI API 密钥")
        ai_base_url: Optional[str] = Field(None, description="AI 基础 URL")
        ai_model: Optional[str] = Field(None, description="默认模型")
        db_path: Optional[str] = Field(None, description="数据库路径")
        log_level: Optional[str] = Field(None, description="日志级别")
        flask_env: Optional[str] = Field(None, description="运行环境")

        @field_validator("ai_base_url")
        @classmethod
        def validate_base_url(cls, v):
            if v is not None:
                result = validate_base_url(v)
                if not result:
                    raise ValueError(str(result.errors[0]))
            return v

        @field_validator("log_level")
        @classmethod
        def validate_log_level(cls, v):
            if v is not None:
                valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "TRACE"]
                if v.upper() not in valid_levels:
                    raise ValueError(f"日志级别无效，有效值: {valid_levels}")
                return v.upper()
            return v

    class SessionCreateRequest(BaseModel):
        """会话创建请求模型"""
        model_config = ConfigDict(extra="forbid")

        title: str = Field(..., min_length=1, max_length=200, description="会话标题")
        degree: str = Field("master", description="学位层次")
        discipline: str = Field("", description="学科方向")
        mentor_info: str = Field("", description="导师信息")

        @field_validator("degree")
        @classmethod
        def validate_degree_field(cls, v):
            result = validate_degree(v)
            if not result:
                raise ValueError(str(result.errors[0]))
            return result.value

        @field_validator("title")
        @classmethod
        def validate_title_field(cls, v):
            if not check_xss(v):
                raise ValueError("标题包含不安全内容")
            return v.strip()

    class ModelCreateRequest(BaseModel):
        """模型创建请求模型"""
        model_config = ConfigDict(extra="forbid")

        id: str = Field(..., min_length=1, max_length=100, description="模型 ID")
        label: str = Field(..., min_length=1, max_length=100, description="模型标签")
        base_url: str = Field(..., description="基础 URL")
        api_key: str = Field("", description="API 密钥")
        pricing: dict = Field(..., description="定价配置")
        supports_streaming: bool = Field(True, description="是否支持流式")
        supports_thinking: bool = Field(False, description="是否支持思维链")
        supports_web_search: bool = Field(False, description="是否支持联网搜索")
        max_context: int = Field(128000, ge=1000, description="最大上下文长度")
        default_temperature: float = Field(0.7, ge=0.0, le=2.0, description="默认温度")
        agent_default: str = Field("", description="默认 Agent 角色")
        release_year: int = Field(2026, ge=2000, le=2100, description="发布年份")

        @field_validator("id")
        @classmethod
        def validate_id_field(cls, v):
            result = validate_model_id(v)
            if not result:
                raise ValueError(str(result.errors[0]))
            return result.value

        @field_validator("base_url")
        @classmethod
        def validate_base_url_field(cls, v):
            result = validate_base_url(v)
            if not result:
                raise ValueError(str(result.errors[0]))
            return result.value

        @field_validator("pricing")
        @classmethod
        def validate_pricing_field(cls, v):
            result = validate_pricing(v)
            if not result:
                raise ValueError(str(result.errors[0]))
            return v

    class StepModelsUpdateRequest(BaseModel):
        """步骤路由更新请求模型"""
        model_config = ConfigDict(extra="forbid")

        orchestrator: Optional[str] = Field(None, description="编排步骤模型")
        reasoner: Optional[str] = Field(None, description="推理步骤模型")
        mentor: Optional[str] = Field(None, description="导师步骤模型")
        inspire: Optional[str] = Field(None, description="创意步骤模型")
        report: Optional[str] = Field(None, description="报告步骤模型")
        search: Optional[str] = Field(None, description="检索步骤模型")

    class CurrencyUpdateRequest(BaseModel):
        """货币切换请求模型"""
        model_config = ConfigDict(extra="forbid")

        currency: str = Field(..., description="货币类型（CNY/USD）")

        @field_validator("currency")
        @classmethod
        def validate_currency_field(cls, v):
            result = validate_currency(v)
            if not result:
                raise ValueError(str(result.errors[0]))
            return result.value

    class LineageImportRequest(BaseModel):
        """谱系导入请求模型"""
        model_config = ConfigDict(extra="forbid")

        nodes: list = Field(..., min_length=1, description="节点列表")
        edges: list = Field(default_factory=list, description="边列表")

    class KnowledgeCardCreateRequest(BaseModel):
        """知识卡片创建请求模型"""
        model_config = ConfigDict(extra="forbid")

        title: str = Field(..., min_length=1, max_length=200, description="卡片标题")
        content: str = Field(..., min_length=1, max_length=10000, description="卡片内容")
        tags: list = Field(default_factory=list, description="标签列表")
        source: str = Field("", max_length=500, description="来源")

        @field_validator("title", "content")
        @classmethod
        def sanitize_fields(cls, v):
            if not check_xss(v):
                raise ValueError("内容包含不安全内容")
            return v

    class BudgetEstimateRequest(BaseModel):
        """预算估算请求模型"""
        model_config = ConfigDict(extra="forbid")

        degree: str = Field(..., description="学位层次")
        mode: str = Field("balanced", description="生成模式")
        count: int = Field(3, ge=1, le=10, description="生成数量")

        @field_validator("degree")
        @classmethod
        def validate_degree_field(cls, v):
            result = validate_degree(v)
            if not result:
                raise ValueError(str(result.errors[0]))
            return result.value

        @field_validator("mode")
        @classmethod
        def validate_mode_field(cls, v):
            result = validate_mode(v)
            if not result:
                raise ValueError(str(result.errors[0]))
            return result.value

    class ConstraintCheckRequest(BaseModel):
        """约束校验请求模型"""
        model_config = ConfigDict(extra="forbid")

        title: Optional[str] = Field(None, description="待校验标题")
        degree: Optional[str] = Field(None, description="学位层次")
        timeframe_months: Optional[int] = Field(None, ge=1, le=120, description="研究周期月数")
        count: Optional[int] = Field(None, ge=0, le=10000, description="文献数量")

        @field_validator("degree")
        @classmethod
        def validate_degree_field(cls, v):
            if v is not None:
                result = validate_degree(v)
                if not result:
                    raise ValueError(str(result.errors[0]))
                return result.value
            return v

    class SearchLiteratureRequest(BaseModel):
        """文献检索请求模型"""
        model_config = ConfigDict(extra="forbid")

        query: str = Field(..., min_length=1, max_length=500, description="检索关键词")
        years: int = Field(2, ge=1, le=10, description="检索年限")
        limit: int = Field(20, ge=1, le=100, description="结果数量上限")

        @field_validator("query")
        @classmethod
        def validate_query_field(cls, v):
            if not check_sql_injection(v):
                raise ValueError("查询包含不安全内容")
            return v.strip()

else:
    # 无 pydantic 时提供占位
    ProposalGenerateRequest = None
    ConfigUpdateRequest = None
    SessionCreateRequest = None
    ModelCreateRequest = None
    StepModelsUpdateRequest = None
    CurrencyUpdateRequest = None
    LineageImportRequest = None
    KnowledgeCardCreateRequest = None
    BudgetEstimateRequest = None
    ConstraintCheckRequest = None
    SearchLiteratureRequest = None


# ===== 验证器注册表 =====


class ValidatorRegistry:
    """验证器注册表

    支持动态注册自定义验证器，按名称检索。
    用于扩展验证能力，无需修改本模块代码。
    """

    def __init__(self):
        self._validators: dict[str, Callable] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """注册内置验证器。"""
        defaults = {
            "required": validate_required,
            "string": validate_string,
            "integer": validate_integer,
            "float": validate_float,
            "boolean": validate_boolean,
            "enum": validate_enum,
            "list": validate_list,
            "dict": validate_dict,
            "email": validate_email,
            "url": validate_url,
            "phone": validate_phone,
            "date": validate_date,
            "degree": validate_degree,
            "discipline": validate_discipline,
            "title": validate_title,
            "abstract": validate_abstract,
            "granularity": validate_granularity,
            "session_status": validate_session_status,
            "mode": validate_mode,
            "currency": validate_currency,
            "uuid": validate_uuid,
            "model_id": validate_model_id,
            "api_key": validate_api_key,
            "base_url": validate_base_url,
            "temperature": validate_temperature,
            "max_tokens": validate_max_tokens,
            "mentor_info": validate_mentor_info,
            "search_query": validate_search_query,
            "pricing": validate_pricing,
            "model_config": validate_model_config,
            "pagination": validate_pagination,
        }
        self._validators.update(defaults)

    def register(self, name: str, validator: Callable) -> None:
        """注册自定义验证器。

        Args:
            name: 验证器名称。
            validator: 验证器函数。
        """
        self._validators[name] = validator

    def get(self, name: str) -> Optional[Callable]:
        """获取验证器。"""
        return self._validators.get(name)

    def list_validators(self) -> list:
        """列出所有已注册验证器名称。"""
        return sorted(self._validators.keys())

    def validate(self, name: str, value: Any, **kwargs) -> ValidationResult:
        """调用指定验证器。

        Args:
            name: 验证器名称。
            value: 待验证的值。
            **kwargs: 验证器参数。

        Returns:
            ValidationResult 实例。
        """
        validator = self._validators.get(name)
        if validator is None:
            result = ValidationResult(is_valid=False)
            result.add_error(ValidationError(f"未知验证器: {name}", code="unknown_validator"))
            return result
        return validator(value, **kwargs)


# 全局验证器注册表实例
_registry = ValidatorRegistry()


def get_validator(name: str) -> Optional[Callable]:
    """获取验证器的便捷函数。"""
    return _registry.get(name)


def register_validator(name: str, validator: Callable) -> None:
    """注册验证器的便捷函数。"""
    _registry.register(name, validator)


def list_validators() -> list:
    """列出所有验证器。"""
    return _registry.list_validators()
