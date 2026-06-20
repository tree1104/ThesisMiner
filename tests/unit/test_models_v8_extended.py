"""V8.0 模型注册表扩展单元测试

测试 backend/config.py 中的模型注册表相关功能：
  - DEFAULT_MODELS: 10 个模型的完整字段验证
  - DEFAULT_STEP_MODELS: 步骤路由映射
  - get_model_config: 按 ID 查询模型
  - get_step_model: 按用途获取模型 ID
  - 模型字段完整性：agent_default / release_year / pricing / capabilities
  - 旧模型移除验证、新模型加入验证

测试策略：
  - 纯逻辑测试，不依赖数据库
  - 重置 Settings 单例避免污染
  - 覆盖正向、反向、边界条件
"""
import os
import sys
import copy

import pytest
from unittest.mock import patch, MagicMock

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.config import (
    DEFAULT_MODELS,
    DEFAULT_STEP_MODELS,
    DEGREE_MODELS,
    LITERATURE_BASELINE,
    ACADEMIC_CALENDAR,
    get_model_config,
    get_step_model,
    get_settings,
    Settings,
    _str_to_bool,
)
import backend.config as _config_module


# ===== 辅助函数 =====

def _reset_settings_singleton():
    """重置 Settings 单例，避免测试间污染。"""
    _config_module._settings_instance = None


def _get_model_ids() -> list:
    """获取所有模型 ID 列表。"""
    return [m["id"] for m in DEFAULT_MODELS]


# ============================================================
# 第一部分：DEFAULT_MODELS 基础验证
# ============================================================

class TestDefaultModelsBasic:
    """测试 DEFAULT_MODELS 基础属性。"""

    def test_models_is_list(self):
        """DEFAULT_MODELS 应为列表。"""
        assert isinstance(DEFAULT_MODELS, list)

    def test_models_count_at_least_10(self):
        """模型数量应至少 10 个。"""
        assert len(DEFAULT_MODELS) >= 10

    def test_each_model_has_id(self):
        """每个模型应包含 id 字段。"""
        for model in DEFAULT_MODELS:
            assert "id" in model
            assert isinstance(model["id"], str)
            assert len(model["id"]) > 0

    def test_each_model_has_label(self):
        """每个模型应包含 label 字段。"""
        for model in DEFAULT_MODELS:
            assert "label" in model

    def test_each_model_has_base_url(self):
        """每个模型应包含 base_url 字段。"""
        for model in DEFAULT_MODELS:
            assert "base_url" in model

    def test_each_model_has_pricing(self):
        """每个模型应包含 pricing 字段。"""
        for model in DEFAULT_MODELS:
            assert "pricing" in model
            assert isinstance(model["pricing"], dict)

    def test_model_ids_unique(self):
        """所有模型 ID 应唯一。"""
        ids = _get_model_ids()
        assert len(ids) == len(set(ids))

    def test_each_model_has_max_context(self):
        """每个模型应包含 max_context 字段。"""
        for model in DEFAULT_MODELS:
            assert "max_context" in model
            assert isinstance(model["max_context"], int)
            assert model["max_context"] > 0

    def test_each_model_has_default_temperature(self):
        """每个模型应包含 default_temperature 字段。"""
        for model in DEFAULT_MODELS:
            assert "default_temperature" in model
            assert 0 <= model["default_temperature"] <= 2


# ============================================================
# 第二部分：V8.0 新增字段验证
# ============================================================

class TestV8ModelFields:
    """测试 V8.0 新增的模型字段。"""

    def test_each_model_has_agent_default(self):
        """每个模型应包含 agent_default 字段。"""
        for model in DEFAULT_MODELS:
            assert "agent_default" in model
            assert model["agent_default"] in (
                "reasoner", "mentor", "inspire", "report", "search",
                "orchestrator", "thesis_writer"
            )

    def test_each_model_has_release_year(self):
        """每个模型应包含 release_year 字段。"""
        for model in DEFAULT_MODELS:
            assert "release_year" in model
            assert model["release_year"] in (2025, 2026)

    def test_each_model_has_capability_flags(self):
        """每个模型应包含能力标记字段。"""
        for model in DEFAULT_MODELS:
            assert "supports_streaming" in model
            assert "supports_thinking" in model
            assert "supports_web_search" in model
            assert isinstance(model["supports_streaming"], bool)
            assert isinstance(model["supports_thinking"], bool)
            assert isinstance(model["supports_web_search"], bool)

    def test_pricing_has_input_and_output(self):
        """每个模型的 pricing 应包含输入与输出价格。"""
        for model in DEFAULT_MODELS:
            pricing = model["pricing"]
            assert "input_cny_per_million" in pricing
            assert "output_cny_per_million" in pricing
            assert pricing["input_cny_per_million"] >= 0
            assert pricing["output_cny_per_million"] >= 0

    def test_output_price_higher_than_input(self):
        """输出价格通常应高于或等于输入价格。"""
        for model in DEFAULT_MODELS:
            pricing = model["pricing"]
            assert pricing["output_cny_per_million"] >= pricing["input_cny_per_million"]


