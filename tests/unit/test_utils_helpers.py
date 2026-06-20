"""helpers 模块单元测试

覆盖 backend/utils/helpers.py 中的所有工具函数：
- 字符串处理（截断/slugify/命名转换/HTML移除/词数统计/关键词提取/脱敏）
- 日期时间处理（格式化/解析/时间戳/相对时间/日期计算）
- ID 生成（UUID/短ID/数字ID/请求ID/会话ID/任务ID/关联ID/令牌/API密钥）
- 哈希函数（MD5/SHA1/SHA256/SHA512/文件哈希/内容哈希/缓存键哈希）
- 文件操作（读写/JSON/大小/列表/复制/移动/扩展名）
- JSON 工具（安全序列化/反序列化/字典合并/深度获取设置/扁平化）
- 异步辅助（并发限制/超时/重试/线程池）
- 类型转换（int/float/str/bool/list/dict）
- 集合工具（分块/扁平化/去重/分组/分区）
- 数学工具（钳制/百分比/平均值/中位数/取整）
- 环境工具（系统判断/环境变量获取）
- 装饰器（记忆化/重试/计时）
- 编码工具（Base64/URL编码）
- 调试工具（美化打印/对象大小/类名/方法检查/安全调用）
"""
import asyncio
import json
import os
import time
from datetime import datetime, date, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.utils import helpers


# ===== 字符串处理测试 =====


class TestTruncate:
    """truncate 函数测试"""

    def test_short_text_unchanged(self):
        """短文本不截断"""
        assert helpers.truncate("hello", 10) == "hello"

    def test_exact_length(self):
        """恰好等于最大长度不截断"""
        assert helpers.truncate("hello", 5) == "hello"

    def test_long_text_truncated(self):
        """长文本被截断并添加后缀"""
        result = helpers.truncate("hello world", 8)
        assert len(result) == 8
        assert result.endswith("...")

    def test_custom_suffix(self):
        """自定义后缀"""
        result = helpers.truncate("hello world", 8, suffix="[...]")
        assert result.endswith("[...]")

    def test_empty_text(self):
        """空文本"""
        assert helpers.truncate("", 10) == ""

    def test_none_text(self):
        """None 输入"""
        assert helpers.truncate(None, 10) is None

    def test_suffix_longer_than_max(self):
        """后缀长度大于最大长度"""
        result = helpers.truncate("hello", 3, suffix="......")
        assert len(result) == 3

    def test_max_length_equals_suffix_length(self):
        """最大长度等于后缀长度"""
        result = helpers.truncate("hello world", 3)
        assert result == "..."


class TestTruncateWords:
    """truncate_words 函数测试"""

    def test_few_words(self):
        """词数不足不截断"""
        assert helpers.truncate_words("hello world", 5) == "hello world"

    def test_many_words(self):
        """词数过多被截断"""
        result = helpers.truncate_words("one two three four five", 3)
        assert result.endswith("...")
        assert result.startswith("one two three")

    def test_empty_text(self):
        """空文本"""
        assert helpers.truncate_words("", 5) == ""

    def test_custom_suffix(self):
        """自定义后缀"""
        result = helpers.truncate_words("a b c d e", 2, suffix="...")
        assert result == "a b..."


class TestSlugify:
    """slugify 函数测试"""

    def test_english_text(self):
        """英文文本"""
        assert helpers.slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        """特殊字符被替换"""
        assert helpers.slugify("Hello, World!") == "hello-world"

    def test_chinese_text(self):
        """中文文本保留"""
        result = helpers.slugify("你好 World")
        assert "你好" in result
        assert "world" in result

    def test_empty_text(self):
        """空文本"""
        assert helpers.slugify("") == ""

    def test_custom_separator(self):
        """自定义分隔符"""
        assert helpers.slugify("Hello World", separator="_") == "hello_world"

    def test_max_length(self):
        """最大长度限制"""
        result = helpers.slugify("a" * 200, max_length=50)
        assert len(result) <= 50

    def test_leading_trailing_separator(self):
        """首尾分隔符被移除"""
        assert helpers.slugify("---hello---") == "hello"


class TestCamelToSnake:
    """camel_to_snake 函数测试"""

    def test_camel_case(self):
        """驼峰转下划线"""
        assert helpers.camel_to_snake("camelCase") == "camel_case"

    def test_pascal_case(self):
        """帕斯卡转下划线"""
        assert helpers.camel_to_snake("PascalCase") == "pascal_case"

    def test_mixed_case(self):
        """混合大小写"""
        assert helpers.camel_to_snake("getHTTPResponse") == "get_http_response"

    def test_already_snake(self):
        """已是下划线"""
        assert helpers.camel_to_snake("already_snake") == "already_snake"

    def test_single_word(self):
        """单词"""
        assert helpers.camel_to_snake("word") == "word"


class TestSnakeToCamel:
    """snake_to_camel 函数测试"""

    def test_snake_case(self):
        """下划线转驼峰"""
        assert helpers.snake_to_camel("snake_case") == "snakeCase"

    def test_already_camel(self):
        """已是驼峰"""
        assert helpers.snake_to_camel("camel") == "camel"

    def test_multiple_underscores(self):
        """多个下划线"""
        assert helpers.snake_to_camel("get_user_name") == "getUserName"


class TestPascalCase:
    """pascal_case 函数测试"""

    def test_snake_to_pascal(self):
        """下划线转帕斯卡"""
        assert helpers.pascal_case("snake_case") == "SnakeCase"

    def test_with_spaces(self):
        """含空格"""
        assert helpers.pascal_case("hello world") == "HelloWorld"

    def test_with_hyphens(self):
        """含连字符"""
        assert helpers.pascal_case("hello-world") == "HelloWorld"


class TestRemoveHtmlTags:
    """remove_html_tags 函数测试"""

    def test_simple_tags(self):
        """简单标签"""
        assert helpers.remove_html_tags("<p>hello</p>") == "hello"

    def test_nested_tags(self):
        """嵌套标签"""
        assert helpers.remove_html_tags("<div><p>hello</p></div>") == "hello"

    def test_html_entities(self):
        """HTML 实体"""
        assert helpers.remove_html_tags("&amp;") == "&"
        assert helpers.remove_html_tags("&lt;") == "<"
        assert helpers.remove_html_tags("&gt;") == ">"
        assert helpers.remove_html_tags("&quot;") == '"'
        assert helpers.remove_html_tags("&#39;") == "'"
        assert helpers.remove_html_tags("&nbsp;") == " "

    def test_empty_text(self):
        """空文本"""
        assert helpers.remove_html_tags("") == ""

    def test_no_tags(self):
        """无标签"""
        assert helpers.remove_html_tags("plain text") == "plain text"


