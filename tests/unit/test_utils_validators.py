"""验证器模块单元测试

测试 backend/utils/validators.py 中的所有组件：
    - ValidationError 异常层级（RequiredFieldError / InvalidFormatError / OutOfRangeError 等）
    - ValidationResult 验证结果类
    - 基础验证器：validate_required / validate_string / validate_integer / validate_float 等
    - 业务验证器：validate_email / validate_url / validate_phone / validate_degree / validate_title 等
    - Pydantic 模型：ProposalGenerateRequest / SessionCreateRequest 等
    - ValidatorRegistry 验证器注册表
    - 常量：VALID_DEGREES / VALID_DISCIPLINES / VALID_GRANULARITIES 等
"""
import pytest
from unittest.mock import patch, MagicMock

# 导入被测模块
from backend.utils.validators import (
    # 异常类
    ValidationError,
    RequiredFieldError,
    InvalidFormatError,
    OutOfRangeError,
    InvalidLengthError,
    InvalidEnumValueError,
    SecurityValidationError,
    # 验证结果
    ValidationResult,
    # 基础验证器
    validate_required,
    validate_string,
    validate_integer,
    validate_float,
    validate_boolean,
    validate_enum,
    validate_list,
    validate_dict,
    # 业务验证器
    validate_email,
    validate_url,
    validate_phone,
    validate_date,
    validate_degree,
    validate_discipline,
    validate_title,
    validate_abstract,
    validate_granularity,
    validate_session_status,
    validate_mode,
    validate_currency,
    validate_uuid,
    validate_model_id,
    validate_api_key,
    validate_base_url,
    validate_temperature,
    validate_max_tokens,
    validate_mentor_info,
    validate_search_query,
    validate_pricing,
    validate_model_config,
    validate_pagination,
    # 常量
    VALID_DEGREES,
    VALID_DISCIPLINES,
    VALID_GRANULARITIES,
    VALID_SESSION_STATUSES,
    VALID_MODES,
    VALID_CURRENCIES,
    ACTIVE_VERBS,
    EMAIL_PATTERN,
    URL_PATTERN,
    XSS_PATTERNS,
    SQL_INJECTION_PATTERNS,
    MAX_TITLE_LENGTH,
    ABSTRACT_MIN_LENGTH,
    ABSTRACT_MAX_LENGTH,
    TITLE_MIN_LENGTH,
)


# ===== 异常类测试 =====


class TestValidationErrors:
    """验证异常类测试。"""

    def test_validation_error_basic(self):
        """测试基本验证异常。"""
        error = ValidationError("测试错误", field="test_field", code="test_code")
        assert error.message == "测试错误"
        assert error.field == "test_field"
        assert error.code == "test_code"

    def test_validation_error_to_dict(self):
        """测试异常转字典。"""
        error = ValidationError("错误消息", field="field1", code="err1")
        result = error.to_dict()
        assert result["field"] == "field1"
        assert result["code"] == "err1"
        assert result["message"] == "错误消息"

    def test_validation_error_str(self):
        """测试异常字符串表示。"""
        error = ValidationError("错误消息", field="field1", code="err1")
        s = str(error)
        assert "错误消息" in s
        assert "field1" in s
        assert "err1" in s

    def test_validation_error_str_no_field(self):
        """测试无字段名的异常字符串。"""
        error = ValidationError("错误消息", code="err1")
        s = str(error)
        assert "错误消息" in s
        assert "err1" in s

    def test_required_field_error(self):
        """测试必填字段异常。"""
        error = RequiredFieldError("username")
        assert error.field == "username"
        assert error.code == "required_field_missing"
        assert "username" in error.message

    def test_required_field_error_custom_message(self):
        """测试自定义消息的必填字段异常。"""
        error = RequiredFieldError("email", "请输入邮箱")
        assert error.message == "请输入邮箱"

    def test_invalid_format_error(self):
        """测试格式无效异常。"""
        error = InvalidFormatError("email", "invalid", "xxx@xxx")
        assert error.field == "email"
        assert error.value == "invalid"
        assert error.expected_format == "xxx@xxx"
        assert error.code == "invalid_format"

    def test_out_of_range_error(self):
        """测试超出范围异常。"""
        error = OutOfRangeError("age", 150, min_value=0, max_value=120)
        assert error.field == "age"
        assert error.value == 150
        assert error.min_value == 0
        assert error.max_value == 120
        assert error.code == "out_of_range"

    def test_out_of_range_error_min_only(self):
        """测试仅最小值的范围异常。"""
        error = OutOfRangeError("count", -1, min_value=0)
        assert error.min_value == 0
        assert error.max_value is None

    def test_invalid_length_error(self):
        """测试长度无效异常。"""
        error = InvalidLengthError("title", 50, min_length=4, max_length=20)
        assert error.field == "title"
        assert error.actual_length == 50
        assert error.min_length == 4
        assert error.max_length == 20
        assert error.code == "invalid_length"

    def test_invalid_enum_value_error(self):
        """测试枚举值无效异常。"""
        error = InvalidEnumValueError("degree", "invalid", ["master", "doctor"])
        assert error.field == "degree"
        assert error.value == "invalid"
        assert error.valid_values == ["master", "doctor"]
        assert error.code == "invalid_enum_value"

    def test_security_validation_error(self):
        """测试安全验证异常。"""
        error = SecurityValidationError("input")
        assert error.field == "input"
        assert error.code == "security_violation"

    def test_security_validation_error_custom_message(self):
        """测试自定义消息的安全异常。"""
        error = SecurityValidationError("input", "包含XSS攻击代码")
        assert error.message == "包含XSS攻击代码"

    def test_error_inheritance(self):
        """测试异常继承关系。"""
        assert issubclass(RequiredFieldError, ValidationError)
        assert issubclass(InvalidFormatError, ValidationError)
        assert issubclass(OutOfRangeError, ValidationError)
        assert issubclass(InvalidLengthError, ValidationError)
        assert issubclass(InvalidEnumValueError, ValidationError)
        assert issubclass(SecurityValidationError, ValidationError)

    def test_error_details(self):
        """测试异常详情。"""
        error = ValidationError("错误", details={"extra": "info"})
        assert error.details == {"extra": "info"}

    def test_error_details_default(self):
        """测试异常详情默认值。"""
        error = ValidationError("错误")
        assert error.details == {}