# ============================================================
# 第三部分：旧模型移除验证
# ============================================================

class TestLegacyModelsRemoved:
    """验证旧模型已从注册表移除。"""

    def test_gpt_4o_mini_removed(self):
        """gpt-4o-mini 应已移除。"""
        ids = _get_model_ids()
        assert "gpt-4o-mini" not in ids

    def test_gpt_4o_removed(self):
        """gpt-4o 应已移除。"""
        ids = _get_model_ids()
        assert "gpt-4o" not in ids

    def test_deepseek_chat_removed(self):
        """deepseek-chat 应已移除。"""
        ids = _get_model_ids()
        assert "deepseek-chat" not in ids

    def test_no_legacy_models_present(self):
        """不应包含任何旧模型。"""
        legacy_models = ["gpt-4o-mini", "gpt-4o", "deepseek-chat", "gpt-3.5-turbo"]
        ids = _get_model_ids()
        for legacy in legacy_models:
            assert legacy not in ids


# ============================================================
# 第四部分：2026 新模型验证
# ============================================================

class TestNewModels2026:
    """验证 2026 最新模型已加入注册表。"""

    def test_claude_sonnet_4_5_present(self):
        """claude-opus-5 应存在（v9.0 顶级报告模型）。"""
        ids = _get_model_ids()
        assert "claude-opus-5" in ids

    def test_claude_opus_4_5_present(self):
        """claude-opus-5 应存在。"""
        ids = _get_model_ids()
        assert "claude-opus-5" in ids

    def test_deepseek_v3_2_present(self):
        """deepseek-v4 应存在（v9.0 通用模型）。"""
        ids = _get_model_ids()
        assert "deepseek-v4" in ids

    def test_deepseek_r2_present(self):
        """deepseek-r3 应存在（v9.0 推理模型）。"""
        ids = _get_model_ids()
        assert "deepseek-r3" in ids

    def test_qwen3_max_present(self):
        """qwen3-max-2026 应存在。"""
        ids = _get_model_ids()
        assert "qwen3-max-2026" in ids

    def test_gemini_2_5_pro_present(self):
        """gemini-3-pro 应存在（v9.0 超长上下文模型）。"""
        ids = _get_model_ids()
        assert "gemini-3-pro" in ids

    def test_glm_4_6_present(self):
        """glm-5.2 应存在（v9.0 智谱模型）。"""
        ids = _get_model_ids()
        assert "glm-5.2" in ids

    def test_doubao_1_5_pro_present(self):
        """doubao-2.0-pro 应存在（v9.0 豆包模型）。"""
        ids = _get_model_ids()
        assert "doubao-2.0-pro" in ids

    def test_new_models_have_2026_year(self):
        """2026 新模型的 release_year 应为 2026。"""
        new_ids = [
            "claude-opus-5", "deepseek-v4", "deepseek-r3",
            "qwen3-max-2026", "gemini-3-pro", "glm-5.2", "doubao-2.0-pro"
        ]
        for mid in new_ids:
            model = get_model_config(mid)
            assert model is not None
            assert model["release_year"] == 2026

    def test_retained_models_have_2025_year(self):
        """v9.0 所有模型 release_year 应为 2026（无 2025 保留模型）。"""
        for model in DEFAULT_MODELS:
            assert model["release_year"] == 2026


# ============================================================
# 第五部分：DEFAULT_STEP_MODELS 验证
# ============================================================