class TestStripWhitespace:
    """strip_whitespace 函数测试"""

    def test_normal_strip(self):
        """普通去空白"""
        assert helpers.strip_whitespace("  hello  ") == "hello"

    def test_aggressive(self):
        """激进去空白"""
        assert helpers.strip_whitespace("  hello   world  ", aggressive=True) == "hello world"

    def test_empty(self):
        """空字符串"""
        assert helpers.strip_whitespace("") == ""

    def test_none(self):
        """None"""
        assert helpers.strip_whitespace(None) is None


class TestCountWords:
    """count_words 函数测试"""

    def test_english(self):
        """英文"""
        assert helpers.count_words("hello world") == 2

    def test_chinese(self):
        """中文按字计数"""
        assert helpers.count_words("你好世界") == 4

    def test_mixed(self):
        """中英混合"""
        assert helpers.count_words("你好 world") == 3

    def test_empty(self):
        """空"""
        assert helpers.count_words("") == 0

    def test_none(self):
        """None"""
        assert helpers.count_words(None) == 0


class TestCountChars:
    """count_chars 函数测试"""

    def test_with_whitespace(self):
        """含空白"""
        assert helpers.count_chars("hello world") == 10

    def test_without_whitespace(self):
        """不含空白"""
        assert helpers.count_chars("hello world", ignore_whitespace=False) == 11

    def test_empty(self):
        """空"""
        assert helpers.count_chars("") == 0


class TestCountLines:
    """count_lines 函数测试"""

    def test_single_line(self):
        """单行"""
        assert helpers.count_lines("hello") == 1

    def test_multiple_lines(self):
        """多行"""
        assert helpers.count_lines("line1\nline2\nline3") == 3

    def test_empty(self):
        """空"""
        assert helpers.count_lines("") == 0


class TestHighlightKeywords:
    """highlight_keywords 函数测试"""

    def test_single_keyword(self):
        """单个关键词"""
        result = helpers.highlight_keywords("hello world", ["world"])
        assert "**world**" in result

    def test_multiple_keywords(self):
        """多个关键词"""
        result = helpers.highlight_keywords("hello world foo", ["world", "foo"])
        assert "**world**" in result
        assert "**foo**" in result

    def test_case_insensitive(self):
        """大小写不敏感"""
        result = helpers.highlight_keywords("Hello World", ["hello"])
        assert "**hello**" in result

    def test_no_keywords(self):
        """无关键词"""
        assert helpers.highlight_keywords("hello", []) == "hello"

    def test_empty_text(self):
        """空文本"""
        assert helpers.highlight_keywords("", ["test"]) == ""


class TestExtractKeywords:
    """extract_keywords 函数测试"""

    def test_english_text(self):
        """英文文本"""
        keywords = helpers.extract_keywords("machine learning machine learning data")
        assert "machine" in keywords
        assert "learning" in keywords

    def test_chinese_text(self):
        """中文文本"""
        keywords = helpers.extract_keywords("机器学习 机器学习 深度学习")
        assert "机器学习" in keywords or "深度学习" in keywords

    def test_max_keywords(self):
        """最大关键词数"""
        text = " ".join([f"word{i}" for i in range(50)])
        keywords = helpers.extract_keywords(text, max_keywords=5)
        assert len(keywords) <= 5

    def test_min_length(self):
        """最小长度过滤"""
        keywords = helpers.extract_keywords("a ab abc abcd", min_length=3)
        assert "abc" in keywords
        assert "abcd" in keywords
        assert "a" not in keywords
        assert "ab" not in keywords

    def test_empty_text(self):
        """空文本"""
        assert helpers.extract_keywords("") == []


class TestMaskSensitive:
    """mask_sensitive 函数测试"""

    def test_normal_mask(self):
        """正常脱敏"""
        result = helpers.mask_sensitive("1234567890123456")
        assert result.startswith("1234")
        assert result.endswith("3456")
        assert "*" in result

    def test_short_value(self):
        """短值全掩码"""
        result = helpers.mask_sensitive("12345678")
        assert result == "********"

    def test_custom_visible(self):
        """自定义可见字符数"""
        result = helpers.mask_sensitive("1234567890", visible_start=2, visible_end=2)
        assert result.startswith("12")
        assert result.endswith("90")

    def test_empty(self):
        """空值"""
        assert helpers.mask_sensitive("") == ""


class TestSafeFormat:
    """safe_format 函数测试"""

    def test_normal_format(self):
        """正常格式化"""
        assert helpers.safe_format("Hello {name}", name="World") == "Hello World"

    def test_missing_key(self):
        """缺失键不报错"""
        result = helpers.safe_format("Hello {name}", other="value")
        assert "{name}" in result

    def test_multiple_keys(self):
        """多个键"""
        result = helpers.safe_format("{a} {b} {c}", a="1", b="2", c="3")
        assert result == "1 2 3"


class TestPluralize:
    """pluralize 函数测试"""

    def test_singular(self):
        """单数"""
        assert helpers.pluralize(1, "item") == "item"

    def test_plural_default(self):
        """复数默认"""
        assert helpers.pluralize(2, "item") == "items"

    def test_plural_custom(self):
        """自定义复数"""
        assert helpers.pluralize(2, "child", "children") == "children"

    def test_zero(self):
        """零"""
        assert helpers.pluralize(0, "item") == "items"


class TestWrapText:
    """wrap_text 函数测试"""

    def test_wrap(self):
        """换行"""
        text = "a" * 100
        result = helpers.wrap_text(text, width=20)
        lines = result.split("\n")
        assert all(len(line) <= 20 for line in lines)

    def test_with_indent(self):
        """带缩进"""
        result = helpers.wrap_text("hello world", width=80, indent="  ")
        assert result.startswith("  ")

    def test_empty(self):
        """空"""
        assert helpers.wrap_text("", width=80) == ""


# ===== 日期时间处理测试 =====


