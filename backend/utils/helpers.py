"""通用工具函数

提供字符串处理、日期格式化、ID 生成、哈希函数、文件操作、
JSON 工具、异步辅助等通用能力。

所有函数均为纯函数（无副作用），可独立使用。
"""
import asyncio
import hashlib
import json
import os
import re
import secrets
import string
import sys
import time
import uuid
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")


# ===== 字符串处理 =====


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """截断字符串到指定长度，超出部分用后缀替代。

    Args:
        text: 原始字符串。
        max_length: 最大长度（含后缀）。
        suffix: 截断后缀。

    Returns:
        截断后的字符串。
    """
    if not text or len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        return suffix[:max_length]
    return text[: max_length - len(suffix)] + suffix


def truncate_words(text: str, max_words: int, suffix: str = "...") -> str:
    """按词数截断字符串。

    Args:
        text: 原始字符串。
        max_words: 最大词数。
        suffix: 截断后缀。

    Returns:
        截断后的字符串。
    """
    if not text:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + suffix


def slugify(text: str, separator: str = "-", max_length: int = 100) -> str:
    """将文本转换为 URL 友好的 slug。

    移除特殊字符，空格替换为分隔符，转为小写。

    Args:
        text: 原始文本。
        separator: 词分隔符。
        max_length: 最大长度。

    Returns:
        slug 字符串。
    """
    if not text:
        return ""
    # 转小写
    text = text.lower().strip()
    # 中文字符保留，其他非字母数字转为分隔符
    text = re.sub(r"[^\w\u4e00-\u9fff]+", separator, text)
    # 移除首尾分隔符
    text = text.strip(separator)
    # 截断
    if len(text) > max_length:
        text = text[:max_length].rstrip(separator)
    return text