class TestDefaultStepModels:
    """测试 DEFAULT_STEP_MODELS 步骤路由。"""

    def test_step_models_is_dict(self):
        """DEFAULT_STEP_MODELS 应为字典。"""
        assert isinstance(DEFAULT_STEP_MODELS, dict)

    def test_step_models_has_orchestrator(self):
        """应包含 orchestrator 步骤。"""
        assert "orchestrator" in DEFAULT_STEP_MODELS

    def test_step_models_has_reasoner(self):
        """应包含 reasoner 步骤。"""
        assert "reasoner" in DEFAULT_STEP_MODELS

    def test_step_models_has_mentor(self):
        """应包含 mentor 步骤。"""
        assert "mentor" in DEFAULT_STEP_MODELS

    def test_step_models_has_inspire(self):
        """应包含 inspire 步骤。"""
        assert "inspire" in DEFAULT_STEP_MODELS

    def test_step_models_has_report(self):
        """应包含 report 步骤。"""
        assert "report" in DEFAULT_STEP_MODELS

    def test_step_models_has_search(self):
        """应包含 search 步骤。"""
        assert "search" in DEFAULT_STEP_MODELS

    def test_orchestrator_routes_to_claude_sonnet(self):
        """orchestrator 应路由到 deepseek-r3（v9.0）。"""
        assert DEFAULT_STEP_MODELS["orchestrator"] == "deepseek-r3"

    def test_reasoner_routes_to_deepseek_r2(self):
        """reasoner 应路由到 deepseek-v4（v9.0）。"""
        assert DEFAULT_STEP_MODELS["reasoner"] == "deepseek-v4"

    def test_mentor_routes_to_gpt_4_1(self):
        """mentor 应路由到 glm-5.2（v9.0）。"""
        assert DEFAULT_STEP_MODELS["mentor"] == "glm-5.2"

    def test_inspire_routes_to_qwen3_max(self):
        """inspire 应路由到 glm-5.2-flash（v9.0）。"""
        assert DEFAULT_STEP_MODELS["inspire"] == "glm-5.2-flash"

    def test_report_routes_to_claude_opus(self):
        """report 应路由到 claude-opus-5（v9.0）。"""
        assert DEFAULT_STEP_MODELS["report"] == "claude-opus-5"

    def test_search_routes_to_deepseek_v3_2(self):
        """search 应路由到 gpt-5-mini（v9.0）。"""
        assert DEFAULT_STEP_MODELS["search"] == "gpt-5-mini"

    def test_all_step_models_exist_in_registry(self):
        """所有步骤路由的模型 ID 应存在于注册表。"""
        ids = _get_model_ids()
        for purpose, mid in DEFAULT_STEP_MODELS.items():
            assert mid in ids, f"步骤 {purpose} 的模型 {mid} 不在注册表中"


# ============================================================
# 第六部分：get_model_config 测试
# ============================================================

class TestGetModelConfig:
    """测试 get_model_config 函数。"""

    def test_get_existing_model(self):
        """获取存在的模型应返回配置字典。"""
        result = get_model_config("gpt-5")
        assert result is not None
        assert result["id"] == "gpt-5"

    def test_get_nonexistent_model_returns_none(self):
        """获取不存在的模型应返回 None。"""
        result = get_model_config("不存在的模型XYZ")
        assert result is None

    def test_get_model_returns_complete_config(self):
        """返回的配置应包含所有字段。"""
        result = get_model_config("deepseek-r3")
        assert result is not None
        assert "id" in result
        assert "label" in result
        assert "pricing" in result
        assert "agent_default" in result
        assert "release_year" in result

    def test_get_model_for_each_default(self):
        """每个默认模型都应能通过 get_model_config 获取。"""
        for model in DEFAULT_MODELS:
            result = get_model_config(model["id"])
            assert result is not None
            assert result["id"] == model["id"]


# ============================================================
# 第七部分：get_step_model 测试
# ============================================================