class TestNowUtc:
    """now_utc 函数测试"""

    def test_returns_datetime(self):
        """返回 datetime"""
        result = helpers.now_utc()
        assert isinstance(result, datetime)

    def test_has_timezone(self):
        """有时区"""
        result = helpers.now_utc()
        assert result.tzinfo is not None


class TestNowLocal:
    """now_local 函数测试"""

    def test_returns_datetime(self):
        """返回 datetime"""
        result = helpers.now_local()
        assert isinstance(result, datetime)


class TestFormatDatetime:
    """format_datetime 函数测试"""

    def test_default_format(self):
        """默认格式"""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        assert helpers.format_datetime(dt) == "2024-01-15 10:30:00"

    def test_custom_format(self):
        """自定义格式"""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        assert helpers.format_datetime(dt, "%Y/%m/%d") == "2024/01/15"

    def test_none(self):
        """None"""
        assert helpers.format_datetime(None) == ""


class TestFormatDate:
    """format_date 函数测试"""

    def test_default_format(self):
        """默认格式"""
        d = date(2024, 1, 15)
        assert helpers.format_date(d) == "2024-01-15"

    def test_none(self):
        """None"""
        assert helpers.format_date(None) == ""


class TestParseDatetime:
    """parse_datetime 函数测试"""

    def test_iso_format(self):
        """ISO 格式"""
        result = helpers.parse_datetime("2024-01-15 10:30:00")
        assert result == datetime(2024, 1, 15, 10, 30, 0)

    def test_date_only(self):
        """仅日期"""
        result = helpers.parse_datetime("2024-01-15")
        assert result == datetime(2024, 1, 15)

    def test_slash_format(self):
        """斜杠格式"""
        result = helpers.parse_datetime("2024/01/15")
        assert result == datetime(2024, 1, 15)

    def test_invalid(self):
        """无效字符串"""
        assert helpers.parse_datetime("invalid") is None

    def test_empty(self):
        """空字符串"""
        assert helpers.parse_datetime("") is None

    def test_custom_formats(self):
        """自定义格式列表"""
        result = helpers.parse_datetime("15.01.2024", formats=["%d.%m.%Y"])
        assert result == datetime(2024, 1, 15)


class TestTimestampFunctions:
    """时间戳函数测试"""

    def test_timestamp_now(self):
        """当前时间戳"""
        ts = helpers.timestamp_now()
        assert isinstance(ts, int)
        assert ts > 0

    def test_timestamp_ms_now(self):
        """毫秒时间戳"""
        ts = helpers.timestamp_ms_now()
        assert isinstance(ts, int)
        assert ts > 0

    def test_format_timestamp(self):
        """格式化时间戳"""
        ts = int(time.mktime(datetime(2024, 1, 15, 0, 0, 0).timetuple()))
        result = helpers.format_timestamp(ts, "%Y-%m-%d")
        assert "2024-01-15" in result


class TestTimeAgo:
    """time_ago 函数测试"""

    def test_just_now(self):
        """刚刚"""
        now = helpers.now_local()
        assert helpers.time_ago(now) == "刚刚"

    def test_minutes_ago(self):
        """几分钟前"""
        past = helpers.now_local() - timedelta(minutes=5)
        result = helpers.time_ago(past)
        assert "分钟前" in result

    def test_hours_ago(self):
        """几小时前"""
        past = helpers.now_local() - timedelta(hours=3)
        result = helpers.time_ago(past)
        assert "小时前" in result

    def test_days_ago(self):
        """几天前"""
        past = helpers.now_local() - timedelta(days=3)
        result = helpers.time_ago(past)
        assert "天前" in result

    def test_none(self):
        """None"""
        assert helpers.time_ago(None) == ""


class TestDateOperations:
    """日期操作测试"""

    def test_days_between(self):
        """计算天数差"""
        start = date(2024, 1, 1)
        end = date(2024, 1, 10)
        assert helpers.days_between(start, end) == 9

    def test_add_days(self):
        """日期加天数"""
        d = date(2024, 1, 1)
        assert helpers.add_days(d, 10) == date(2024, 1, 11)

    def test_add_days_negative(self):
        """日期减天数"""
        d = date(2024, 1, 10)
        assert helpers.add_days(d, -5) == date(2024, 1, 5)

    def test_is_weekend(self):
        """判断周末"""
        saturday = date(2024, 1, 13)  # 周六
        monday = date(2024, 1, 15)  # 周一
        assert helpers.is_weekend(saturday) is True
        assert helpers.is_weekend(monday) is False

    def test_start_of_day(self):
        """当天开始"""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = helpers.start_of_day(dt)
        assert result.hour == 0
        assert result.minute == 0

    def test_end_of_day(self):
        """当天结束"""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = helpers.end_of_day(dt)
        assert result.hour == 23
        assert result.minute == 59


# ===== ID 生成测试 =====


class TestIdGeneration:
    """ID 生成函数测试"""

    def test_generate_uuid(self):
        """UUID 生成"""
        uid = helpers.generate_uuid()
        assert isinstance(uid, str)
        assert len(uid) == 36  # UUID 标准长度

    def test_generate_short_id(self):
        """短 ID 生成"""
        sid = helpers.generate_short_id(8)
        assert len(sid) == 8

    def test_generate_short_id_custom_length(self):
        """自定义长度短 ID"""
        sid = helpers.generate_short_id(16)
        assert len(sid) == 16

    def test_generate_numeric_id(self):
        """数字 ID 生成"""
        nid = helpers.generate_numeric_id(6)
        assert len(nid) == 6
        assert nid.isdigit()

    def test_generate_request_id(self):
        """请求 ID 生成"""
        rid = helpers.generate_request_id()
        assert rid.startswith("req-")

    def test_generate_session_id(self):
        """会话 ID 生成"""
        sid = helpers.generate_session_id()
        assert sid.startswith("sess-")

    def test_generate_task_id(self):
        """任务 ID 生成"""
        tid = helpers.generate_task_id()
        assert tid.startswith("task-")

    def test_generate_correlation_id(self):
        """关联 ID 生成"""
        cid = helpers.generate_correlation_id()
        assert cid.startswith("corr-")

    def test_generate_token(self):
        """令牌生成"""
        token = helpers.generate_token(32)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_api_key(self):
        """API 密钥生成"""
        key = helpers.generate_api_key()
        assert key.startswith("sk-")

    def test_generate_api_key_custom_prefix(self):
        """自定义前缀 API 密钥"""
        key = helpers.generate_api_key(prefix="pk")
        assert key.startswith("pk-")

    def test_uniqueness(self):
        """唯一性"""
        ids = {helpers.generate_uuid() for _ in range(100)}
        assert len(ids) == 100