def camel_to_snake(name: str) -> str:
    """驼峰命名转下划线命名。

    Args:
        name: 驼峰命名字符串。

    Returns:
        下划线命名字符串。
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def snake_to_camel(name: str) -> str:
    """下划线命名转驼峰命名。"""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def pascal_case(name: str) -> str:
    """转帕斯卡命名（首字母大写驼峰）。"""
    components = re.split(r"[_\-\s]+", name)
    return "".join(x.title() for x in components if x)


def remove_html_tags(text: str) -> str:
    """移除 HTML 标签。"""
    if not text:
        return text
    cleaned = re.sub(r"<[^>]+>", "", text)
    # 解码常见 HTML 实体
    entities = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
    }
    for entity, char in entities.items():
        cleaned = cleaned.replace(entity, char)
    return cleaned


def strip_whitespace(text: str, aggressive: bool = False) -> str:
    """去除空白字符。

    Args:
        text: 原始字符串。
        aggressive: 是否激进去除（所有多余空白合并为单个空格）。
    """
    if not text:
        return text
    if aggressive:
        return re.sub(r"\s+", " ", text).strip()
    return text.strip()


def count_words(text: str) -> int:
    """统计词数（中英文混合）。

    中文按字计数，英文按词计数。
    """
    if not text:
        return 0
    # 中文字符数
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    # 英文词数（移除中文后按空格分割）
    english_text = re.sub(r"[\u4e00-\u9fff]", " ", text)
    english_words = len(english_text.split())
    return chinese_chars + english_words


def count_chars(text: str, ignore_whitespace: bool = True) -> int:
    """统计字符数。"""
    if not text:
        return 0
    if ignore_whitespace:
        return len(re.sub(r"\s", "", text))
    return len(text)


def count_lines(text: str) -> int:
    """统计行数。"""
    if not text:
        return 0
    return len(text.splitlines())


def highlight_keywords(text: str, keywords: list, prefix: str = "**", suffix: str = "**") -> str:
    """高亮文本中的关键词。

    Args:
        text: 原始文本。
        keywords: 关键词列表。
        prefix: 高亮前缀（如 Markdown 的 **）。
        suffix: 高亮后缀。

    Returns:
        高亮后的文本。
    """
    if not text or not keywords:
        return text
    result = text
    for keyword in keywords:
        if keyword:
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            result = pattern.sub(f"{prefix}{keyword}{suffix}", result)
    return result


def extract_keywords(text: str, min_length: int = 2, max_keywords: int = 20) -> list:
    """从文本中提取关键词（基于词频的简单实现）。

    Args:
        text: 原始文本。
        min_length: 关键词最小长度。
        max_keywords: 返回的最大关键词数。

    Returns:
        关键词列表（按词频降序）。
    """
    if not text:
        return []
    # 移除标点与特殊字符
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", text)
    words = cleaned.split()
    # 过滤短词与停用词
    stopwords = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "the", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can", "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "as"}
    word_counts: dict[str, int] = {}
    for word in words:
        word_lower = word.lower()
        if len(word_lower) < min_length or word_lower in stopwords:
            continue
        word_counts[word_lower] = word_counts.get(word_lower, 0) + 1
    # 按词频排序
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_words[:max_keywords]]


def mask_sensitive(value: str, visible_start: int = 4, visible_end: int = 4, mask_char: str = "*") -> str:
    """脱敏敏感字符串。

    保留首尾若干字符，中间用掩码字符替代。

    Args:
        value: 原始字符串。
        visible_start: 开头可见字符数。
        visible_end: 结尾可见字符数。
        mask_char: 掩码字符。

    Returns:
        脱敏后的字符串。
    """
    if not value:
        return value
    length = len(value)
    if length <= visible_start + visible_end:
        return mask_char * length
    return value[:visible_start] + mask_char * (length - visible_start - visible_end) + value[-visible_end:]


def safe_format(template: str, **kwargs) -> str:
    """安全字符串格式化。

    使用 str.format_map 的安全版本，缺失键不报错。

    Args:
        template: 模板字符串（含 {key} 占位符）。
        **kwargs: 替换值。

    Returns:
        格式化后的字符串。
    """
    class SafeDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return template.format_map(SafeDict(**kwargs))


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    """英文复数化。

    Args:
        count: 数量。
        singular: 单数形式。
        plural: 可选，复数形式（默认加 s）。

    Returns:
        根据数量返回单数或复数形式。
    """
    if count == 1:
        return singular
    return plural or (singular + "s")


def wrap_text(text: str, width: int = 80, indent: str = "") -> str:
    """文本换行包装。

    Args:
        text: 原始文本。
        width: 每行最大宽度。
        indent: 缩进字符串。

    Returns:
        换行后的文本。
    """
    if not text:
        return text
    import textwrap
    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)


# ===== 日期时间处理 =====


def now_utc() -> datetime:
    """获取当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    """获取当前本地时间。"""
    return datetime.now()


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化日期时间。"""
    if dt is None:
        return ""
    return dt.strftime(fmt)


def format_date(d: date, fmt: str = "%Y-%m-%d") -> str:
    """格式化日期。"""
    if d is None:
        return ""
    return d.strftime(fmt)


def parse_datetime(value: str, formats: Optional[list] = None) -> Optional[datetime]:
    """解析日期时间字符串。

    Args:
        value: 日期时间字符串。
        formats: 尝试的格式列表。

    Returns:
        datetime 对象，解析失败返回 None。
    """
    if not value:
        return None
    formats = formats or [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def iso_now() -> str:
    """返回当前时间的 ISO 8601 字符串。"""
    return now_utc().isoformat()


def timestamp_now() -> int:
    """返回当前 Unix 时间戳（秒）。"""
    return int(time.time())


def timestamp_ms_now() -> int:
    """返回当前 Unix 时间戳（毫秒）。"""
    return int(time.time() * 1000)


def format_timestamp(ts: int, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化 Unix 时间戳。"""
    return datetime.fromtimestamp(ts).strftime(fmt)