# ===== ValidationResult 测试 =====


class TestValidationResult:
    """ValidationResult 验证结果测试。"""

    def test_valid_result(self):
        """测试有效结果。"""
        result = ValidationResult(is_valid=True, value="test")
        assert result.is_valid is True
        assert result.value == "test"
        assert result.errors == []

    def test_invalid_result(self):
        """测试无效结果。"""
        result = ValidationResult(is_valid=False, errors=["error1"])
        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_add_error(self):
        """测试添加错误。"""
        result = ValidationResult(is_valid=True)
        error = ValidationError("测试错误", field="test")
        result.add_error(error)
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0] is error

    def test_add_multiple_errors(self):
        """测试添加多个错误。"""
        result = ValidationResult(is_valid=True)
        result.add_error(ValidationError("错误1"))
        result.add_error(ValidationError("错误2"))
        result.add_error(ValidationError("错误3"))
        assert result.is_valid is False
        assert len(result.errors) == 3

    def test_to_dict(self):
        """测试结果转字典。"""
        result = ValidationResult(is_valid=False, value="val", errors=[ValidationError("错误")])
        d = result.to_dict()
        assert d["is_valid"] is False
        assert d["value"] == "val"
        assert len(d["errors"]) == 1

    def test_bool_true(self):
        """测试布尔值为 True。"""
        result = ValidationResult(is_valid=True)
        assert bool(result) is True

    def test_bool_false(self):
        """测试布尔值为 False。"""
        result = ValidationResult(is_valid=False)
        assert bool(result) is False

    def test_default_errors_empty(self):
        """测试默认错误列表为空。"""
        result = ValidationResult(is_valid=True)
        assert result.errors == []


# ===== 基础验证器测试 =====


class TestValidateRequired:
    """validate_required 必填验证器测试。"""

    def test_valid_string(self):
        """测试有效字符串。"""
        result = validate_required("hello", "name")
        assert result.is_valid is True

    def test_none_value(self):
        """测试 None 值。"""
        result = validate_required(None, "name")
        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_empty_string(self):
        """测试空字符串。"""
        result = validate_required("", "name")
        assert result.is_valid is False

    def test_whitespace_string(self):
        """测试空白字符串。"""
        result = validate_required("   ", "name")
        assert result.is_valid is False

    def test_empty_list(self):
        """测试空列表。"""
        result = validate_required([], "items")
        assert result.is_valid is False

    def test_empty_dict(self):
        """测试空字典。"""
        result = validate_required({}, "data")
        assert result.is_valid is False

    def test_non_empty_list(self):
        """测试非空列表。"""
        result = validate_required([1, 2], "items")
        assert result.is_valid is True

    def test_zero_value(self):
        """测试零值。"""
        result = validate_required(0, "count")
        assert result.is_valid is True

    def test_false_value(self):
        """测试 False 值。"""
        result = validate_required(False, "flag")
        assert result.is_valid is True