# ===== 哈希函数测试 =====


class TestHashFunctions:
    """哈希函数测试"""

    def test_md5_hash(self):
        """MD5 哈希"""
        result = helpers.md5_hash("hello")
        assert result == "5d41402abc4b2a76b9719d911017c592"

    def test_sha1_hash(self):
        """SHA1 哈希"""
        result = helpers.sha1_hash("hello")
        assert result == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"

    def test_sha256_hash(self):
        """SHA256 哈希"""
        result = helpers.sha256_hash("hello")
        assert len(result) == 64

    def test_sha512_hash(self):
        """SHA512 哈希"""
        result = helpers.sha512_hash("hello")
        assert len(result) == 128

    def test_hash_with_algorithm_md5(self):
        """指定算法 MD5"""
        result = helpers.hash_with_algorithm("hello", "md5")
        assert result == helpers.md5_hash("hello")

    def test_hash_with_algorithm_sha256(self):
        """指定算法 SHA256"""
        result = helpers.hash_with_algorithm("hello", "sha256")
        assert result == helpers.sha256_hash("hello")

    def test_hash_with_algorithm_uppercase(self):
        """大写算法名"""
        result = helpers.hash_with_algorithm("hello", "SHA256")
        assert result == helpers.sha256_hash("hello")

    def test_hash_with_invalid_algorithm(self):
        """无效算法"""
        with pytest.raises(ValueError):
            helpers.hash_with_algorithm("hello", "invalid")

    def test_hash_empty_string(self):
        """空字符串哈希"""
        result = helpers.sha256_hash("")
        assert len(result) == 64

    def test_content_hash(self):
        """内容哈希"""
        result = helpers.content_hash({"a": 1, "b": 2})
        assert isinstance(result, str)
        assert len(result) == 64

    def test_content_hash_consistent(self):
        """内容哈希一致性"""
        h1 = helpers.content_hash({"a": 1, "b": 2})
        h2 = helpers.content_hash({"b": 2, "a": 1})  # 顺序不同
        assert h1 == h2  # sort_keys 确保一致

    def test_cache_key_hash(self):
        """缓存键哈希"""
        key = helpers.cache_key_hash("arg1", "arg2", kwarg="value")
        assert isinstance(key, str)
        assert len(key) == 32

    def test_cache_key_hash_different_args(self):
        """不同参数不同哈希"""
        k1 = helpers.cache_key_hash("a")
        k2 = helpers.cache_key_hash("b")
        assert k1 != k2


class TestHashFile:
    """hash_file 函数测试"""

    def test_hash_file(self, tmp_path):
        """文件哈希"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("hello world", encoding="utf-8")
        result = helpers.hash_file(str(filepath))
        assert len(result) == 64

    def test_hash_file_md5(self, tmp_path):
        """MD5 文件哈希"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("hello world", encoding="utf-8")
        result = helpers.hash_file(str(filepath), algorithm="md5")
        assert len(result) == 32

    def test_hash_file_invalid_algorithm(self, tmp_path):
        """无效算法"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("hello", encoding="utf-8")
        with pytest.raises(ValueError):
            helpers.hash_file(str(filepath), algorithm="invalid")


# ===== 文件操作测试 =====


class TestFileOperations:
    """文件操作测试"""

    def test_ensure_dir(self, tmp_path):
        """确保目录存在"""
        dir_path = tmp_path / "subdir" / "nested"
        result = helpers.ensure_dir(str(dir_path))
        assert dir_path.exists()
        assert dir_path.is_dir()

    def test_safe_read_file(self, tmp_path):
        """安全读取文件"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("hello", encoding="utf-8")
        assert helpers.safe_read_file(str(filepath)) == "hello"

    def test_safe_read_file_not_exists(self):
        """读取不存在的文件"""
        assert helpers.safe_read_file("/nonexistent/file.txt") is None

    def test_safe_write_file(self, tmp_path):
        """安全写入文件"""
        filepath = tmp_path / "output.txt"
        assert helpers.safe_write_file(str(filepath), "hello") is True
        assert filepath.read_text(encoding="utf-8") == "hello"

    def test_safe_write_file_creates_parent(self, tmp_path):
        """写入时创建父目录"""
        filepath = tmp_path / "subdir" / "output.txt"
        assert helpers.safe_write_file(str(filepath), "hello") is True
        assert filepath.exists()

    def test_safe_read_json(self, tmp_path):
        """安全读取 JSON"""
        filepath = tmp_path / "data.json"
        filepath.write_text('{"key": "value"}', encoding="utf-8")
        result = helpers.safe_read_json(str(filepath))
        assert result == {"key": "value"}

    def test_safe_read_json_invalid(self, tmp_path):
        """读取无效 JSON"""
        filepath = tmp_path / "data.json"
        filepath.write_text("invalid json", encoding="utf-8")
        assert helpers.safe_read_json(str(filepath)) is None

    def test_safe_read_json_not_exists(self):
        """读取不存在的 JSON"""
        assert helpers.safe_read_json("/nonexistent/file.json") is None

    def test_safe_write_json(self, tmp_path):
        """安全写入 JSON"""
        filepath = tmp_path / "data.json"
        assert helpers.safe_write_json(str(filepath), {"key": "value"}) is True
        result = helpers.safe_read_json(str(filepath))
        assert result == {"key": "value"}

    def test_file_size(self, tmp_path):
        """文件大小"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("hello", encoding="utf-8")
        assert helpers.file_size(str(filepath)) == 5

    def test_file_size_not_exists(self):
        """不存在的文件大小为 0"""
        assert helpers.file_size("/nonexistent/file.txt") == 0

    def test_format_file_size(self):
        """格式化文件大小"""
        assert helpers.format_file_size(0) == "0 B"
        assert helpers.format_file_size(1023) == "1023 B"
        assert "KB" in helpers.format_file_size(1024)
        assert "MB" in helpers.format_file_size(1024 * 1024)
        assert "GB" in helpers.format_file_size(1024 * 1024 * 1024)

    def test_format_file_size_negative(self):
        """负数"""
        assert helpers.format_file_size(-1) == "0 B"

    def test_file_size_human(self, tmp_path):
        """文件大小可读字符串"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("hello", encoding="utf-8")
        result = helpers.file_size_human(str(filepath))
        assert "B" in result

    def test_list_files(self, tmp_path):
        """列出文件"""
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        files = helpers.list_files(str(tmp_path))
        assert len(files) == 2

    def test_list_files_pattern(self, tmp_path):
        """按模式列出文件"""
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.py").write_text("b", encoding="utf-8")
        files = helpers.list_files(str(tmp_path), pattern="*.py")
        assert len(files) == 1

    def test_list_files_recursive(self, tmp_path):
        """递归列出文件"""
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / "b.txt").write_text("b", encoding="utf-8")
        files = helpers.list_files(str(tmp_path), recursive=True)
        assert len(files) == 2

    def test_list_files_not_exists(self):
        """目录不存在"""
        assert helpers.list_files("/nonexistent/dir") == []

    def test_delete_file(self, tmp_path):
        """删除文件"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("hello", encoding="utf-8")
        assert helpers.delete_file(str(filepath)) is True
        assert not filepath.exists()

    def test_delete_file_not_exists(self):
        """删除不存在的文件"""
        assert helpers.delete_file("/nonexistent/file.txt") is False

    def test_copy_file(self, tmp_path):
        """复制文件"""
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("hello", encoding="utf-8")
        assert helpers.copy_file(str(src), str(dst)) is True
        assert dst.read_text(encoding="utf-8") == "hello"

    def test_move_file(self, tmp_path):
        """移动文件"""
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("hello", encoding="utf-8")
        assert helpers.move_file(str(src), str(dst)) is True
        assert dst.read_text(encoding="utf-8") == "hello"
        assert not src.exists()

    def test_file_exists(self, tmp_path):
        """文件存在判断"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("hello", encoding="utf-8")
        assert helpers.file_exists(str(filepath)) is True
        assert helpers.file_exists(str(tmp_path / "nonexistent.txt")) is False

    def test_dir_exists(self, tmp_path):
        """目录存在判断"""
        assert helpers.dir_exists(str(tmp_path)) is True
        assert helpers.dir_exists(str(tmp_path / "nonexistent")) is False

    def test_get_file_extension(self):
        """获取扩展名"""
        assert helpers.get_file_extension("file.txt") == "txt"
        assert helpers.get_file_extension("file.PY") == "py"
        assert helpers.get_file_extension("file") == ""
        assert helpers.get_file_extension("file.tar.gz") == "gz"

    def test_get_filename(self):
        """获取文件名"""
        assert helpers.get_filename("/path/to/file.txt") == "file.txt"
        assert helpers.get_filename("file.txt") == "file.txt"

    def test_get_filename_without_ext(self):
        """获取不含扩展名的文件名"""
        assert helpers.get_filename_without_ext("/path/to/file.txt") == "file"
        assert helpers.get_filename_without_ext("file.txt") == "file"