def time_ago(dt: datetime) -> str:
    """返回相对时间描述（如"3 分钟前"）。

    Args:
        dt: 过去的时间点。

    Returns:
        相对时间字符串。
    """
    if dt is None:
        return ""
    now = now_local()
    if dt.tzinfo:
        now = now_utc()
    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 0:
        return "未来"
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{int(seconds // 60)} 分钟前"
    if seconds < 86400:
        return f"{int(seconds // 3600)} 小时前"
    if seconds < 2592000:
        return f"{int(seconds // 86400)} 天前"
    if seconds < 31536000:
        return f"{int(seconds // 2592000)} 个月前"
    return f"{int(seconds // 31536000)} 年前"


def days_between(start: date, end: date) -> int:
    """计算两个日期间的天数。"""
    return (end - start).days


def add_days(d: date, days: int) -> date:
    """日期加天数。"""
    return d + timedelta(days=days)


def is_weekend(d: date) -> bool:
    """判断是否为周末。"""
    return d.weekday() >= 5


def start_of_day(dt: datetime) -> datetime:
    """返回当天的开始（00:00:00）。"""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime) -> datetime:
    """返回当天的结束（23:59:59.999999）。"""
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


# ===== ID 生成 =====


def generate_uuid() -> str:
    """生成 UUID v4 字符串。"""
    return str(uuid.uuid4())


def generate_short_id(length: int = 8) -> str:
    """生成短 ID（URL 安全）。

    Args:
        length: ID 长度。

    Returns:
        短 ID 字符串。
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_numeric_id(length: int = 6) -> str:
    """生成数字 ID。"""
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_request_id() -> str:
    """生成请求 ID（用于日志追踪）。"""
    return f"req-{generate_short_id(12)}"


def generate_session_id() -> str:
    """生成会话 ID。"""
    return f"sess-{generate_uuid()}"


def generate_task_id() -> str:
    """生成任务 ID。"""
    return f"task-{generate_short_id(16)}"


def generate_correlation_id() -> str:
    """生成关联 ID（用于分布式追踪）。"""
    return f"corr-{uuid.uuid4().hex[:16]}"


def generate_token(length: int = 32) -> str:
    """生成随机令牌（URL 安全）。"""
    return secrets.token_urlsafe(length)


def generate_api_key(prefix: str = "sk") -> str:
    """生成 API 密钥。"""
    return f"{prefix}-{secrets.token_urlsafe(32)}"


# ===== 哈希函数 =====


def md5_hash(text: str) -> str:
    """计算 MD5 哈希。"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def sha1_hash(text: str) -> str:
    """计算 SHA1 哈希。"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def sha256_hash(text: str) -> str:
    """计算 SHA256 哈希。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha512_hash(text: str) -> str:
    """计算 SHA512 哈希。"""
    return hashlib.sha512(text.encode("utf-8")).hexdigest()


def hash_with_algorithm(text: str, algorithm: str = "sha256") -> str:
    """使用指定算法计算哈希。

    Args:
        text: 原始文本。
        algorithm: 哈希算法（md5/sha1/sha256/sha512）。

    Returns:
        哈希十六进制字符串。
    """
    algorithms = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }
    hasher = algorithms.get(algorithm.lower())
    if hasher is None:
        raise ValueError(f"不支持的哈希算法: {algorithm}")
    return hasher(text.encode("utf-8")).hexdigest()


def hash_file(filepath: str, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """计算文件哈希。

    Args:
        filepath: 文件路径。
        algorithm: 哈希算法。
        chunk_size: 读取块大小。

    Returns:
        文件哈希十六进制字符串。
    """
    algorithms = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }
    hasher = algorithms.get(algorithm.lower())
    if hasher is None:
        raise ValueError(f"不支持的哈希算法: {algorithm}")
    h = hasher()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def content_hash(content: Any, algorithm: str = "sha256") -> str:
    """计算任意内容的哈希（先序列化为 JSON）。

    Args:
        content: 任意可序列化内容。
        algorithm: 哈希算法。

    Returns:
        内容哈希十六进制字符串。
    """
    serialized = json.dumps(content, sort_keys=True, ensure_ascii=False, default=str)
    return hash_with_algorithm(serialized, algorithm)