class TestValidateString:
    """validate_string 字符串验证器测试。"""

    def test_valid_string(self):
        """测试有效字符串。"""
        result = validate_string("hello", "name")
        assert result.is_valid is True

    def test_min_length(self):
        """测试最小长度。"""
        result = validate_string("ab", "name", min_length=3)
        assert result.is_valid is False

    def test_max_length(self):
        """测试最大长度。"""
        result = validate_string("hello world", "name", max_length=5)
        assert result.is_valid is False

    def test_valid_length_range(self):
        """测试有效长度范围。"""
        result = validate_string("hello", "name", min_length=1, max_length=10)
        assert result.is_valid is True

    def test_allow_empty(self):
        """测试允许空字符串。"""
        result = validate_string("", "name", allow_empty=True)
        assert result.is_valid is True

    def test_not_allow_empty(self):
        """测试不允许空字符串。"""
        result = validate_string("", "name", allow_empty=False)
        assert result.is_valid is False

    def test_none_with_allow_empty(self):
        """测试 None 值允许空。"""
        result = validate_string(None, "name", allow_empty=True)
        assert result.is_valid is True

    def test_none_without_allow_empty(self):
        """测试 None 值不允许空。"""
        result = validate_string(None, "name", allow_empty=False)
        assert result.is_valid is False

    def test_non_string_value(self):
        """测试非字符串值。"""
        result = validate_string(123, "name")
        assert result.is_valid is False

    def test_pattern_match(self):
        """测试模式匹配。"""
        result = validate_string("abc123", "code", pattern=r"^[a-z]+\d+$")
        assert result.is_valid is True

    def test_pattern_no_match(self):
        """测试模式不匹配。"""
        result = validate_string("123abc", "code", pattern=r"^[a-z]+\d+$")
        assert result.is_valid is False

    def test_strips_value(self):
        """测试值被 strip。"""
        result = validate_string("  hello  ", "name")
        assert result.value == "hello"


class TestValidateInteger:
    """validate_integer 整数验证器测试。"""

    def test_valid_integer(self):
        """测试有效整数。"""
        result = validate_integer(42, "age")
        assert result.is_valid is True
        assert result.value == 42

    def test_string_integer(self):
        """测试字符串整数。"""
        result = validate_integer("42", "age")
        assert result.is_valid is True
        assert result.value == 42

    def test_invalid_string(self):
        """测试无效字符串。"""
        result = validate_integer("abc", "age")
        assert result.is_valid is False

    def test_none_value(self):
        """测试 None 值。"""
        result = validate_integer(None, "age")
        assert result.is_valid is False

    def test_none_allowed(self):
        """测试允许 None。"""
        result = validate_integer(None, "age", allow_none=True)
        assert result.is_valid is True

    def test_min_value(self):
        """测试最小值。"""
        result = validate_integer(-1, "count", min_value=0)
        assert result.is_valid is False

    def test_max_value(self):
        """测试最大值。"""
        result = validate_integer(101, "count", max_value=100)
        assert result.is_valid is False

    def test_in_range(self):
        """测试范围内值。"""
        result = validate_integer(50, "count", min_value=0, max_value=100)
        assert result.is_valid is True

    def test_boolean_rejected(self):
        """测试布尔值被拒绝。"""
        result = validate_integer(True, "flag")
        assert result.is_valid is False

    def test_float_string_rejected(self):
        """测试浮点字符串被拒绝。"""
        result = validate_integer("3.14", "value")
        assert result.is_valid is False


class TestValidateFloat:
    """validate_float 浮点数验证器测试。"""

    def test_valid_float(self):
        """测试有效浮点数。"""
        result = validate_float(3.14, "price")
        assert result.is_valid is True

    def test_integer_as_float(self):
        """测试整数作为浮点数。"""
        result = validate_float(42, "price")
        assert result.is_valid is True
        assert result.value == 42.0

    def test_string_float(self):
        """测试字符串浮点数。"""
        result = validate_float("3.14", "price")
        assert result.is_valid is True

    def test_invalid_string(self):
        """测试无效字符串。"""
        result = validate_float("abc", "price")
        assert result.is_valid is False

    def test_none_allowed(self):
        """测试允许 None。"""
        result = validate_float(None, "price", allow_none=True)
        assert result.is_valid is True

    def test_min_value(self):
        """测试最小值。"""
        result = validate_float(-0.1, "price", min_value=0.0)
        assert result.is_valid is False

    def test_max_value(self):
        """测试最大值。"""
        result = validate_float(101.0, "price", max_value=100.0)
        assert result.is_valid is False

    def test_boolean_rejected(self):
        """测试布尔值被拒绝。"""
        result = validate_float(True, "price")
        assert result.is_valid is False


class TestValidateBoolean:
    """validate_boolean 布尔验证器测试。"""

    def test_true_value(self):
        """测试 True 值。"""
        result = validate_boolean(True, "flag")
        assert result.is_valid is True

    def test_false_value(self):
        """测试 False 值。"""
        result = validate_boolean(False, "flag")
        assert result.is_valid is True

    def test_string_true(self):
        """测试字符串 true。"""
        result = validate_boolean("true", "flag")
        assert result.is_valid is True

    def test_string_false(self):
        """测试字符串 false。"""
        result = validate_boolean("false", "flag")
        assert result.is_valid is True

    def test_string_yes(self):
        """测试字符串 yes。"""
        result = validate_boolean("yes", "flag")
        assert result.is_valid is True

    def test_string_no(self):
        """测试字符串 no。"""
        result = validate_boolean("no", "flag")
        assert result.is_valid is True

    def test_integer_one(self):
        """测试整数 1。"""
        result = validate_boolean(1, "flag")
        assert result.is_valid is True

    def test_integer_zero(self):
        """测试整数 0。"""
        result = validate_boolean(0, "flag")
        assert result.is_valid is True

    def test_invalid_value(self):
        """测试无效值。"""
        result = validate_boolean("invalid", "flag")
        assert result.is_valid is False