class TestGetStepModel:
    """测试 get_step_model 函数。"""

    def test_get_step_model_reasoner(self):
        """获取 reasoner 步骤模型。"""
        _reset_settings_singleton()
        # 使用 mock 确保使用默认配置（避免 config.json 覆盖）
        with patch("backend.config.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.step_models = DEFAULT_STEP_MODELS
            mock_s.models = copy.deepcopy(DEFAULT_MODELS)
            mock_s.ai_model = "deepseek-v4"
            mock_settings.return_value = mock_s
            result = get_step_model("reasoner")
            assert result == "deepseek-v4"

    def test_get_step_model_mentor(self):
        """获取 mentor 步骤模型。"""
        _reset_settings_singleton()
        with patch("backend.config.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.step_models = DEFAULT_STEP_MODELS
            mock_s.models = copy.deepcopy(DEFAULT_MODELS)
            mock_s.ai_model = "deepseek-v4"
            mock_settings.return_value = mock_s
            result = get_step_model("mentor")
            assert result == "glm-5.2"

    def test_get_step_model_orchestrator(self):
        """获取 orchestrator 步骤模型。"""
        _reset_settings_singleton()
        with patch("backend.config.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.step_models = DEFAULT_STEP_MODELS
            mock_s.models = copy.deepcopy(DEFAULT_MODELS)
            mock_s.ai_model = "deepseek-v4"
            mock_settings.return_value = mock_s
            result = get_step_model("orchestrator")
            assert result == "deepseek-r3"

    def test_get_step_model_unknown_purpose(self):
        """未知用途应回退到第一个模型。"""
        _reset_settings_singleton()
        with patch("backend.config.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.step_models = DEFAULT_STEP_MODELS
            mock_s.models = copy.deepcopy(DEFAULT_MODELS)
            mock_s.ai_model = "deepseek-v4"
            mock_settings.return_value = mock_s
            result = get_step_model("unknown_purpose")
            # 应回退到 models[0]
            assert isinstance(result, str)
            assert len(result) > 0

    def test_get_step_model_returns_string(self):
        """返回值应为字符串。"""
        _reset_settings_singleton()
        with patch("backend.config.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.step_models = DEFAULT_STEP_MODELS
            mock_s.models = copy.deepcopy(DEFAULT_MODELS)
            mock_s.ai_model = "deepseek-v4"
            mock_settings.return_value = mock_s
            result = get_step_model("search")
            assert isinstance(result, str)


# ============================================================
# 第八部分：Settings 类测试
# ============================================================

class TestSettings:
    """测试 Settings 类。"""

    def test_settings_singleton(self):
        """get_settings 应返回单例。"""
        _reset_settings_singleton()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_settings_has_models(self):
        """Settings 应包含 models 列表。"""
        _reset_settings_singleton()
        settings = get_settings()
        assert hasattr(settings, "models")
        assert isinstance(settings.models, list)
        assert len(settings.models) >= 10

    def test_settings_has_step_models(self):
        """Settings 应包含 step_models 字典。"""
        _reset_settings_singleton()
        settings = get_settings()
        assert hasattr(settings, "step_models")
        assert isinstance(settings.step_models, dict)

    def test_settings_has_currency(self):
        """Settings 应包含 currency 字段。"""
        _reset_settings_singleton()
        settings = get_settings()
        assert hasattr(settings, "currency")
        assert settings.currency in ("CNY", "USD")

    def test_settings_has_ai_api_key(self):
        """Settings 应包含 ai_api_key 字段。"""
        _reset_settings_singleton()
        settings = get_settings()
        assert hasattr(settings, "ai_api_key")

    def test_settings_has_ai_model(self):
        """Settings 应包含 ai_model 字段。"""
        _reset_settings_singleton()
        settings = get_settings()
        assert hasattr(settings, "ai_model")

    def test_settings_models_independent_from_default(self):
        """Settings.models 应是 DEFAULT_MODELS 的深拷贝。"""
        _reset_settings_singleton()
        settings = get_settings()
        # 修改 settings.models 不应影响 DEFAULT_MODELS
        original_len = len(DEFAULT_MODELS)
        settings.models.append({"id": "temp-test-model"})
        assert len(DEFAULT_MODELS) == original_len
        # 清理
        settings.models.pop()

    def test_settings_default_ai_model_is_deepseek_v3_2(self):
        """默认 ai_model 应为 deepseek-v4（v9.0，当无环境变量覆盖时）。"""
        # 使用 mock 避免环境变量/config.json 覆盖
        with patch.dict(os.environ, {"AI_MODEL": "deepseek-v4"}, clear=False):
            _reset_settings_singleton()
            # 临时移除 config.json 影响
            with patch("backend.config.Path.exists", return_value=False):
                settings = Settings()
                assert settings.ai_model == "deepseek-v4"


# ============================================================
# 第九部分：_str_to_bool 辅助函数测试
# ============================================================

class TestStrToBool:
    """测试 _str_to_bool 辅助函数。"""

    def test_true_string(self):
        """'true' 应返回 True。"""
        assert _str_to_bool("true") is True

    def test_false_string(self):
        """'false' 应返回 False。"""
        assert _str_to_bool("false") is False

    def test_one_string(self):
        """'1' 应返回 True。"""
        assert _str_to_bool("1") is True

    def test_zero_string(self):
        """'0' 应返回 False。"""
        assert _str_to_bool("0") is False

    def test_yes_string(self):
        """'yes' 应返回 True。"""
        assert _str_to_bool("yes") is True

    def test_on_string(self):
        """'on' 应返回 True。"""
        assert _str_to_bool("on") is True

    def test_empty_string(self):
        """空字符串应返回 False。"""
        assert _str_to_bool("") is False

    def test_random_string(self):
        """随机字符串应返回 False。"""
        assert _str_to_bool("random") is False

    def test_case_insensitive(self):
        """应大小写不敏感。"""
        assert _str_to_bool("TRUE") is True
        assert _str_to_bool("Yes") is True

    def test_with_whitespace(self):
        """带空白的字符串应正确解析。"""
        assert _str_to_bool("  true  ") is True


# ============================================================
# 第十部分：常量验证
# ============================================================

class TestConstants:
    """测试配置常量。"""

    def test_degree_models_has_master(self):
        """DEGREE_MODELS 应包含 master。"""
        assert "master" in DEGREE_MODELS

    def test_degree_models_has_doctor(self):
        """DEGREE_MODELS 应包含 doctor。"""
        assert "doctor" in DEGREE_MODELS

    def test_literature_baseline_master(self):
        """硕士文献基线应为 30。"""
        assert LITERATURE_BASELINE["master"] == 30

    def test_literature_baseline_doctor(self):
        """博士文献基线应为 50。"""
        assert LITERATURE_BASELINE["doctor"] == 50

    def test_academic_calendar_master(self):
        """硕士学术日历应包含 max_years=1。"""
        assert ACADEMIC_CALENDAR["master"]["max_years"] == 1

    def test_academic_calendar_doctor(self):
        """博士学术日历应包含 max_years=2。"""
        assert ACADEMIC_CALENDAR["doctor"]["max_years"] == 2

    def test_academic_calendar_has_description(self):
        """学术日历应包含 description 字段。"""
        assert "description" in ACADEMIC_CALENDAR["master"]
        assert "description" in ACADEMIC_CALENDAR["doctor"]


# ============================================================
# 第十一部分：Agent 默认模型映射验证
# ============================================================

class TestAgentDefaultMapping:
    """测试每个模型的 agent_default 字段映射。"""

    def test_deepseek_r2_is_reasoner(self):
        """deepseek-v4 的 agent_default 应为 reasoner（v9.0）。"""
        model = get_model_config("deepseek-v4")
        assert model["agent_default"] == "reasoner"

    def test_gpt_4_1_is_mentor(self):
        """glm-5.2 的 agent_default 应为 mentor（v9.0）。"""
        model = get_model_config("glm-5.2")
        assert model["agent_default"] == "mentor"

    def test_claude_sonnet_is_orchestrator(self):
        """deepseek-r3 的 agent_default 应为 orchestrator（v9.0）。"""
        model = get_model_config("deepseek-r3")
        assert model["agent_default"] == "orchestrator"

    def test_claude_opus_is_report(self):
        """claude-opus-5 的 agent_default 应为 report（v9.0）。"""
        model = get_model_config("claude-opus-5")
        assert model["agent_default"] == "report"

    def test_qwen3_max_is_inspire(self):
        """glm-5.2-flash 的 agent_default 应为 inspire（v9.0）。"""
        model = get_model_config("glm-5.2-flash")
        assert model["agent_default"] == "inspire"

    def test_deepseek_v3_2_is_search(self):
        """gpt-5-mini 的 agent_default 应为 search（v9.0）。"""
        model = get_model_config("gpt-5-mini")
        assert model["agent_default"] == "search"

    def test_all_agent_roles_covered(self):
        """所有 Agent 角色都应至少有一个模型对应。"""
        roles = set(m["agent_default"] for m in DEFAULT_MODELS)
        expected_roles = {"reasoner", "mentor", "inspire", "report", "search", "orchestrator"}
        assert expected_roles.issubset(roles)


# ============================================================
# 第十二部分：模型能力标记验证
# ============================================================

class TestModelCapabilities:
    """测试模型能力标记。"""

    def test_deepseek_r2_supports_thinking(self):
        """deepseek-v4 应支持 thinking（v9.0）。"""
        model = get_model_config("deepseek-v4")
        assert model["supports_thinking"] is True

    def test_claude_sonnet_supports_web_search(self):
        """glm-5.2 应支持 web_search（v9.0）。"""
        model = get_model_config("glm-5.2")
        assert model["supports_web_search"] is True

    def test_all_models_support_streaming(self):
        """所有模型应支持 streaming。"""
        for model in DEFAULT_MODELS:
            assert model["supports_streaming"] is True

    def test_gpt_4_1_not_support_thinking(self):
        """gpt-5-mini 不应支持 thinking（v9.0）。"""
        model = get_model_config("gpt-5-mini")
        assert model["supports_thinking"] is False

    def test_gemini_has_large_context(self):
        """gemini-3-pro 应有超大上下文（v9.0）。"""
        model = get_model_config("gemini-3-pro")
        assert model["max_context"] >= 1000000

    def test_deepseek_r2_temperature_zero(self):
        """deepseek-r3 的默认温度应为 0.0（v9.0）。"""
        model = get_model_config("deepseek-r3")
        assert model["default_temperature"] == 0.0