def cache_key_hash(*args, **kwargs) -> str:
    """生成缓存键哈希。

    将参数序列化后取哈希，用作缓存键。

    Args:
        *args: 位置参数。
        **kwargs: 关键字参数。

    Returns:
        缓存键哈希字符串。
    """
    key_data = {"args": args, "kwargs": kwargs}
    serialized = json.dumps(key_data, sort_keys=True, ensure_ascii=False, default=str)
    return sha256_hash(serialized)[:32]


# ===== 文件操作 =====


def ensure_dir(path: str) -> Path:
    """确保目录存在，不存在则创建。

    Args:
        path: 目录路径。

    Returns:
        Path 对象。
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_read_file(filepath: str, encoding: str = "utf-8") -> Optional[str]:
    """安全读取文件内容。

    Args:
        filepath: 文件路径。
        encoding: 文件编码。

    Returns:
        文件内容字符串，文件不存在返回 None。
    """
    try:
        with open(filepath, "r", encoding=encoding) as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return None


def safe_write_file(filepath: str, content: str, encoding: str = "utf-8") -> bool:
    """安全写入文件内容。

    Args:
        filepath: 文件路径。
        content: 文件内容。
        encoding: 文件编码。

    Returns:
        成功返回 True。
    """
    try:
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding=encoding) as f:
            f.write(content)
        return True
    except IOError:
        return False


def safe_read_json(filepath: str) -> Optional[Any]:
    """安全读取 JSON 文件。"""
    content = safe_read_file(filepath)
    if content is None:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def safe_write_json(filepath: str, data: Any, indent: int = 2, ensure_ascii: bool = False) -> bool:
    """安全写入 JSON 文件。"""
    try:
        content = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, default=str)
        return safe_write_file(filepath, content)
    except (TypeError, ValueError):
        return False


def file_size(filepath: str) -> int:
    """获取文件大小（字节）。"""
    try:
        return os.path.getsize(filepath)
    except OSError:
        return 0


def file_size_human(filepath: str) -> str:
    """获取文件大小的可读字符串。"""
    size = file_size(filepath)
    return format_file_size(size)


def format_file_size(size: int) -> str:
    """格式化文件大小为可读字符串。

    Args:
        size: 文件大小（字节）。

    Returns:
        可读字符串（如 "1.5 MB"）。
    """
    if size < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


def list_files(directory: str, pattern: str = "*", recursive: bool = False) -> list:
    """列出目录中的文件。

    Args:
        directory: 目录路径。
        pattern: 文件名匹配模式。
        recursive: 是否递归。

    Returns:
        文件路径列表。
    """
    p = Path(directory)
    if not p.exists():
        return []
    if recursive:
        return [str(f) for f in p.rglob(pattern) if f.is_file()]
    return [str(f) for f in p.glob(pattern) if f.is_file()]


def delete_file(filepath: str) -> bool:
    """删除文件。"""
    try:
        os.remove(filepath)
        return True
    except OSError:
        return False


def copy_file(src: str, dst: str) -> bool:
    """复制文件。"""
    import shutil
    try:
        shutil.copy2(src, dst)
        return True
    except (OSError, shutil.Error):
        return False


def move_file(src: str, dst: str) -> bool:
    """移动文件。"""
    import shutil
    try:
        shutil.move(src, dst)
        return True
    except (OSError, shutil.Error):
        return False


def file_exists(filepath: str) -> bool:
    """判断文件是否存在。"""
    return os.path.isfile(filepath)


def dir_exists(path: str) -> bool:
    """判断目录是否存在。"""
    return os.path.isdir(path)


def get_file_extension(filepath: str) -> str:
    """获取文件扩展名（不含点）。"""
    return Path(filepath).suffix.lstrip(".").lower()


def get_filename(filepath: str) -> str:
    """获取文件名（含扩展名）。"""
    return Path(filepath).name


def get_filename_without_ext(filepath: str) -> str:
    """获取文件名（不含扩展名）。"""
    return Path(filepath).stem


# ===== JSON 工具 =====


def safe_json_dumps(data: Any, indent: Optional[int] = None, ensure_ascii: bool = False) -> str:
    """安全 JSON 序列化。

    处理不可序列化的对象（如 datetime）。
    """
    def default(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    return json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, default=default)


def safe_json_loads(text: str, default: Any = None) -> Any:
    """安全 JSON 反序列化。

    Args:
        text: JSON 字符串。
        default: 解析失败返回的默认值。

    Returns:
        解析后的对象，失败返回 default。
    """
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def merge_dicts(*dicts: dict, deep: bool = True) -> dict:
    """合并多个字典。

    Args:
        *dicts: 待合并的字典。
        deep: 是否深度合并。

    Returns:
        合并后的新字典。
    """
    result: dict = {}
    for d in dicts:
        if not isinstance(d, dict):
            continue
        if deep:
            for key, value in d.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dicts(result[key], value, deep=True)
                else:
                    result[key] = value
        else:
            result.update(d)
    return result


def deep_get(data: dict, keys: str, default: Any = None, separator: str = ".") -> Any:
    """深度获取嵌套字典的值。

    Args:
        data: 字典数据。
        keys: 键路径（如 "a.b.c"）。
        default: 默认值。
        separator: 路径分隔符。

    Returns:
        值，不存在返回 default。
    """
    if not data or not keys:
        return default
    current = data
    for key in keys.split(separator):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def deep_set(data: dict, keys: str, value: Any, separator: str = ".") -> dict:
    """深度设置嵌套字典的值。"""
    if not data:
        data = {}
    if not keys:
        return data
    current = data
    key_list = keys.split(separator)
    for key in key_list[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[key_list[-1]] = value
    return data


def flatten_dict(data: dict, separator: str = ".", prefix: str = "") -> dict:
    """扁平化嵌套字典。

    Args:
        data: 嵌套字典。
        separator: 键分隔符。
        prefix: 键前缀。

    Returns:
        扁平化后的字典。
    """
    result = {}
    for key, value in data.items():
        full_key = f"{prefix}{separator}{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten_dict(value, separator, full_key))
        else:
            result[full_key] = value
    return result


def unflatten_dict(data: dict, separator: str = ".") -> dict:
    """反扁平化字典（将扁平键还原为嵌套结构）。"""
    result: dict = {}
    for key, value in data.items():
        deep_set(result, key, value, separator)
    return result


def remove_none_values(data: dict) -> dict:
    """移除字典中值为 None 的键。"""
    return {k: v for k, v in data.items() if v is not None}


def remove_empty_values(data: dict) -> dict:
    """移除字典中空值的键（None / 空字符串 / 空列表 / 空字典）。"""
    return {
        k: v for k, v in data.items()
        if v is not None and v != "" and v != [] and v != {}
    }


# ===== 异步辅助 =====


async def gather_with_limit(coroutines: list, limit: int = 10) -> list:
    """并发执行协程，限制最大并发数。

    Args:
        coroutines: 协程列表。
        limit: 最大并发数。

    Returns:
        结果列表（顺序与输入一致）。
    """
    semaphore = asyncio.Semaphore(limit)

    async def _run(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*[_run(c) for c in coroutines])


async def run_with_timeout(coro: Awaitable, timeout: float, default: Any = None) -> Any:
    """带超时执行协程。

    Args:
        coro: 协程。
        timeout: 超时秒数。
        default: 超时返回的默认值。

    Returns:
        协程结果，超时返回 default。
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return default