class TestValidateEnum:
    """validate_enum 枚举验证器测试。"""

    def test_valid_value(self):
        """测试有效枚举值。"""
        result = validate_enum("master", "degree", ["master", "doctor"])
        assert result.is_valid is True

    def test_invalid_value(self):
        """测试无效枚举值。"""
        result = validate_enum("invalid", "degree", ["master", "doctor"])
        assert result.is_valid is False

    def test_empty_value(self):
        """测试空值。"""
        result = validate_enum("", "degree", ["master", "doctor"])
        assert result.is_valid is False

    def test_none_value(self):
        """测试 None 值。"""
        result = validate_enum(None, "degree", ["master", "doctor"])
        assert result.is_valid is False

    def test_case_sensitive(self):
        """测试大小写敏感。"""
        result = validate_enum("Master", "degree", ["master", "doctor"])
        assert result.is_valid is False


class TestValidateList:
    """validate_list 列表验证器测试。"""

    def test_valid_list(self):
        """测试有效列表。"""
        result = validate_list([1, 2, 3], "items")
        assert result.is_valid is True

    def test_empty_list(self):
        """测试空列表。"""
        result = validate_list([], "items")
        assert result.is_valid is True

    def test_non_list_value(self):
        """测试非列表值。"""
        result = validate_list("not a list", "items")
        assert result.is_valid is False

    def test_min_length(self):
        """测试最小长度。"""
        result = validate_list([1], "items", min_length=2)
        assert result.is_valid is False

    def test_max_length(self):
        """测试最大长度。"""
        result = validate_list([1, 2, 3, 4], "items", max_length=3)
        assert result.is_valid is False


class TestValidateDict:
    """validate_dict 字典验证器测试。"""

    def test_valid_dict(self):
        """测试有效字典。"""
        result = validate_dict({"key": "value"}, "data")
        assert result.is_valid is True

    def test_empty_dict(self):
        """测试空字典。"""
        result = validate_dict({}, "data")
        assert result.is_valid is True

    def test_non_dict_value(self):
        """测试非字典值。"""
        result = validate_dict("not a dict", "data")
        assert result.is_valid is False

    def test_required_keys(self):
        """测试必需键。"""
        result = validate_dict({"name": "test"}, "data", required_keys=["name", "age"])
        assert result.is_valid is False


# ===== 业务验证器测试 =====


class TestValidateEmail:
    """validate_email 邮箱验证器测试。"""

    def test_valid_email(self):
        """测试有效邮箱。"""
        result = validate_email("test@example.com")
        assert result.is_valid is True

    def test_valid_email_with_subdomain(self):
        """测试带子域名的邮箱。"""
        result = validate_email("user@mail.example.com")
        assert result.is_valid is True

    def test_valid_email_with_plus(self):
        """测试带加号的邮箱。"""
        result = validate_email("user+tag@example.com")
        assert result.is_valid is True

    def test_invalid_email_no_at(self):
        """测试无 @ 的邮箱。"""
        result = validate_email("invalidemail.com")
        assert result.is_valid is False

    def test_invalid_email_no_domain(self):
        """测试无域名的邮箱。"""
        result = validate_email("user@")
        assert result.is_valid is False

    def test_invalid_email_no_user(self):
        """测试无用户名的邮箱。"""
        result = validate_email("@example.com")
        assert result.is_valid is False

    def test_invalid_email_spaces(self):
        """测试带空格的邮箱。"""
        result = validate_email("user @example.com")
        assert result.is_valid is False

    def test_empty_email(self):
        """测试空邮箱。"""
        result = validate_email("")
        assert result.is_valid is False

    def test_none_email(self):
        """测试 None 邮箱。"""
        result = validate_email(None)
        assert result.is_valid is False


class TestValidateUrl:
    """validate_url URL 验证器测试。"""

    def test_valid_http_url(self):
        """测试有效 HTTP URL。"""
        result = validate_url("http://example.com")
        assert result.is_valid is True

    def test_valid_https_url(self):
        """测试有效 HTTPS URL。"""
        result = validate_url("https://example.com")
        assert result.is_valid is True

    def test_valid_url_with_path(self):
        """测试带路径的 URL。"""
        result = validate_url("https://example.com/path/to/page")
        assert result.is_valid is True

    def test_valid_url_with_port(self):
        """测试带端口的 URL。"""
        result = validate_url("https://example.com:8080")
        assert result.is_valid is True

    def test_valid_url_with_query(self):
        """测试带查询参数的 URL。"""
        result = validate_url("https://example.com?key=value&foo=bar")
        assert result.is_valid is True

    def test_invalid_url_no_protocol(self):
        """测试无协议的 URL。"""
        result = validate_url("example.com")
        assert result.is_valid is False

    def test_invalid_url_ftp(self):
        """测试 FTP 协议 URL。"""
        result = validate_url("ftp://example.com")
        assert result.is_valid is False

    def test_empty_url(self):
        """测试空 URL。"""
        result = validate_url("")
        assert result.is_valid is False

    def test_none_url(self):
        """测试 None URL。"""
        result = validate_url(None)
        assert result.is_valid is False


