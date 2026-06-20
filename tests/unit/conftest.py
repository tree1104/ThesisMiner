"""单元测试共享 fixtures

提供临时数据库、模拟配置等共享测试夹具，
确保每个测试文件运行时使用独立的临时数据库，避免污染正式数据。
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ===== 临时数据库夹具 =====
# 在导入 backend.database 之前覆盖 DB_PATH，确保所有测试使用临时数据库

_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_unit_test_")
_TMP_DB = os.path.join(_TMP_DIR, "unit_test.db")


def _setup_temp_db():
    """设置临时数据库路径并初始化。

    在导入 backend.database 模块前调用，覆盖模块级 DB_PATH 常量。
    """
    import backend.database as _db
    _db.DB_PATH = _TMP_DB
    _db.init_db()
    return _TMP_DB


# 尝试设置临时数据库（若 backend.database 已被导入则直接覆盖）
try:
    _setup_temp_db()
except Exception:
    # 若设置失败（如模块尚未导入），在 fixture 中再次尝试
    pass


@pytest.fixture(scope="session", autouse=True)
def _ensure_temp_db():
    """会话级自动夹具：确保整个测试会话使用临时数据库。

    在测试会话开始时设置临时数据库路径，所有测试共享同一个临时数据库文件。
    """
    try:
        _setup_temp_db()
    except Exception:
        pass
    yield


@pytest.fixture
def temp_db_path():
    """返回临时数据库路径。"""
    return _TMP_DB


@pytest.fixture
def reset_settings():
    """重置 Settings 单例，确保测试间配置隔离。"""
    import backend.config as _config
    _config._settings_instance = None
    yield
    _config._settings_instance = None


@pytest.fixture
def mock_api_key():
    """模拟已配置 AI API Key 的环境。"""
    import backend.config as _config
    _config._settings_instance = None
    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("AI_API_KEY", "test-api-key-for-unit-test")
        yield
    _config._settings_instance = None


def make_mock_llm_result(
    content: str = "模拟回复内容",
    model: str = "mock-model",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    cached_tokens: int = 0,
    reasoning_content: str = None,
) -> dict:
    """构造模拟的 call_llm 返回值。

    Args:
        content: 模拟的回复正文。
        model: 模拟的模型名称。
        prompt_tokens: 模拟的输入 token 数。
        completion_tokens: 模拟的输出 token 数。
        cached_tokens: 模拟的缓存命中 token 数。
        reasoning_content: 可选的思维链内容。

    Returns:
        模拟的 call_llm 结果字典。
    """
    result = {
        "content": content,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cached_tokens": cached_tokens,
        "cost": 0.0,
        "citations": [],
    }
    if reasoning_content:
        result["reasoning_content"] = reasoning_content
    return result