async def retry_async(
    func: Callable,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Any:
    """异步重试。

    Args:
        func: 返回协程的可调用对象。
        max_retries: 最大重试次数。
        delay: 初始延迟秒数。
        backoff: 退避倍数。
        exceptions: 触发重试的异常类型。

    Returns:
        函数返回值。

    Raises:
        最后一次重试仍失败时抛出异常。
    """
    last_exception = None
    current_delay = delay
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                await asyncio.sleep(current_delay)
                current_delay *= backoff
    raise last_exception


async def run_in_executor(func: Callable, *args, **kwargs) -> Any:
    """在线程池中运行同步函数。"""
    loop = asyncio.get_event_loop()
    if kwargs:
        from functools import partial
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))
    return await loop.run_in_executor(None, func, *args)


# ===== 类型转换 =====


def to_int(value: Any, default: int = 0) -> int:
    """安全转换为整数。"""
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (ValueError, TypeError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    """安全转换为浮点数。"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def to_str(value: Any, default: str = "") -> str:
    """安全转换为字符串。"""
    if value is None:
        return default
    return str(value)


def to_bool(value: Any, default: bool = False) -> bool:
    """安全转换为布尔值。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return default


def to_list(value: Any, default: Optional[list] = None) -> list:
    """安全转换为列表。"""
    if value is None:
        return default or []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str):
        return [value]
    return [value]