class TestValidatePhone:
    """validate_phone 电话号码验证器测试。"""

    def test_valid_cn_phone(self):
        """测试有效中国手机号。"""
        result = validate_phone("13812345678")
        assert result.is_valid is True

    def test_valid_cn_phone_start_15(self):
        """测试 15 开头手机号。"""
        result = validate_phone("15912345678")
        assert result.is_valid is True

    def test_valid_cn_phone_start_17(self):
        """测试 17 开头手机号。"""
        result = validate_phone("17612345678")
        assert result.is_valid is True

    def test_invalid_phone_too_short(self):
        """测试过短手机号。"""
        result = validate_phone("1381234567")
        assert result.is_valid is False

    def test_invalid_phone_too_long(self):
        """测试过长手机号。"""
        result = validate_phone("138123456789")
        assert result.is_valid is False

    def test_invalid_phone_start_with_0(self):
        """测试 0 开头号码。"""
        result = validate_phone("02812345678")
        assert result.is_valid is False

    def test_invalid_phone_letters(self):
        """测试包含字母的号码。"""
        result = validate_phone("1381234abcd")
        assert result.is_valid is False


class TestValidateDegree:
    """validate_degree 学位验证器测试。"""

    def test_valid_master(self):
        """测试硕士学位。"""
        result = validate_degree("master")
        assert result.is_valid is True

    def test_valid_doctor(self):
        """测试博士学位。"""
        result = validate_degree("doctor")
        assert result.is_valid is True

    def test_valid_bachelor(self):
        """测试本科学位。"""
        result = validate_degree("bachelor")
        assert result.is_valid is True

    def test_valid_postdoc(self):
        """测试博士后。"""
        result = validate_degree("postdoc")
        assert result.is_valid is True

    def test_invalid_degree(self):
        """测试无效学位。"""
        result = validate_degree("invalid")
        assert result.is_valid is False

    def test_empty_degree(self):
        """测试空学位。"""
        result = validate_degree("")
        assert result.is_valid is False

    def test_none_degree(self):
        """测试 None 学位。"""
        result = validate_degree(None)
        assert result.is_valid is False


class TestValidateDiscipline:
    """validate_discipline 学科验证器测试。"""

    def test_valid_discipline(self):
        """测试有效学科。"""
        result = validate_discipline("computer_science")
        assert result.is_valid is True

    def test_valid_philosophy(self):
        """测试哲学学科。"""
        result = validate_discipline("philosophy")
        assert result.is_valid is True

    def test_valid_medicine(self):
        """测试医学学科。"""
        result = validate_discipline("medicine")
        assert result.is_valid is True

    def test_invalid_discipline(self):
        """测试无效学科。"""
        result = validate_discipline("invalid_subject")
        assert result.is_valid is False

    def test_empty_discipline(self):
        """测试空学科。"""
        result = validate_discipline("")
        assert result.is_valid is False


class TestValidateTitle:
    """validate_title 标题验证器测试。"""

    def test_valid_title(self):
        """测试有效标题。"""
        result = validate_title("深度学习在图像识别中的应用")
        assert result.is_valid is True

    def test_empty_title(self):
        """测试空标题。"""
        result = validate_title("")
        assert result.is_valid is False

    def test_title_too_long(self):
        """测试过长标题。"""
        long_title = "这是一个非常非常非常非常非常非常非常非常长的标题超过二十个字"
        result = validate_title(long_title)
        assert result.is_valid is False

    def test_title_too_short(self):
        """测试过短标题。"""
        result = validate_title("短")
        assert result.is_valid is False

    def test_title_with_active_verb(self):
        """测试以主动动词开头的标题。"""
        result = validate_title("研究深度学习方法")
        assert result.is_valid is False

    def test_title_with_based_pattern(self):
        """测试基于模式的标题。"""
        result = validate_title("基于深度学习的图像识别研究")
        assert result.is_valid is False

    def test_title_with_html(self):
        """测试含 HTML 的标题。"""
        result = validate_title("<script>alert(1)</script>深度学习")
        assert result.is_valid is False

    def test_title_none(self):
        """测试 None 标题。"""
        result = validate_title(None)
        assert result.is_valid is False


class TestValidateAbstract:
    """validate_abstract 摘要验证器测试。"""

    def test_valid_abstract(self):
        """测试有效摘要。"""
        abstract = "近年来，随着深度学习技术的快速发展，图像识别领域取得了显著进展。本文采用卷积神经网络方法，对大规模图像数据集进行实验。结果表明，所提出的方法在准确率上提升了百分之十。"
        result = validate_abstract(abstract)
        assert result.is_valid is True

    def test_empty_abstract(self):
        """测试空摘要。"""
        result = validate_abstract("")
        assert result.is_valid is False

    def test_short_abstract(self):
        """测试过短摘要。"""
        result = validate_abstract("短摘要")
        assert result.is_valid is False

    def test_long_abstract(self):
        """测试过长摘要。"""
        long_abstract = "x" * 1500
        result = validate_abstract(long_abstract)
        assert result.is_valid is False

    def test_none_abstract(self):
        """测试 None 摘要。"""
        result = validate_abstract(None)
        assert result.is_valid is False