# ===== JSON 工具测试 =====


class TestJsonTools:
    """JSON 工具测试"""

    def test_safe_json_dumps_basic(self):
        """基本序列化"""
        result = helpers.safe_json_dumps({"key": "value"})
        assert json.loads(result) == {"key": "value"}

    def test_safe_json_dumps_datetime(self):
        """序列化 datetime"""
        dt = datetime(2024, 1, 15, 10, 30)
        result = helpers.safe_json_dumps({"time": dt})
        assert "2024-01-15T10:30:00" in result

    def test_safe_json_dumps_set(self):
        """序列化 set"""
        result = helpers.safe_json_dumps({"items": {1, 2, 3}})
        parsed = json.loads(result)
        assert sorted(parsed["items"]) == [1, 2, 3]

    def test_safe_json_dumps_bytes(self):
        """序列化 bytes"""
        result = helpers.safe_json_dumps({"data": b"hello"})
        parsed = json.loads(result)
        assert parsed["data"] == "hello"

    def test_safe_json_dumps_indent(self):
        """带缩进序列化"""
        result = helpers.safe_json_dumps({"key": "value"}, indent=2)
        assert "\n" in result

    def test_safe_json_loads_valid(self):
        """有效 JSON 反序列化"""
        assert helpers.safe_json_loads('{"key": "value"}') == {"key": "value"}

    def test_safe_json_loads_invalid(self):
        """无效 JSON"""
        assert helpers.safe_json_loads("invalid") is None

    def test_safe_json_loads_empty(self):
        """空字符串"""
        assert helpers.safe_json_loads("") is None

    def test_safe_json_loads_with_default(self):
        """带默认值"""
        assert helpers.safe_json_loads("invalid", default={}) == {}