def to_dict(value: Any, default: Optional[dict] = None) -> dict:
    """安全转换为字典。"""
    if value is None:
        return default or {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = safe_json_loads(value)
        if isinstance(parsed, dict):
            return parsed
    return default or {}


# ===== 集合工具 =====


def chunk_list(items: list, chunk_size: int) -> list:
    """将列表分块。

    Args:
        items: 原始列表。
        chunk_size: 每块大小。

    Returns:
        分块后的列表（列表的列表）。
    """
    if chunk_size <= 0:
        return [items]
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def flatten_list(nested: list) -> list:
    """扁平化嵌套列表（一层）。"""
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result


def deep_flatten(nested: list) -> list:
    """深度扁平化嵌套列表。"""
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(deep_flatten(item))
        else:
            result.append(item)
    return result


def unique_list(items: list, key: Optional[Callable] = None) -> list:
    """列表去重（保持顺序）。

    Args:
        items: 原始列表。
        key: 可选，用于判断唯一性的键函数。

    Returns:
        去重后的列表。
    """
    seen = set()
    result = []
    for item in items:
        k = key(item) if key else item
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


def group_by(items: list, key: Callable) -> dict:
    """按键分组。"""
    result: dict = {}
    for item in items:
        k = key(item)
        if k not in result:
            result[k] = []
        result[k].append(item)
    return result


def partition(items: list, predicate: Callable) -> tuple:
    """按条件分区为两个列表。

    Args:
        items: 原始列表。
        predicate: 谓词函数。

    Returns:
        (满足条件的列表, 不满足条件的列表)
    """
    truthy = []
    falsy = []
    for item in items:
        if predicate(item):
            truthy.append(item)
        else:
            falsy.append(item)
    return truthy, falsy


# ===== 数学工具 =====


def clamp(value: Union[int, float], min_value: Union[int, float], max_value: Union[int, float]) -> Union[int, float]:
    """将值限制在范围内。"""
    return max(min_value, min(max_value, value))


def percentage(part: float, total: float, decimals: int = 1) -> float:
    """计算百分比。"""
    if total == 0:
        return 0.0
    return round((part / total) * 100, decimals)


def average(values: list) -> float:
    """计算平均值。"""
    if not values:
        return 0.0
    return sum(values) / len(values)


def median(values: list) -> float:
    """计算中位数。"""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_values[mid - 1] + sorted_values[mid]) / 2
    return sorted_values[mid]


def round_up(value: float, decimals: int = 0) -> float:
    """向上取整。"""
    import math
    multiplier = 10 ** decimals
    return math.ceil(value * multiplier) / multiplier


def round_down(value: float, decimals: int = 0) -> float:
    """向下取整。"""
    import math
    multiplier = 10 ** decimals
    return math.floor(value * multiplier) / multiplier


# ===== 环境工具 =====


def is_windows() -> bool:
    """判断是否为 Windows 系统。"""
    return sys.platform.startswith("win")


def is_linux() -> bool:
    """判断是否为 Linux 系统。"""
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    """判断是否为 macOS 系统。"""
    return sys.platform == "darwin"