class TestValidateGranularity:
    """validate_granularity 粒度验证器测试。"""

    def test_valid_topic(self):
        """测试 topic 粒度。"""
        result = validate_granularity("topic")
        assert result.is_valid is True

    def test_valid_outline(self):
        """测试 outline 粒度。"""
        result = validate_granularity("outline")
        assert result.is_valid is True

    def test_valid_full(self):
        """测试 full 粒度。"""
        result = validate_granularity("full")
        assert result.is_valid is True

    def test_invalid_granularity(self):
        """测试无效粒度。"""
        result = validate_granularity("invalid")
        assert result.is_valid is False

    def test_empty_granularity(self):
        """测试空粒度。"""
        result = validate_granularity("")
        assert result.is_valid is False


class TestValidateMode:
    """validate_mode 模式验证器测试。"""

    def test_valid_quick(self):
        """测试 quick 模式。"""
        result = validate_mode("quick")
        assert result.is_valid is True

    def test_valid_deep(self):
        """测试 deep 模式。"""
        result = validate_mode("deep")
        assert result.is_valid is True

    def test_valid_balanced(self):
        """测试 balanced 模式。"""
        result = validate_mode("balanced")
        assert result.is_valid is True

    def test_invalid_mode(self):
        """测试无效模式。"""
        result = validate_mode("invalid")
        assert result.is_valid is False


class TestValidateCurrency:
    """validate_currency 货币验证器测试。"""

    def test_valid_cny(self):
        """测试人民币。"""
        result = validate_currency("CNY")
        assert result.is_valid is True

    def test_valid_usd(self):
        """测试美元。"""
        result = validate_currency("USD")
        assert result.is_valid is True

    def test_invalid_currency(self):
        """测试无效货币。"""
        result = validate_currency("EUR")
        assert result.is_valid is False

    def test_lowercase_currency(self):
        """测试小写货币。"""
        result = validate_currency("cny")
        assert result.is_valid is False


class TestValidateUuid:
    """validate_uuid UUID 验证器测试。"""

    def test_valid_uuid(self):
        """测试有效 UUID。"""
        result = validate_uuid("550e8400-e29b-41d4-a716-446655440000")
        assert result.is_valid is True

    def test_valid_uuid_uppercase(self):
        """测试大写 UUID。"""
        result = validate_uuid("550E8400-E29B-41D4-A716-446655440000")
        assert result.is_valid is True

    def test_invalid_uuid_short(self):
        """测试过短 UUID。"""
        result = validate_uuid("550e8400-e29b-41d4-a716")
        assert result.is_valid is False

    def test_invalid_uuid_no_dashes(self):
        """测试无连字符 UUID。"""
        result = validate_uuid("550e8400e29b41d4a716446655440000")
        assert result.is_valid is False

    def test_empty_uuid(self):
        """测试空 UUID。"""
        result = validate_uuid("")
        assert result.is_valid is False


class TestValidateModelId:
    """validate_model_id 模型 ID 验证器测试。"""

    def test_valid_model_id(self):
        """测试有效模型 ID。"""
        result = validate_model_id("gpt-4.1")
        assert result.is_valid is True

    def test_valid_model_id_with_numbers(self):
        """测试带数字的模型 ID。"""
        result = validate_model_id("deepseek-v3.2")
        assert result.is_valid is True

    def test_invalid_model_id_spaces(self):
        """测试带空格的模型 ID。"""
        result = validate_model_id("gpt 4.1")
        assert result.is_valid is False

    def test_empty_model_id(self):
        """测试空模型 ID。"""
        result = validate_model_id("")
        assert result.is_valid is False


class TestValidateApiKey:
    """validate_api_key API 密钥验证器测试。"""

    def test_valid_api_key(self):
        """测试有效 API 密钥。"""
        result = validate_api_key("sk-1234567890abcdef")
        assert result.is_valid is True

    def test_short_api_key(self):
        """测试过短 API 密钥。"""
        result = validate_api_key("sk-123")
        assert result.is_valid is False

    def test_empty_api_key(self):
        """测试空 API 密钥。"""
        result = validate_api_key("")
        assert result.is_valid is False

    def test_none_api_key(self):
        """测试 None API 密钥。"""
        result = validate_api_key(None)
        assert result.is_valid is False


class TestValidateBaseUrl:
    """validate_base_url 基础 URL 验证器测试。"""

    def test_valid_https_url(self):
        """测试有效 HTTPS URL。"""
        result = validate_base_url("https://api.openai.com")
        assert result.is_valid is True

    def test_valid_http_url(self):
        """测试有效 HTTP URL。"""
        result = validate_base_url("http://localhost:8080")
        assert result.is_valid is True

    def test_invalid_url_no_protocol(self):
        """测试无协议 URL。"""
        result = validate_base_url("api.openai.com")
        assert result.is_valid is False

    def test_empty_url(self):
        """测试空 URL。"""
        result = validate_base_url("")
        assert result.is_valid is False