class TestDictOperations:
    """字典操作测试"""

    def test_merge_dicts_shallow(self):
        """浅合并"""
        result = helpers.merge_dicts({"a": 1}, {"b": 2}, deep=False)
        assert result == {"a": 1, "b": 2}

    def test_merge_dicts_deep(self):
        """深合并"""
        d1 = {"a": {"x": 1, "y": 2}}
        d2 = {"a": {"y": 3, "z": 4}}
        result = helpers.merge_dicts(d1, d2, deep=True)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_merge_dicts_overwrite(self):
        """合并覆盖"""
        result = helpers.merge_dicts({"a": 1}, {"a": 2})
        assert result == {"a": 2}

    def test_merge_dicts_skip_non_dict(self):
        """跳过非字典"""
        result = helpers.merge_dicts({"a": 1}, "not a dict", {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_deep_get(self):
        """深度获取"""
        data = {"a": {"b": {"c": "value"}}}
        assert helpers.deep_get(data, "a.b.c") == "value"

    def test_deep_get_default(self):
        """深度获取默认值"""
        data = {"a": {"b": {}}}
        assert helpers.deep_get(data, "a.b.c", default="default") == "default"

    def test_deep_get_empty(self):
        """空数据"""
        assert helpers.deep_get({}, "a.b") is None
        assert helpers.deep_get(None, "a.b") is None

    def test_deep_set(self):
        """深度设置"""
        data = {}
        helpers.deep_set(data, "a.b.c", "value")
        assert data == {"a": {"b": {"c": "value"}}}

    def test_deep_set_existing(self):
        """深度设置到已有结构"""
        data = {"a": {"b": {}}}
        helpers.deep_set(data, "a.b.c", "value")
        assert data == {"a": {"b": {"c": "value"}}}

    def test_flatten_dict(self):
        """扁平化字典"""
        data = {"a": {"b": {"c": 1}}, "d": 2}
        result = helpers.flatten_dict(data)
        assert result == {"a.b.c": 1, "d": 2}

    def test_unflatten_dict(self):
        """反扁平化字典"""
        data = {"a.b.c": 1, "d": 2}
        result = helpers.unflatten_dict(data)
        assert result == {"a": {"b": {"c": 1}}, "d": 2}

    def test_remove_none_values(self):
        """移除 None 值"""
        data = {"a": 1, "b": None, "c": 3}
        result = helpers.remove_none_values(data)
        assert result == {"a": 1, "c": 3}

    def test_remove_empty_values(self):
        """移除空值"""
        data = {"a": 1, "b": None, "c": "", "d": [], "e": {}}
        result = helpers.remove_empty_values(data)
        assert result == {"a": 1}


# ===== 异步辅助测试 =====


class TestAsyncHelpers:
    """异步辅助函数测试"""

    @pytest.mark.asyncio
    async def test_gather_with_limit(self):
        """并发限制"""
        async def task(n):
            await asyncio.sleep(0.01)
            return n

        coros = [task(i) for i in range(5)]
        results = await helpers.gather_with_limit(coros, limit=3)
        assert sorted(results) == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_run_with_timeout_success(self):
        """超时执行成功"""
        async def quick_task():
            await asyncio.sleep(0.01)
            return "done"

        result = await helpers.run_with_timeout(quick_task(), timeout=1.0)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_run_with_timeout_exceeded(self):
        """超时返回默认值"""
        async def slow_task():
            await asyncio.sleep(10)
            return "done"

        result = await helpers.run_with_timeout(slow_task(), timeout=0.05, default="timeout")
        assert result == "timeout"

    @pytest.mark.asyncio
    async def test_retry_async_success(self):
        """异步重试成功"""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await helpers.retry_async(func, max_retries=3, delay=0.01)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_with_failures(self):
        """异步重试带失败"""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "success"

        result = await helpers.retry_async(func, max_retries=5, delay=0.01)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_all_fail(self):
        """异步重试全部失败"""
        async def func():
            raise ValueError("always fail")

        with pytest.raises(ValueError):
            await helpers.retry_async(func, max_retries=2, delay=0.01)

    @pytest.mark.asyncio
    async def test_run_in_executor(self):
        """线程池执行"""
        def sync_func(x):
            return x * 2

        result = await helpers.run_in_executor(sync_func, 5)
        assert result == 10


# ===== 类型转换测试 =====


class TestTypeConversion:
    """类型转换测试"""

    def test_to_int_valid(self):
        """有效整数"""
        assert helpers.to_int(42) == 42
        assert helpers.to_int("42") == 42
        assert helpers.to_int(42.9) == 42

    def test_to_int_invalid(self):
        """无效整数"""
        assert helpers.to_int("invalid") == 0
        assert helpers.to_int(None) == 0

    def test_to_int_with_default(self):
        """带默认值"""
        assert helpers.to_int("invalid", default=-1) == -1

    def test_to_float_valid(self):
        """有效浮点数"""
        assert helpers.to_float(3.14) == 3.14
        assert helpers.to_float("3.14") == 3.14
        assert helpers.to_float(3) == 3.0

    def test_to_float_invalid(self):
        """无效浮点数"""
        assert helpers.to_float("invalid") == 0.0
        assert helpers.to_float(None) == 0.0

    def test_to_str(self):
        """转字符串"""
        assert helpers.to_str(42) == "42"
        assert helpers.to_str("hello") == "hello"
        assert helpers.to_str(None) == ""
        assert helpers.to_str(None, default="null") == "null"

    def test_to_bool_true_values(self):
        """真值"""
        assert helpers.to_bool(True) is True
        assert helpers.to_bool(1) is True
        assert helpers.to_bool("true") is True
        assert helpers.to_bool("yes") is True
        assert helpers.to_bool("on") is True
        assert helpers.to_bool("1") is True

    def test_to_bool_false_values(self):
        """假值"""
        assert helpers.to_bool(False) is False
        assert helpers.to_bool(0) is False
        assert helpers.to_bool("false") is False
        assert helpers.to_bool("no") is False
        assert helpers.to_bool("") is False

    def test_to_bool_none(self):
        """None"""
        assert helpers.to_bool(None) is False
        assert helpers.to_bool(None, default=True) is True

    def test_to_list_from_list(self):
        """列表转列表"""
        assert helpers.to_list([1, 2, 3]) == [1, 2, 3]

    def test_to_list_from_tuple(self):
        """元组转列表"""
        assert helpers.to_list((1, 2, 3)) == [1, 2, 3]

    def test_to_list_from_set(self):
        """集合转列表"""
        result = helpers.to_list({1, 2, 3})
        assert sorted(result) == [1, 2, 3]

    def test_to_list_from_string(self):
        """字符串转列表"""
        assert helpers.to_list("hello") == ["hello"]

    def test_to_list_from_none(self):
        """None 转列表"""
        assert helpers.to_list(None) == []

    def test_to_dict_from_dict(self):
        """字典转字典"""
        d = {"a": 1}
        assert helpers.to_dict(d) == d

    def test_to_dict_from_string(self):
        """字符串转字典"""
        assert helpers.to_dict('{"a": 1}') == {"a": 1}

    def test_to_dict_from_none(self):
        """None 转字典"""
        assert helpers.to_dict(None) == {}


# ===== 集合工具测试 =====


class TestCollectionTools:
    """集合工具测试"""

    def test_chunk_list(self):
        """列表分块"""
        result = helpers.chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_chunk_list_exact(self):
        """正好分块"""
        result = helpers.chunk_list([1, 2, 3, 4], 2)
        assert result == [[1, 2], [3, 4]]

    def test_chunk_list_invalid_size(self):
        """无效块大小"""
        result = helpers.chunk_list([1, 2, 3], 0)
        assert result == [[1, 2, 3]]

    def test_flatten_list(self):
        """扁平化一层"""
        result = helpers.flatten_list([[1, 2], [3, 4], 5])
        assert result == [1, 2, 3, 4, 5]

    def test_deep_flatten(self):
        """深度扁平化"""
        result = helpers.deep_flatten([[1, [2, [3]]], 4])
        assert result == [1, 2, 3, 4]

    def test_unique_list(self):
        """去重保持顺序"""
        result = helpers.unique_list([3, 1, 2, 1, 3, 4])
        assert result == [3, 1, 2, 4]

    def test_unique_list_with_key(self):
        """按键去重"""
        data = [{"id": 1}, {"id": 2}, {"id": 1}]
        result = helpers.unique_list(data, key=lambda x: x["id"])
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    def test_group_by(self):
        """分组"""
        data = [1, 2, 3, 4, 5, 6]
        result = helpers.group_by(data, key=lambda x: x % 2)
        assert result[0] == [2, 4, 6]
        assert result[1] == [1, 3, 5]

    def test_partition(self):
        """分区"""
        data = [1, 2, 3, 4, 5]
        truthy, falsy = helpers.partition(data, predicate=lambda x: x > 3)
        assert truthy == [4, 5]
        assert falsy == [1, 2, 3]


# ===== 数学工具测试 =====


class TestMathTools:
    """数学工具测试"""

    def test_clamp_within_range(self):
        """范围内"""
        assert helpers.clamp(5, 1, 10) == 5

    def test_clamp_below_min(self):
        """低于最小值"""
        assert helpers.clamp(0, 1, 10) == 1

    def test_clamp_above_max(self):
        """高于最大值"""
        assert helpers.clamp(15, 1, 10) == 10

    def test_percentage(self):
        """百分比"""
        assert helpers.percentage(25, 100) == 25.0

    def test_percentage_zero_total(self):
        """总数为零"""
        assert helpers.percentage(25, 0) == 0.0

    def test_percentage_decimals(self):
        """小数位"""
        assert helpers.percentage(1, 3, decimals=2) == 33.33

    def test_average(self):
        """平均值"""
        assert helpers.average([1, 2, 3, 4, 5]) == 3.0

    def test_average_empty(self):
        """空列表"""
        assert helpers.average([]) == 0.0

    def test_median_odd(self):
        """中位数（奇数个）"""
        assert helpers.median([1, 3, 5]) == 5

    def test_median_even(self):
        """中位数（偶数个）"""
        assert helpers.median([1, 2, 3, 4]) == 2.5

    def test_median_empty(self):
        """空列表中位数"""
        assert helpers.median([]) == 0.0

    def test_round_up(self):
        """向上取整"""
        assert helpers.round_up(3.2) == 4.0
        assert helpers.round_up(3.14159, decimals=2) == 3.15

    def test_round_down(self):
        """向下取整"""
        assert helpers.round_down(3.8) == 3.0
        assert helpers.round_down(3.14159, decimals=2) == 3.14


# ===== 环境工具测试 =====


class TestEnvironmentTools:
    """环境工具测试"""

    def test_is_windows(self):
        """判断 Windows"""
        result = helpers.is_windows()
        assert isinstance(result, bool)

    def test_is_linux(self):
        """判断 Linux"""
        result = helpers.is_linux()
        assert isinstance(result, bool)

    def test_is_macos(self):
        """判断 macOS"""
        result = helpers.is_macos()
        assert isinstance(result, bool)

    def test_get_env(self):
        """获取环境变量"""
        os.environ["TEST_ENV_VAR"] = "test_value"
        assert helpers.get_env("TEST_ENV_VAR") == "test_value"
        del os.environ["TEST_ENV_VAR"]

    def test_get_env_default(self):
        """默认值"""
        assert helpers.get_env("NONEXISTENT_VAR", default="default") == "default"

    def test_get_env_required(self):
        """必填环境变量"""
        with pytest.raises(ValueError):
            helpers.get_env("NONEXISTENT_REQUIRED_VAR", required=True)

    def test_get_env_int(self):
        """整数环境变量"""
        os.environ["TEST_INT_VAR"] = "42"
        assert helpers.get_env_int("TEST_INT_VAR") == 42
        del os.environ["TEST_INT_VAR"]

    def test_get_env_int_default(self):
        """整数默认值"""
        assert helpers.get_env_int("NONEXISTENT_INT", default=10) == 10

    def test_get_env_int_invalid(self):
        """无效整数"""
        os.environ["TEST_INVALID_INT"] = "not_a_number"
        assert helpers.get_env_int("TEST_INVALID_INT", default=0) == 0
        del os.environ["TEST_INVALID_INT"]

    def test_get_env_float(self):
        """浮点环境变量"""
        os.environ["TEST_FLOAT_VAR"] = "3.14"
        assert helpers.get_env_float("TEST_FLOAT_VAR") == 3.14
        del os.environ["TEST_FLOAT_VAR"]

    def test_get_env_bool(self):
        """布尔环境变量"""
        os.environ["TEST_BOOL_VAR"] = "true"
        assert helpers.get_env_bool("TEST_BOOL_VAR") is True
        del os.environ["TEST_BOOL_VAR"]

    def test_get_env_bool_false(self):
        """布尔假值"""
        os.environ["TEST_BOOL_FALSE"] = "false"
        assert helpers.get_env_bool("TEST_BOOL_FALSE") is False
        del os.environ["TEST_BOOL_FALSE"]

    def test_get_env_list(self):
        """列表环境变量"""
        os.environ["TEST_LIST_VAR"] = "a,b,c"
        result = helpers.get_env_list("TEST_LIST_VAR")
        assert result == ["a", "b", "c"]
        del os.environ["TEST_LIST_VAR"]

    def test_get_env_list_custom_separator(self):
        """自定义分隔符列表"""
        os.environ["TEST_LIST_SEP"] = "a;b;c"
        result = helpers.get_env_list("TEST_LIST_SEP", separator=";")
        assert result == ["a", "b", "c"]
        del os.environ["TEST_LIST_SEP"]


# ===== 装饰器测试 =====


class TestDecorators:
    """装饰器测试"""

    def test_memoize(self):
        """记忆化装饰器"""
        call_count = 0

        @helpers.memoize
        def expensive_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert expensive_func(5) == 10
        assert expensive_func(5) == 10
        assert call_count == 1  # 第二次从缓存读取

    def test_memoize_different_args(self):
        """不同参数不缓存"""
        call_count = 0

        @helpers.memoize
        def func(x):
            nonlocal call_count
            call_count += 1
            return x

        func(1)
        func(2)
        assert call_count == 2

    def test_retry_decorator_success(self):
        """重试装饰器成功"""

        @helpers.retry(max_retries=2, delay=0.01)
        def func():
            return "success"

        assert func() == "success"

    def test_retry_decorator_with_failures(self):
        """重试装饰器带失败"""
        call_count = 0

        @helpers.retry(max_retries=3, delay=0.01)
        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "success"

        assert func() == "success"
        assert call_count == 3

    def test_retry_decorator_all_fail(self):
        """重试装饰器全部失败"""

        @helpers.retry(max_retries=2, delay=0.01)
        def func():
            raise ValueError("always fail")

        with pytest.raises(ValueError):
            func()

    def test_timed_decorator(self):
        """计时装饰器"""
        @helpers.timed
        def func():
            return "result"

        assert func() == "result"


# ===== 编码工具测试 =====


class TestEncodingTools:
    """编码工具测试"""

    def test_encode_base64(self):
        """Base64 编码"""
        result = helpers.encode_base64("hello")
        assert isinstance(result, str)

    def test_decode_base64(self):
        """Base64 解码"""
        encoded = helpers.encode_base64("hello")
        assert helpers.decode_base64(encoded) == "hello"

    def test_encode_url(self):
        """URL 编码"""
        assert helpers.encode_url("hello world") == "hello%20world"

    def test_decode_url(self):
        """URL 解码"""
        assert helpers.decode_url("hello%20world") == "hello world"

    def test_encode_decode_roundtrip(self):
        """编解码往返"""
        original = "你好世界!@#$%"
        encoded = helpers.encode_url(original)
        assert helpers.decode_url(encoded) == original


# ===== 调试工具测试 =====


class TestDebugTools:
    """调试工具测试"""

    def test_pretty_print(self):
        """美化打印"""
        result = helpers.pretty_print({"key": "value"})
        assert isinstance(result, str)
        assert "key" in result

    def test_pretty_print_with_indent(self):
        """带缩进美化打印"""
        result = helpers.pretty_print({"key": "value"}, indent=4)
        assert "\n" in result

    def test_get_object_size(self):
        """对象大小"""
        size = helpers.get_object_size("hello")
        assert isinstance(size, int)
        assert size > 0

    def test_class_name(self):
        """类名"""
        assert helpers.class_name("string") == "str"
        assert helpers.class_name(42) == "int"
        assert helpers.class_name([]) == "list"

    def test_method_exists(self):
        """方法存在检查"""
        assert helpers.method_exists("hello", "upper") is True
        assert helpers.method_exists("hello", "nonexistent") is False

    def test_safe_call_success(self):
        """安全调用成功"""
        result = helpers.safe_call(lambda x: x * 2, 5)
        assert result == 10

    def test_safe_call_exception(self):
        """安全调用异常"""
        def failing_func():
            raise ValueError("error")

        result = helpers.safe_call(failing_func, default="error_default")
        assert result == "error_default"

    def test_safe_getattr(self):
        """安全获取属性"""
        obj = type("Obj", (), {"attr": "value"})()
        assert helpers.safe_getattr(obj, "attr") == "value"
        assert helpers.safe_getattr(obj, "nonexistent", default="default") == "default"


# ===== 集成测试 =====


class TestIntegration:
    """集成测试"""

    def test_string_processing_pipeline(self):
        """字符串处理管道"""
        text = "  Hello, World! This is a Test.  "
        cleaned = helpers.strip_whitespace(text, aggressive=True)
        slug = helpers.slugify(cleaned)
        assert "hello" in slug
        assert "world" in slug

    def test_json_file_roundtrip(self, tmp_path):
        """JSON 文件往返"""
        data = {"name": "测试", "value": 42, "list": [1, 2, 3]}
        filepath = tmp_path / "data.json"
        assert helpers.safe_write_json(str(filepath), data) is True
        loaded = helpers.safe_read_json(str(filepath))
        assert loaded == data

    def test_hash_and_cache_key(self):
        """哈希与缓存键"""
        content = "important data"
        h = helpers.sha256_hash(content)
        key = helpers.cache_key_hash(content)
        assert h != key
        assert len(h) == 64
        assert len(key) == 32

    def test_dict_manipulation_chain(self):
        """字典操作链"""
        data = {"a": {"b": 1}, "c": None}
        data = helpers.remove_none_values(data)
        helpers.deep_set(data, "a.d", 2)
        assert helpers.deep_get(data, "a.b") == 1
        assert helpers.deep_get(data, "a.d") == 2

    def test_id_generation_uniqueness(self):
        """ID 生成唯一性"""
        uuids = {helpers.generate_uuid() for _ in range(1000)}
        short_ids = {helpers.generate_short_id(12) for _ in range(1000)}
        assert len(uuids) == 1000
        assert len(short_ids) == 1000


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试"""

    def test_truncate_zero_length(self):
        """零长度截断"""
        result = helpers.truncate("hello", 0)
        assert result == ""

    def test_slugify_only_special_chars(self):
        """仅特殊字符"""
        assert helpers.slugify("!!!@@@###") == ""

    def test_count_words_only_whitespace(self):
        """仅空白"""
        assert helpers.count_words("   ") == 0

    def test_merge_dicts_empty(self):
        """合并空字典"""
        result = helpers.merge_dicts({}, {})
        assert result == {}

    def test_deep_get_very_nested(self):
        """深度嵌套获取"""
        data = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        assert helpers.deep_get(data, "a.b.c.d.e") == "deep"

    def test_chunk_list_empty(self):
        """空列表分块"""
        assert helpers.chunk_list([], 3) == []

    def test_unique_list_empty(self):
        """空列表去重"""
        assert helpers.unique_list([]) == []

    def test_to_int_boolean(self):
        """布尔转整数"""
        assert helpers.to_int(True) == 1
        assert helpers.to_int(False) == 0

    def test_mask_sensitive_empty(self):
        """空值脱敏"""
        assert helpers.mask_sensitive("") == ""

    def test_format_file_size_zero(self):
        """零大小"""
        assert helpers.format_file_size(0) == "0 B"

    def test_safe_json_loads_none(self):
        """None 输入"""
        assert helpers.safe_json_loads(None) is None

    def test_flatten_dict_empty(self):
        """空字典扁平化"""
        assert helpers.flatten_dict({}) == {}