def get_env(key: str, default: str = "", required: bool = False) -> str:
    """获取环境变量。

    Args:
        key: 环境变量名。
        default: 默认值。
        required: 是否必填（为 True 且未设置时抛出异常）。

    Returns:
        环境变量值。

    Raises:
        ValueError: required=True 且环境变量未设置。
    """
    value = os.environ.get(key, default)
    if required and not value:
        raise ValueError(f"环境变量 {key} 未设置")
    return value


def get_env_int(key: str, default: int = 0) -> int:
    """获取整数型环境变量。"""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_float(key: str, default: float = 0.0) -> float:
    """获取浮点型环境变量。"""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def get_env_bool(key: str, default: bool = False) -> bool:
    """获取布尔型环境变量。"""
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


def get_env_list(key: str, separator: str = ",", default: Optional[list] = None) -> list:
    """获取列表型环境变量。"""
    value = os.environ.get(key)
    if value is None:
        return default or []
    return [item.strip() for item in value.split(separator) if item.strip()]


# ===== 装饰器 =====


def memoize(func: Callable) -> Callable:
    """记忆化装饰器（缓存函数结果）。

    基于参数哈希缓存，适用于纯函数。
    """
    cache: dict = {}

    def wrapper(*args, **kwargs):
        key = cache_key_hash(*args, **kwargs)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    wrapper.__wrapped__ = func
    wrapper._cache = cache
    return wrapper


def retry(func: Callable, max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: tuple = (Exception,)) -> Callable:
    """同步重试装饰器。"""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        last_exception = None
        current_delay = delay
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt < max_retries:
                    import time as _time
                    _time.sleep(current_delay)
                    current_delay *= backoff
        raise last_exception

    return wrapper


def timed(func: Callable) -> Callable:
    """计时装饰器（记录函数执行耗时）。"""
    import functools
    import logging

    logger = logging.getLogger(func.__module__)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000
            logger.debug(f"{func.__qualname__} 执行耗时: {elapsed:.2f}ms")
            return result
        except Exception:
            elapsed = (time.time() - start) * 1000
            logger.debug(f"{func.__qualname__} 失败耗时: {elapsed:.2f}ms")
            raise

    return wrapper


# ===== 编码工具 =====


def encode_base64(text: str, encoding: str = "utf-8") -> str:
    """Base64 编码。"""
    import base64
    return base64.b64encode(text.encode(encoding)).decode("ascii")


def decode_base64(text: str, encoding: str = "utf-8") -> str:
    """Base64 解码。"""
    import base64
    return base64.b64decode(text.encode("ascii")).decode(encoding)


def encode_url(text: str) -> str:
    """URL 编码。"""
    import urllib.parse
    return urllib.parse.quote(text, safe="")


def decode_url(text: str) -> str:
    """URL 解码。"""
    import urllib.parse
    return urllib.parse.unquote(text)


# ===== 调试工具 =====


def pretty_print(data: Any, indent: int = 2) -> str:
    """美化打印数据结构。"""
    return safe_json_dumps(data, indent=indent, ensure_ascii=False)


def debug_print(label: str, data: Any) -> None:
    """调试打印（带标签）。"""
    print(f"=== {label} ===")
    print(pretty_print(data))
    print("=" * (len(label) + 8))


def get_object_size(obj: Any) -> int:
    """获取对象内存大小（字节）。"""
    import sys
    return sys.getsizeof(obj)


def class_name(obj: Any) -> str:
    """获取对象的类名。"""
    return type(obj).__name__


def method_exists(obj: Any, method_name: str) -> bool:
    """检查对象是否有指定方法。"""
    return hasattr(obj, method_name) and callable(getattr(obj, method_name, None))


def safe_call(func: Callable, *args, default: Any = None, **kwargs) -> Any:
    """安全调用函数（捕获异常返回默认值）。"""
    try:
        return func(*args, **kwargs)
    except Exception:
        return default


def safe_getattr(obj: Any, attr: str, default: Any = None) -> Any:
    """安全获取属性。"""
    return getattr(obj, attr, default)