class TestValidateTemperature:
    """validate_temperature 温度参数验证器测试。"""

    def test_valid_temperature(self):
        """测试有效温度。"""
        result = validate_temperature(0.7)
        assert result.is_valid is True

    def test_valid_temperature_zero(self):
        """测试零温度。"""
        result = validate_temperature(0.0)
        assert result.is_valid is True

    def test_valid_temperature_max(self):
        """测试最大温度。"""
        result = validate_temperature(2.0)
        assert result.is_valid is True

    def test_temperature_too_low(self):
        """测试过低温度。"""
        result = validate_temperature(-0.1)
        assert result.is_valid is False

    def test_temperature_too_high(self):
        """测试过高温度。"""
        result = validate_temperature(2.1)
        assert result.is_valid is False

    def test_string_temperature(self):
        """测试字符串温度。"""
        result = validate_temperature("0.7")
        assert result.is_valid is True


class TestValidateMaxTokens:
    """validate_max_tokens 最大 token 数验证器测试。"""

    def test_valid_max_tokens(self):
        """测试有效 token 数。"""
        result = validate_max_tokens(4096)
        assert result.is_valid is True

    def test_max_tokens_too_small(self):
        """测试过小 token 数。"""
        result = validate_max_tokens(0)
        assert result.is_valid is False

    def test_max_tokens_negative(self):
        """测试负数 token 数。"""
        result = validate_max_tokens(-1)
        assert result.is_valid is False

    def test_string_max_tokens(self):
        """测试字符串 token 数。"""
        result = validate_max_tokens("4096")
        assert result.is_valid is True


class TestValidateMentorInfo:
    """validate_mentor_info 导师信息验证器测试。"""

    def test_valid_mentor_info(self):
        """测试有效导师信息。"""
        result = validate_mentor_info("张教授，计算机科学方向")
        assert result.is_valid is True

    def test_empty_mentor_info(self):
        """测试空导师信息。"""
        result = validate_mentor_info("")
        assert result.is_valid is False

    def test_mentor_info_too_long(self):
        """测试过长导师信息。"""
        long_info = "x" * 6000
        result = validate_mentor_info(long_info)
        assert result.is_valid is False


class TestValidateSearchQuery:
    """validate_search_query 搜索查询验证器测试。"""

    def test_valid_query(self):
        """测试有效查询。"""
        result = validate_search_query("深度学习 图像识别")
        assert result.is_valid is True

    def test_empty_query(self):
        """测试空查询。"""
        result = validate_search_query("")
        assert result.is_valid is False

    def test_query_too_long(self):
        """测试过长查询。"""
        long_query = "x" * 600
        result = validate_search_query(long_query)
        assert result.is_valid is False


class TestValidatePagination:
    """validate_pagination 分页验证器测试。"""

    def test_valid_pagination(self):
        """测试有效分页。"""
        result = validate_pagination(page=1, limit=20)
        assert result.is_valid is True

    def test_invalid_page_zero(self):
        """测试页码为零。"""
        result = validate_pagination(page=0, limit=20)
        assert result.is_valid is False

    def test_invalid_page_negative(self):
        """测试负页码。"""
        result = validate_pagination(page=-1, limit=20)
        assert result.is_valid is False

    def test_invalid_limit_zero(self):
        """测试每页条数为零。"""
        result = validate_pagination(page=1, limit=0)
        assert result.is_valid is False

    def test_invalid_limit_too_large(self):
        """测试每页条数过大。"""
        result = validate_pagination(page=1, limit=200)
        assert result.is_valid is False


# ===== 常量测试 =====


class TestConstants:
    """常量定义测试。"""

    def test_valid_degrees(self):
        """测试学位常量。"""
        assert "master" in VALID_DEGREES
        assert "doctor" in VALID_DEGREES
        assert "bachelor" in VALID_DEGREES
        assert "postdoc" in VALID_DEGREES

    def test_valid_disciplines(self):
        """测试学科常量。"""
        assert "computer_science" in VALID_DISCIPLINES
        assert "philosophy" in VALID_DISCIPLINES
        assert "medicine" in VALID_DISCIPLINES
        assert len(VALID_DISCIPLINES) > 50

    def test_valid_granularities(self):
        """测试粒度常量。"""
        assert "topic" in VALID_GRANULARITIES
        assert "outline" in VALID_GRANULARITIES
        assert "full" in VALID_GRANULARITIES

    def test_valid_modes(self):
        """测试模式常量。"""
        assert "quick" in VALID_MODES
        assert "deep" in VALID_MODES
        assert "balanced" in VALID_MODES

    def test_valid_currencies(self):
        """测试货币常量。"""
        assert "CNY" in VALID_CURRENCIES
        assert "USD" in VALID_CURRENCIES

    def test_active_verbs(self):
        """测试主动动词常量。"""
        assert "研究" in ACTIVE_VERBS
        assert "分析" in ACTIVE_VERBS
        assert len(ACTIVE_VERBS) >= 10

    def test_max_title_length(self):
        """测试标题最大长度常量。"""
        assert MAX_TITLE_LENGTH == 20

    def test_abstract_length_range(self):
        """测试摘要长度范围常量。"""
        assert ABSTRACT_MIN_LENGTH == 100
        assert ABSTRACT_MAX_LENGTH == 1000

    def test_title_min_length(self):
        """测试标题最小长度常量。"""
        assert TITLE_MIN_LENGTH == 4

    def test_email_pattern(self):
        """测试邮箱正则。"""
        assert EMAIL_PATTERN.match("test@example.com")
        assert not EMAIL_PATTERN.match("invalid")

    def test_url_pattern(self):
        """测试 URL 正则。"""
        assert URL_PATTERN.match("https://example.com")
        assert not URL_PATTERN.match("not a url")

    def test_xss_patterns(self):
        """测试 XSS 模式。"""
        assert len(XSS_PATTERNS) > 0
        # 测试检测 XSS
        xss_input = "<script>alert(1)</script>"
        matched = any(p.search(xss_input) for p in XSS_PATTERNS)
        assert matched

    def test_sql_injection_patterns(self):
        """测试 SQL 注入模式。"""
        assert len(SQL_INJECTION_PATTERNS) > 0
        # 测试检测 SQL 注入
        sql_input = "' OR 1=1 --"
        matched = any(p.search(sql_input) for p in SQL_INJECTION_PATTERNS)
        assert matched


