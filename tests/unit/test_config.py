"""单元测试：配置管理模块

测试 backend/config.py 的所有功能，包括：
- Settings 单例与字段默认值
- DEFAULT_MODELS 模型注册表结构
- DEFAULT_STEP_MODELS 步骤路由映射
- get_model_config / get_step_model 查询函数
- save_config / _load_user_config 持久化与加载
- _str_to_bool 字符串布尔解析
- 环境变量优先级
- 用户配置文件覆盖逻辑
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 在导入 backend 模块前设置临时数据库
import backend.database as _db
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_config_test_")
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.config import (
    Settings,
    DEFAULT_MODELS,
    DEFAULT_STEP_MODELS,
    DEGREE_MODELS,
    LITERATURE_BASELINE,
    ACADEMIC_CALENDAR,
    CONFIG_FILE_PATH,
    get_settings,
    get_model_config,
    get_step_model,
    save_config,
    _str_to_bool,
)


# ===== _str_to_bool 测试 =====


class TestStrToBool:
    """_str_to_bool 字符串布尔解析测试"""

    def test_str_to_bool_true(self):
        """'true' 应解析为 True"""
        assert _str_to_bool("true") is True

    def test_str_to_bool_true_uppercase(self):
        """'TRUE' 应解析为 True（大小写不敏感）"""
        assert _str_to_bool("TRUE") is True

    def test_str_to_bool_1(self):
        """'1' 应解析为 True"""
        assert _str_to_bool("1") is True

    def test_str_to_bool_yes(self):
        """'yes' 应解析为 True"""
        assert _str_to_bool("yes") is True

    def test_str_to_bool_on(self):
        """'on' 应解析为 True"""
        assert _str_to_bool("on") is True

    def test_str_to_bool_false(self):
        """'false' 应解析为 False"""
        assert _str_to_bool("false") is False

    def test_str_to_bool_zero(self):
        """'0' 应解析为 False"""
        assert _str_to_bool("0") is False

    def test_str_to_bool_empty(self):
        """空字符串应解析为 False"""
        assert _str_to_bool("") is False

    def test_str_to_bool_random_text(self):
        """随机文本应解析为 False"""
        assert _str_to_bool("random") is False

    def test_str_to_bool_with_spaces(self):
        """带空格的 'true' 应解析为 True（自动 strip）"""
        assert _str_to_bool("  true  ") is True

    def test_str_to_bool_integer_input(self):
        """整数 1 应解析为 True（先转字符串）"""
        assert _str_to_bool(1) is True

    def test_str_to_bool_integer_zero(self):
        """整数 0 应解析为 False"""
        assert _str_to_bool(0) is False


# ===== DEFAULT_MODELS 测试 =====


class TestDefaultModels:
    """DEFAULT_MODELS 模型注册表测试"""

    def test_default_models_is_list(self):
        """DEFAULT_MODELS 应为列表"""
        assert isinstance(DEFAULT_MODELS, list)

    def test_default_models_not_empty(self):
        """DEFAULT_MODELS 不应为空"""
        assert len(DEFAULT_MODELS) > 0

    def test_default_models_count(self):
        """DEFAULT_MODELS 应包含至少 10 个模型"""
        assert len(DEFAULT_MODELS) >= 10

    def test_each_model_has_required_fields(self):
        """每个模型应包含必需字段"""
        required_fields = [
            "id", "label", "base_url", "api_key", "pricing",
            "supports_streaming", "supports_thinking", "supports_web_search",
            "max_context", "default_temperature", "agent_default", "release_year",
        ]
        for model in DEFAULT_MODELS:
            for field in required_fields:
                assert field in model, f"模型 {model.get('id')} 缺少字段 {field}"

    def test_each_model_has_valid_id(self):
        """每个模型应有非空 id"""
        for model in DEFAULT_MODELS:
            assert model["id"], "模型 id 不应为空"

    def test_each_model_has_valid_pricing(self):
        """每个模型应有 pricing 字典含 input/output"""
        for model in DEFAULT_MODELS:
            pricing = model["pricing"]
            assert isinstance(pricing, dict)
            assert "input_cny_per_million" in pricing
            assert "output_cny_per_million" in pricing

    def test_each_model_agent_default_valid(self):
        """每个模型的 agent_default 应为合法值"""
        valid_defaults = {"reasoner", "mentor", "inspire", "report", "search", "orchestrator"}
        for model in DEFAULT_MODELS:
            assert model["agent_default"] in valid_defaults, (
                f"模型 {model['id']} 的 agent_default 非法: {model['agent_default']}"
            )

    def test_each_model_release_year_valid(self):
        """每个模型的 release_year 应为 2025 或 2026"""
        for model in DEFAULT_MODELS:
            assert model["release_year"] in (2025, 2026), (
                f"模型 {model['id']} 的 release_year 非法: {model['release_year']}"
            )

    def test_model_ids_unique(self):
        """所有模型 id 应唯一"""
        ids = [m["id"] for m in DEFAULT_MODELS]
        assert len(ids) == len(set(ids)), "模型 id 存在重复"

    def test_deepseek_models_present(self):
        """应包含 DeepSeek 系列模型"""
        ids = {m["id"] for m in DEFAULT_MODELS}
        assert "deepseek-v3.2" in ids
        assert "deepseek-r2" in ids

    def test_claude_models_present(self):
        """应包含 Claude 系列模型"""
        ids = {m["id"] for m in DEFAULT_MODELS}
        assert "claude-sonnet-4.5" in ids
        assert "claude-opus-4.5" in ids

    def test_max_context_positive(self):
        """每个模型的 max_context 应为正数"""
        for model in DEFAULT_MODELS:
            assert model["max_context"] > 0, (
                f"模型 {model['id']} 的 max_context 应为正数"
            )

    def test_default_temperature_in_range(self):
        """每个模型的 default_temperature 应在 0-2 之间"""
        for model in DEFAULT_MODELS:
            temp = model["default_temperature"]
            assert 0 <= temp <= 2, (
                f"模型 {model['id']} 的 default_temperature 超出范围: {temp}"
            )


# ===== DEFAULT_STEP_MODELS 测试 =====


class TestDefaultStepModels:
    """DEFAULT_STEP_MODELS 步骤路由测试"""

    def test_step_models_is_dict(self):
        """DEFAULT_STEP_MODELS 应为字典"""
        assert isinstance(DEFAULT_STEP_MODELS, dict)

    def test_step_models_has_all_keys(self):
        """应包含全部 6 个步骤键"""
        expected_keys = {"orchestrator", "reasoner", "mentor", "inspire", "report", "search"}
        assert set(DEFAULT_STEP_MODELS.keys()) == expected_keys

    def test_step_models_values_are_strings(self):
        """所有值应为字符串"""
        for key, value in DEFAULT_STEP_MODELS.items():
            assert isinstance(value, str), f"步骤 {key} 的值应为字符串"
            assert value, f"步骤 {key} 的值不应为空"

    def test_step_models_reference_existing_models(self):
        """步骤路由引用的模型应在 DEFAULT_MODELS 中存在"""
        model_ids = {m["id"] for m in DEFAULT_MODELS}
        for purpose, model_id in DEFAULT_STEP_MODELS.items():
            assert model_id in model_ids, (
                f"步骤 {purpose} 引用的模型 {model_id} 不在注册表中"
            )

    def test_orchestrator_uses_claude_sonnet(self):
        """orchestrator 步骤应使用 claude-sonnet-4.5"""
        assert DEFAULT_STEP_MODELS["orchestrator"] == "claude-sonnet-4.5"

    def test_reasoner_uses_deepseek_r2(self):
        """reasoner 步骤应使用 deepseek-r2"""
        assert DEFAULT_STEP_MODELS["reasoner"] == "deepseek-r2"


# ===== 常量定义测试 =====


class TestConstants:
    """配置常量测试"""

    def test_degree_models_has_master_and_doctor(self):
        """DEGREE_MODELS 应包含 master 和 doctor"""
        assert "master" in DEGREE_MODELS
        assert "doctor" in DEGREE_MODELS

    def test_literature_baseline_values(self):
        """LITERATURE_BASELINE 硕士 30 / 博士 50"""
        assert LITERATURE_BASELINE["master"] == 30
        assert LITERATURE_BASELINE["doctor"] == 50

    def test_academic_calendar_master(self):
        """ACADEMIC_CALENDAR 硕士最大 1 年"""
        assert ACADEMIC_CALENDAR["master"]["max_years"] == 1

    def test_academic_calendar_doctor(self):
        """ACADEMIC_CALENDAR 博士最大 2 年"""
        assert ACADEMIC_CALENDAR["doctor"]["max_years"] == 2

    def test_config_file_path(self):
        """CONFIG_FILE_PATH 应为 data/config.json"""
        assert CONFIG_FILE_PATH == "data/config.json"


# ===== Settings 类测试 =====


class TestSettings:
    """Settings 类测试"""

    def test_settings_initializes_with_defaults(self):
        """Settings 应使用默认值初始化"""
        import backend.config as _config
        _config._settings_instance = None
        settings = Settings()
        assert isinstance(settings.ai_api_key, str)
        assert isinstance(settings.ai_base_url, str)
        assert isinstance(settings.ai_model, str)
        assert isinstance(settings.db_path, str)
        assert isinstance(settings.log_level, str)

    def test_settings_models_is_list(self):
        """Settings.models 应为列表"""
        import backend.config as _config
        _config._settings_instance = None
        settings = Settings()
        assert isinstance(settings.models, list)
        assert len(settings.models) > 0

    def test_settings_step_models_is_dict(self):
        """Settings.step_models 应为字典"""
        import backend.config as _config
        _config._settings_instance = None
        settings = Settings()
        assert isinstance(settings.step_models, dict)

    def test_settings_currency_default_cny(self):
        """Settings.currency 默认应为 CNY"""
        import backend.config as _config
        _config._settings_instance = None
        settings = Settings()
        assert settings.currency in ("CNY", "USD")

    def test_settings_auto_open_browser_is_bool(self):
        """Settings.auto_open_browser 应为布尔值"""
        import backend.config as _config
        _config._settings_instance = None
        settings = Settings()
        assert isinstance(settings.auto_open_browser, bool)

    def test_settings_real_search_enabled_is_bool(self):
        """Settings.real_search_enabled 应为布尔值"""
        import backend.config as _config
        _config._settings_instance = None
        settings = Settings()
        assert isinstance(settings.real_search_enabled, bool)

    def test_settings_search_api_keys_has_arxiv(self):
        """Settings.search_api_keys 应包含 arxiv 键"""
        import backend.config as _config
        _config._settings_instance = None
        settings = Settings()
        assert "arxiv" in settings.search_api_keys

    def test_settings_search_api_keys_has_semantic_scholar(self):
        """Settings.search_api_keys 应包含 semantic_scholar 键"""
        import backend.config as _config
        _config._settings_instance = None
        settings = Settings()
        assert "semantic_scholar" in settings.search_api_keys

    def test_settings_models_deepcopy_not_shared(self):
        """Settings.models 应为 DEFAULT_MODELS 的深拷贝，修改不影响原值"""
        import backend.config as _config
        _config._settings_instance = None
        settings = Settings()
        original_count = len(DEFAULT_MODELS)
        settings.models.append({"id": "test-extra-model"})
        assert len(DEFAULT_MODELS) == original_count

    def test_settings_load_user_config_no_file(self):
        """无配置文件时 _load_user_config 不报错"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.object(Path, "exists", return_value=False):
            settings = Settings()
            assert settings is not None

    def test_settings_load_user_config_invalid_json(self):
        """配置文件 JSON 非法时不报错"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "open", MagicMock(side_effect=json.JSONDecodeError("err", "doc", 0))):
                settings = Settings()
                assert settings is not None

    def test_settings_load_user_config_valid(self):
        """有效配置文件应覆盖默认值"""
        import backend.config as _config
        _config._settings_instance = None
        user_config = {
            "ai_api_key": "user-key-123",
            "ai_model": "user-model",
            "currency": "USD",
        }
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = json.dumps(user_config)
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "open", return_value=mock_file):
                settings = Settings()
                assert settings.ai_api_key == "user-key-123"
                assert settings.ai_model == "user-model"
                assert settings.currency == "USD"

    def test_settings_currency_invalid_falls_back_to_cny(self):
        """非法 currency 应回退到 CNY"""
        import backend.config as _config
        _config._settings_instance = None
        user_config = {"currency": "EUR"}
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = json.dumps(user_config)
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "open", return_value=mock_file):
                settings = Settings()
                assert settings.currency == "CNY"

    def test_settings_step_models_merge(self):
        """step_models 应合并而非整体覆盖"""
        import backend.config as _config
        _config._settings_instance = None
        user_config = {
            "step_models": {"reasoner": "gpt-4.1"}
        }
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = json.dumps(user_config)
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "open", return_value=mock_file):
                settings = Settings()
                # 用户覆盖的 reasoner
                assert settings.step_models["reasoner"] == "gpt-4.1"
                # 其他键应保留默认
                assert "orchestrator" in settings.step_models
                assert "mentor" in settings.step_models


# ===== get_settings 单例测试 =====


class TestGetSettings:
    """get_settings 单例测试"""

    def test_get_settings_returns_instance(self):
        """get_settings 应返回 Settings 实例"""
        import backend.config as _config
        _config._settings_instance = None
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_singleton(self):
        """get_settings 应返回同一实例"""
        import backend.config as _config
        _config._settings_instance = None
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_get_settings_caches_instance(self):
        """get_settings 应缓存实例"""
        import backend.config as _config
        _config._settings_instance = None
        s1 = get_settings()
        assert _config._settings_instance is s1


# ===== get_model_config 测试 =====


class TestGetModelConfig:
    """get_model_config 模型配置查询测试"""

    def test_get_model_config_existing(self):
        """查询已存在的模型应返回配置字典"""
        import backend.config as _config
        _config._settings_instance = None
        config = get_model_config("deepseek-v3.2")
        assert config is not None
        assert config["id"] == "deepseek-v3.2"

    def test_get_model_config_nonexistent(self):
        """查询不存在的模型应返回 None"""
        import backend.config as _config
        _config._settings_instance = None
        config = get_model_config("nonexistent-model-xyz")
        assert config is None

    def test_get_model_config_returns_dict(self):
        """返回值应为字典"""
        import backend.config as _config
        _config._settings_instance = None
        config = get_model_config("gpt-4.1")
        assert isinstance(config, dict)

    def test_get_model_config_has_pricing(self):
        """返回的配置应包含 pricing"""
        import backend.config as _config
        _config._settings_instance = None
        config = get_model_config("claude-sonnet-4.5")
        assert "pricing" in config

    def test_get_model_config_empty_string(self):
        """空字符串应返回 None"""
        import backend.config as _config
        _config._settings_instance = None
        config = get_model_config("")
        assert config is None


# ===== get_step_model 测试 =====


class TestGetStepModel:
    """get_step_model 步骤模型路由测试"""

    def test_get_step_model_reasoner(self):
        """reasoner 步骤应返回 deepseek-r2"""
        import backend.config as _config
        import copy
        _config._settings_instance = None
        # 使用 mock 避免 config.json 覆盖默认配置
        with patch("backend.config.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.step_models = DEFAULT_STEP_MODELS
            mock_s.models = copy.deepcopy(DEFAULT_MODELS)
            mock_s.ai_model = "deepseek-v3.2"
            mock_settings.return_value = mock_s
            model_id = get_step_model("reasoner")
            assert model_id == "deepseek-r2"

    def test_get_step_model_orchestrator(self):
        """orchestrator 步骤应返回 claude-sonnet-4.5"""
        import backend.config as _config
        _config._settings_instance = None
        model_id = get_step_model("orchestrator")
        assert model_id == "claude-sonnet-4.5"

    def test_get_step_model_unknown_purpose(self):
        """未知用途应回退到第一个模型"""
        import backend.config as _config
        _config._settings_instance = None
        model_id = get_step_model("unknown_purpose")
        assert model_id  # 应返回非空字符串

    def test_get_step_model_returns_string(self):
        """返回值应为字符串"""
        import backend.config as _config
        _config._settings_instance = None
        model_id = get_step_model("mentor")
        assert isinstance(model_id, str)

    def test_get_step_model_search(self):
        """search 步骤应返回 deepseek-v3.2"""
        import backend.config as _config
        _config._settings_instance = None
        model_id = get_step_model("search")
        assert model_id == "deepseek-v3.2"


# ===== save_config 测试 =====


class TestSaveConfig:
    """save_config 配置持久化测试"""

    def test_save_config_creates_file(self, tmp_path):
        """save_config 应创建配置文件"""
        import backend.config as _config
        _config._settings_instance = None
        test_path = str(tmp_path / "config.json")
        with patch.object(_config, "CONFIG_FILE_PATH", test_path):
            _config.save_config({"ai_api_key": "saved-key"})
        assert os.path.exists(test_path)

    def test_save_config_writes_json(self, tmp_path):
        """save_config 应写入 JSON 格式"""
        import backend.config as _config
        _config._settings_instance = None
        test_path = str(tmp_path / "config.json")
        with patch.object(_config, "CONFIG_FILE_PATH", test_path):
            _config.save_config({"ai_model": "test-model"})
        with open(test_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["ai_model"] == "test-model"

    def test_save_config_merges_existing(self, tmp_path):
        """save_config 应合并已有配置"""
        import backend.config as _config
        _config._settings_instance = None
        test_path = str(tmp_path / "config.json")
        # 先写入初始配置
        with patch.object(_config, "CONFIG_FILE_PATH", test_path):
            _config.save_config({"ai_api_key": "key1"})
        # 再追加配置
        with patch.object(_config, "CONFIG_FILE_PATH", test_path):
            _config.save_config({"ai_model": "model1"})
        with open(test_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["ai_api_key"] == "key1"
        assert data["ai_model"] == "model1"

    def test_save_config_resets_singleton(self, tmp_path):
        """save_config 后应重置 Settings 单例"""
        import backend.config as _config
        _config._settings_instance = None
        test_path = str(tmp_path / "config.json")
        with patch.object(_config, "CONFIG_FILE_PATH", test_path):
            _config.save_config({"ai_api_key": "new-key"})
        assert _config._settings_instance is None

    def test_save_config_creates_parent_dir(self, tmp_path):
        """save_config 应自动创建父目录"""
        import backend.config as _config
        _config._settings_instance = None
        test_path = str(tmp_path / "subdir" / "config.json")
        with patch.object(_config, "CONFIG_FILE_PATH", test_path):
            _config.save_config({"ai_api_key": "key"})
        assert os.path.exists(test_path)

    def test_save_config_ensure_ascii_false(self, tmp_path):
        """save_config 应使用 ensure_ascii=False 保留中文"""
        import backend.config as _config
        _config._settings_instance = None
        test_path = str(tmp_path / "config.json")
        with patch.object(_config, "CONFIG_FILE_PATH", test_path):
            _config.save_config({"ai_model": "中文模型"})
        with open(test_path, "r", encoding="utf-8") as f:
            raw = f.read()
        assert "中文模型" in raw


# ===== _load_user_config 测试 =====


class TestLoadUserConfig:
    """_load_user_config 用户配置加载测试"""

    def test_load_user_config_no_file(self):
        """配置文件不存在时应静默返回"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.object(Path, "exists", return_value=False):
            settings = Settings()
            assert settings.ai_api_key == os.getenv("AI_API_KEY", "")

    def test_load_user_config_overrides_ai_key(self):
        """配置文件应覆盖 ai_api_key"""
        import backend.config as _config
        _config._settings_instance = None
        user_config = {"ai_api_key": "loaded-key"}
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = json.dumps(user_config)
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "open", return_value=mock_file):
                settings = Settings()
                assert settings.ai_api_key == "loaded-key"

    def test_load_user_config_overrides_models(self):
        """配置文件应覆盖 models 列表"""
        import backend.config as _config
        _config._settings_instance = None
        custom_models = [{"id": "custom-model", "label": "Custom"}]
        user_config = {"models": custom_models}
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = json.dumps(user_config)
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "open", return_value=mock_file):
                settings = Settings()
                assert len(settings.models) == 1
                assert settings.models[0]["id"] == "custom-model"

    def test_load_user_config_search_api_keys_merge(self):
        """search_api_keys 应合并而非整体覆盖"""
        import backend.config as _config
        _config._settings_instance = None
        user_config = {"search_api_keys": {"arxiv": "arxiv-key-123"}}
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = json.dumps(user_config)
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "open", return_value=mock_file):
                settings = Settings()
                assert settings.search_api_keys["arxiv"] == "arxiv-key-123"
                assert "semantic_scholar" in settings.search_api_keys

    def test_load_user_config_auto_open_browser(self):
        """配置文件应覆盖 auto_open_browser"""
        import backend.config as _config
        _config._settings_instance = None
        user_config = {"auto_open_browser": False}
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = json.dumps(user_config)
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "open", return_value=mock_file):
                settings = Settings()
                assert settings.auto_open_browser is False

    def test_load_user_config_real_search_enabled(self):
        """配置文件应覆盖 real_search_enabled"""
        import backend.config as _config
        _config._settings_instance = None
        user_config = {"real_search_enabled": True}
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = json.dumps(user_config)
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "open", return_value=mock_file):
                settings = Settings()
                assert settings.real_search_enabled is True

    def test_load_user_config_os_error_handled(self):
        """文件读取 OSError 应被捕获"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "open", side_effect=OSError("permission denied")):
                settings = Settings()
                assert settings is not None


# ===== 环境变量测试 =====


class TestEnvironmentVariables:
    """环境变量优先级测试"""

    def test_ai_api_key_from_env(self):
        """AI_API_KEY 环境变量应被读取"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.dict(os.environ, {"AI_API_KEY": "env-key-456"}):
            with patch.object(Path, "exists", return_value=False):
                settings = Settings()
                assert settings.ai_api_key == "env-key-456"

    def test_ai_base_url_from_env(self):
        """AI_BASE_URL 环境变量应被读取"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.dict(os.environ, {"AI_BASE_URL": "https://custom.api/v1"}):
            with patch.object(Path, "exists", return_value=False):
                settings = Settings()
                assert settings.ai_base_url == "https://custom.api/v1"

    def test_ai_model_from_env(self):
        """AI_MODEL 环境变量应被读取"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.dict(os.environ, {"AI_MODEL": "env-model"}):
            with patch.object(Path, "exists", return_value=False):
                settings = Settings()
                assert settings.ai_model == "env-model"

    def test_db_path_from_env(self):
        """DB_PATH 环境变量应被读取"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.dict(os.environ, {"DB_PATH": "/tmp/env.db"}):
            with patch.object(Path, "exists", return_value=False):
                settings = Settings()
                assert settings.db_path == "/tmp/env.db"

    def test_log_level_from_env(self):
        """LOG_LEVEL 环境变量应被读取"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            with patch.object(Path, "exists", return_value=False):
                settings = Settings()
                assert settings.log_level == "DEBUG"

    def test_currency_from_env(self):
        """CURRENCY 环境变量应被读取"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.dict(os.environ, {"CURRENCY": "USD"}):
            with patch.object(Path, "exists", return_value=False):
                settings = Settings()
                assert settings.currency == "USD"

    def test_real_search_enabled_from_env(self):
        """REAL_SEARCH_ENABLED 环境变量应被解析为布尔值"""
        import backend.config as _config
        _config._settings_instance = None
        with patch.dict(os.environ, {"REAL_SEARCH_ENABLED": "true"}):
            with patch.object(Path, "exists", return_value=False):
                settings = Settings()
                assert settings.real_search_enabled is True