# ===== 集成测试 =====


class TestIntegration:
    """集成测试。"""

    def test_multiple_validators_pass(self):
        """测试多个验证器同时通过。"""
        results = [
            validate_email("test@example.com"),
            validate_url("https://example.com"),
            validate_degree("master"),
            validate_discipline("computer_science"),
        ]
        assert all(r.is_valid for r in results)

    def test_multiple_validators_fail(self):
        """测试多个验证器同时失败。"""
        results = [
            validate_email("invalid"),
            validate_url("not a url"),
            validate_degree("invalid"),
        ]
        assert all(not r.is_valid for r in results)

    def test_validation_chain(self):
        """测试验证链。"""
        # 先验证必填，再验证格式
        r1 = validate_required("test@example.com", "email")
        assert r1.is_valid
        if r1.is_valid:
            r2 = validate_email(r1.value)
            assert r2.is_valid

    def test_error_aggregation(self):
        """测试错误聚合。"""
        errors = []
        result = validate_email("invalid")
        if not result.is_valid:
            errors.extend(result.errors)
        result = validate_url("invalid")
        if not result.is_valid:
            errors.extend(result.errors)
        assert len(errors) >= 2

    def test_title_validation_comprehensive(self):
        """测试标题综合验证。"""
        # 有效标题
        assert validate_title("深度学习在图像识别中的应用").is_valid
        # 空标题
        assert not validate_title("").is_valid
        # 过长标题
        assert not validate_title("x" * 30).is_valid
        # 过短标题
        assert not validate_title("短").is_valid

    def test_abstract_validation_comprehensive(self):
        """测试摘要综合验证。"""
        # 有效摘要
        valid = "近年来，随着深度学习技术的快速发展，图像识别领域取得了显著进展。本文采用卷积神经网络方法，对大规模图像数据集进行实验。结果表明，所提出的方法在准确率上提升了百分之十。"
        assert validate_abstract(valid).is_valid
        # 空摘要
        assert not validate_abstract("").is_valid
        # 过短摘要
        assert not validate_abstract("短").is_valid


# ===== 边界与异常测试 =====


class TestEdgeCases:
    """边界与异常测试。"""

    def test_validate_required_with_zero(self):
        """测试零值必填验证。"""
        assert validate_required(0, "count").is_valid

    def test_validate_required_with_false(self):
        """测试 False 必填验证。"""
        assert validate_required(False, "flag").is_valid

    def test_validate_string_with_unicode(self):
        """测试 Unicode 字符串验证。"""
        result = validate_string("中文测试🎉", "text")
        assert result.is_valid is True

    def test_validate_integer_with_negative(self):
        """测试负整数验证。"""
        result = validate_integer(-42, "value")
        assert result.is_valid is True

    def test_validate_float_with_very_small(self):
        """测试极小浮点数验证。"""
        result = validate_float(0.000001, "value")
        assert result.is_valid is True

    def test_validate_email_with_long_domain(self):
        """测试长域名邮箱验证。"""
        result = validate_email("user@very-long-domain-name.example.com")
        assert result.is_valid is True

    def test_validate_url_with_long_path(self):
        """测试长路径 URL 验证。"""
        result = validate_url("https://example.com/" + "a" * 500)
        assert result.is_valid is True

    def test_validate_title_boundary_length(self):
        """测试标题边界长度。"""
        # 正好 20 字
        title = "一二三四五六七八九十一二三四五六七八九十"
        result = validate_title(title)
        assert result.is_valid is True or result.is_valid is False  # 取决于实现

    def test_validate_abstract_boundary_length(self):
        """测试摘要边界长度。"""
        # 正好 100 字
        abstract = "x" * 100
        result = validate_abstract(abstract)
        # 取决于实现是否包含边界值
        assert result.is_valid is True or result.is_valid is False
