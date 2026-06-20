"""Task 3 测试：验证 v9.0 模型注册表更新（2026.06 最新批次）

验证：
- 旧 2025 模型及旧 2026 模型已全部移除（deepseek-chat-v3 / gpt-4.1 / claude-sonnet-4.5 等）
- 2026.06 最新批次模型已加入（deepseek-v4 / glm-5.2 / gpt-5 / claude-opus-5 等）
- 每个模型含 capabilities 字段（deep_thinking / web_search / streaming）
- 每个模型含 agent_default 与 release_year=2026
- DEFAULT_STEP_MODELS 包含 thesis_writer 角色（v9.0 新增）
- 定价为 CNY 格式（pricing 含 input / cached_input / output）
"""
import os
import sys
import copy

import pytest
from unittest.mock import patch, MagicMock

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.config import (
    DEFAULT_MODELS,
    DEFAULT_STEP_MODELS,
    APP_VERSION,
    APP_TITLE,
    get_model_config,
    get_step_model,
    get_settings,
)
import backend.config as _config_module


# ===== 常量定义 =====

# 旧模型 ID 黑名单（应已全部移除）
# 包含 2025 批次与旧 2026 批次
OLD_MODEL_IDS = {
    # 2025 批次
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-3.5-turbo",
    "deepseek-chat",
    "deepseek-reasoner",
    "deepseek-chat-v3",
    "qwen-plus",
    "qwen-max",
    # 旧 2026 批次
    "deepseek-v3.2",
    "deepseek-r2",
    "claude-sonnet-4.5",
    "claude-opus-4.5",
    "qwen3-max",
    "gemini-2.5-pro",
    "glm-4.6",
    "doubao-1.5-pro",
}

# 2026.06 新模型 ID 白名单（应已加入）
NEW_MODEL_IDS = {
    "deepseek-v4",
    "deepseek-r3",
    "glm-5.2",
    "glm-5.2-flash",
    "gpt-5",
    "gpt-5-mini",
    "claude-opus-5",
    "qwen3-max-2026",
    "gemini-3-pro",
    "doubao-2.0-pro",
}

# 合法的 provider 集合
VALID_PROVIDERS = {"deepseek", "zhipu", "openai", "anthropic", "qwen", "google", "bytecode"}

# 合法的 agent_default 角色集合（v9.0 新增 thesis_writer）
VALID_AGENT_ROLES = {
    "orchestrator",
    "reasoner",
    "mentor",
    "inspire",
    "report",
    "search",
    "thesis_writer",
}

# capabilities 必填的三个布尔键
CAPABILITY_KEYS = ("deep_thinking", "web_search", "streaming")

# pricing 必填的三个 CNY 键
PRICING_CNY_KEYS = ("input", "cached_input", "output")


# ===== 辅助函数 =====

def _reset_settings_singleton():
    """重置 Settings 单例，避免测试间污染。"""
    _config_module._settings_instance = None


def _get_model_ids():
    """获取所有模型 ID 集合。"""
    return {m["id"] for m in DEFAULT_MODELS}


# ============================================================
# 第一部分：版本号验证
# ============================================================

class TestAppVersion:
    """验证应用版本号已更新到 v9.0。"""

    def test_app_version_is_9(self):
        """APP_VERSION 应为 9.0.0。"""
        assert APP_VERSION == "9.0.0", f"APP_VERSION 应为 9.0.0，实际: {APP_VERSION}"

    def test_app_title_is_v9(self):
        """APP_TITLE 应为 ThesisMiner v9.0。"""
        assert APP_TITLE == "ThesisMiner v9.0", f"APP_TITLE 应为 ThesisMiner v9.0，实际: {APP_TITLE}"


# ============================================================
# 第二部分：旧模型移除验证
# ============================================================

class TestOldModelsRemoved:
    """验证旧模型已从注册表移除。"""

    def test_deepseek_chat_v3_removed(self):
        """deepseek-chat-v3 应已移除。"""
        assert "deepseek-chat-v3" not in _get_model_ids()

    def test_gpt_4_1_removed(self):
        """gpt-4.1 应已移除。"""
        assert "gpt-4.1" not in _get_model_ids()

    def test_gpt_4_1_mini_removed(self):
        """gpt-4.1-mini 应已移除。"""
        assert "gpt-4.1-mini" not in _get_model_ids()

    def test_claude_sonnet_4_5_removed(self):
        """claude-sonnet-4.5 应已移除。"""
        assert "claude-sonnet-4.5" not in _get_model_ids()

    def test_claude_opus_4_5_removed(self):
        """claude-opus-4.5 应已移除。"""
        assert "claude-opus-4.5" not in _get_model_ids()

    def test_deepseek_v3_2_removed(self):
        """deepseek-v3.2 应已移除。"""
        assert "deepseek-v3.2" not in _get_model_ids()

    def test_deepseek_r2_removed(self):
        """deepseek-r2 应已移除。"""
        assert "deepseek-r2" not in _get_model_ids()

    def test_qwen3_max_removed(self):
        """qwen3-max 应已移除。"""
        assert "qwen3-max" not in _get_model_ids()

    def test_gemini_2_5_pro_removed(self):
        """gemini-2.5-pro 应已移除。"""
        assert "gemini-2.5-pro" not in _get_model_ids()

    def test_glm_4_6_removed(self):
        """glm-4.6 应已移除。"""
        assert "glm-4.6" not in _get_model_ids()

    def test_doubao_1_5_pro_removed(self):
        """doubao-1.5-pro 应已移除。"""
        assert "doubao-1.5-pro" not in _get_model_ids()

    def test_all_old_models_removed(self):
        """所有旧模型 ID 应已从 DEFAULT_MODELS 移除。"""
        current_ids = _get_model_ids()
        for old_id in OLD_MODEL_IDS:
            assert old_id not in current_ids, f"旧模型 {old_id} 应已移除"


# ============================================================
# 第三部分：2026.06 新模型加入验证
# ============================================================

class TestNewModels2026Added:
    """验证 2026.06 最新批次模型已加入注册表。"""

    def test_deepseek_v4_present(self):
        """deepseek-v4 应存在。"""
        assert "deepseek-v4" in _get_model_ids()

    def test_deepseek_r3_present(self):
        """deepseek-r3 应存在。"""
        assert "deepseek-r3" in _get_model_ids()

    def test_glm_5_2_present(self):
        """glm-5.2 应存在。"""
        assert "glm-5.2" in _get_model_ids()

    def test_glm_5_2_flash_present(self):
        """glm-5.2-flash 应存在。"""
        assert "glm-5.2-flash" in _get_model_ids()

    def test_gpt_5_present(self):
        """gpt-5 应存在。"""
        assert "gpt-5" in _get_model_ids()

    def test_gpt_5_mini_present(self):
        """gpt-5-mini 应存在。"""
        assert "gpt-5-mini" in _get_model_ids()

    def test_claude_opus_5_present(self):
        """claude-opus-5 应存在。"""
        assert "claude-opus-5" in _get_model_ids()

    def test_qwen3_max_2026_present(self):
        """qwen3-max-2026 应存在。"""
        assert "qwen3-max-2026" in _get_model_ids()

    def test_gemini_3_pro_present(self):
        """gemini-3-pro 应存在。"""
        assert "gemini-3-pro" in _get_model_ids()

    def test_doubao_2_0_pro_present(self):
        """doubao-2.0-pro 应存在。"""
        assert "doubao-2.0-pro" in _get_model_ids()

    def test_all_new_models_present(self):
        """所有 2026.06 新模型应已加入 DEFAULT_MODELS。"""
        current_ids = _get_model_ids()
        for new_id in NEW_MODEL_IDS:
            assert new_id in current_ids, f"新模型 {new_id} 应已加入"

    def test_models_count_is_10(self):
        """模型数量应为 10 个。"""
        assert len(DEFAULT_MODELS) == 10, f"模型数量应为 10，实际: {len(DEFAULT_MODELS)}"


# ============================================================
# 第四部分：capabilities 字段验证
# ============================================================

class TestCapabilitiesField:
    """验证每个模型含 capabilities 字段及三个布尔键。"""

    def test_every_model_has_capabilities(self):
        """每个模型应含 capabilities 字段。"""
        for model in DEFAULT_MODELS:
            assert "capabilities" in model, f"模型 {model['id']} 缺少 capabilities 字段"
            assert isinstance(model["capabilities"], dict), (
                f"模型 {model['id']} 的 capabilities 应为字典"
            )

    def test_capabilities_has_deep_thinking(self):
        """每个模型的 capabilities 应含 deep_thinking 布尔键。"""
        for model in DEFAULT_MODELS:
            caps = model["capabilities"]
            assert "deep_thinking" in caps, f"模型 {model['id']} 缺少 capabilities.deep_thinking"
            assert isinstance(caps["deep_thinking"], bool), (
                f"模型 {model['id']} 的 capabilities.deep_thinking 应为布尔值"
            )

    def test_capabilities_has_web_search(self):
        """每个模型的 capabilities 应含 web_search 布尔键。"""
        for model in DEFAULT_MODELS:
            caps = model["capabilities"]
            assert "web_search" in caps, f"模型 {model['id']} 缺少 capabilities.web_search"
            assert isinstance(caps["web_search"], bool), (
                f"模型 {model['id']} 的 capabilities.web_search 应为布尔值"
            )

    def test_capabilities_has_streaming(self):
        """每个模型的 capabilities 应含 streaming 布尔键。"""
        for model in DEFAULT_MODELS:
            caps = model["capabilities"]
            assert "streaming" in caps, f"模型 {model['id']} 缺少 capabilities.streaming"
            assert isinstance(caps["streaming"], bool), (
                f"模型 {model['id']} 的 capabilities.streaming 应为布尔值"
            )

    def test_capabilities_all_keys_present(self):
        """每个模型的 capabilities 应包含全部三个键。"""
        for model in DEFAULT_MODELS:
            caps = model["capabilities"]
            for key in CAPABILITY_KEYS:
                assert key in caps, f"模型 {model['id']} 的 capabilities 缺少 {key}"


# ============================================================
# 第五部分：agent_default 与 release_year 验证
# ============================================================

class TestAgentDefaultAndReleaseYear:
    """验证每个模型含 agent_default 与 release_year=2026。"""

    def test_every_model_has_agent_default(self):
        """每个模型应含 agent_default 字段。"""
        for model in DEFAULT_MODELS:
            assert "agent_default" in model, f"模型 {model['id']} 缺少 agent_default 字段"

    def test_agent_default_value_valid(self):
        """每个模型的 agent_default 值应为合法角色。"""
        for model in DEFAULT_MODELS:
            assert model["agent_default"] in VALID_AGENT_ROLES, (
                f"模型 {model['id']} 的 agent_default 值非法: {model['agent_default']}"
            )

    def test_every_model_has_release_year(self):
        """每个模型应含 release_year 字段。"""
        for model in DEFAULT_MODELS:
            assert "release_year" in model, f"模型 {model['id']} 缺少 release_year 字段"

    def test_release_year_is_2026(self):
        """每个模型的 release_year 应为 2026。"""
        for model in DEFAULT_MODELS:
            assert model["release_year"] == 2026, (
                f"模型 {model['id']} 的 release_year 应为 2026，实际: {model['release_year']}"
            )


# ============================================================
# 第六部分：provider 字段验证
# ============================================================

class TestProviderField:
    """验证每个模型含 provider 字段且值合法。"""

    def test_every_model_has_provider(self):
        """每个模型应含 provider 字段。"""
        for model in DEFAULT_MODELS:
            assert "provider" in model, f"模型 {model['id']} 缺少 provider 字段"

    def test_provider_value_valid(self):
        """每个模型的 provider 值应为合法提供商。"""
        for model in DEFAULT_MODELS:
            assert model["provider"] in VALID_PROVIDERS, (
                f"模型 {model['id']} 的 provider 值非法: {model['provider']}"
            )


# ============================================================
# 第七部分：定价 CNY 格式验证
# ============================================================

class TestPricingCnyFormat:
    """验证定价为 CNY 格式（含 input / cached_input / output）。"""

    def test_every_model_has_pricing(self):
        """每个模型应含 pricing 字段。"""
        for model in DEFAULT_MODELS:
            assert "pricing" in model, f"模型 {model['id']} 缺少 pricing 字段"
            assert isinstance(model["pricing"], dict), (
                f"模型 {model['id']} 的 pricing 应为字典"
            )

    def test_pricing_has_input(self):
        """每个模型的 pricing 应含 input 键。"""
        for model in DEFAULT_MODELS:
            assert "input" in model["pricing"], f"模型 {model['id']} 缺少 pricing.input"

    def test_pricing_has_cached_input(self):
        """每个模型的 pricing 应含 cached_input 键。"""
        for model in DEFAULT_MODELS:
            assert "cached_input" in model["pricing"], (
                f"模型 {model['id']} 缺少 pricing.cached_input"
            )

    def test_pricing_has_output(self):
        """每个模型的 pricing 应含 output 键。"""
        for model in DEFAULT_MODELS:
            assert "output" in model["pricing"], f"模型 {model['id']} 缺少 pricing.output"

    def test_pricing_values_non_negative(self):
        """定价值应为非负数。"""
        for model in DEFAULT_MODELS:
            pricing = model["pricing"]
            for key in PRICING_CNY_KEYS:
                assert isinstance(pricing[key], (int, float)), (
                    f"模型 {model['id']} 的 pricing.{key} 应为数值"
                )
                assert pricing[key] >= 0, (
                    f"模型 {model['id']} 的 pricing.{key} 应为非负数，实际: {pricing[key]}"
                )

    def test_output_price_higher_than_input(self):
        """输出价格通常应高于或等于输入价格。"""
        for model in DEFAULT_MODELS:
            pricing = model["pricing"]
            assert pricing["output"] >= pricing["input"], (
                f"模型 {model['id']} 的 output 价格应 >= input 价格"
            )

    def test_cached_input_lower_than_input(self):
        """缓存输入价格应低于或等于输入价格。"""
        for model in DEFAULT_MODELS:
            pricing = model["pricing"]
            assert pricing["cached_input"] <= pricing["input"], (
                f"模型 {model['id']} 的 cached_input 价格应 <= input 价格"
            )


# ============================================================
# 第八部分：context_length 字段验证
# ============================================================

class TestContextLengthField:
    """验证每个模型含 context_length 字段。"""

    def test_every_model_has_context_length(self):
        """每个模型应含 context_length 字段。"""
        for model in DEFAULT_MODELS:
            assert "context_length" in model, f"模型 {model['id']} 缺少 context_length 字段"

    def test_context_length_is_int(self):
        """context_length 应为整数。"""
        for model in DEFAULT_MODELS:
            assert isinstance(model["context_length"], int), (
                f"模型 {model['id']} 的 context_length 应为整数"
            )

    def test_context_length_positive(self):
        """context_length 应为正数。"""
        for model in DEFAULT_MODELS:
            assert model["context_length"] > 0, (
                f"模型 {model['id']} 的 context_length 应为正数"
            )


# ============================================================
# 第九部分：DEFAULT_STEP_MODELS 验证（含 thesis_writer）
# ============================================================

class TestDefaultStepModels:
    """测试 DEFAULT_STEP_MODELS 步骤路由（v9.0 含 thesis_writer）。"""

    def test_step_models_is_dict(self):
        """DEFAULT_STEP_MODELS 应为字典。"""
        assert isinstance(DEFAULT_STEP_MODELS, dict)

    def test_step_models_has_thesis_writer(self):
        """DEFAULT_STEP_MODELS 应包含 thesis_writer 角色（v9.0 新增）。"""
        assert "thesis_writer" in DEFAULT_STEP_MODELS, "step_models 应包含 thesis_writer 键"

    def test_step_models_has_all_7_roles(self):
        """DEFAULT_STEP_MODELS 应包含全部 7 个角色。"""
        expected_keys = {
            "orchestrator", "reasoner", "mentor", "inspire",
            "report", "search", "thesis_writer",
        }
        assert set(DEFAULT_STEP_MODELS.keys()) == expected_keys, (
            f"step_models 键不匹配，实际: {set(DEFAULT_STEP_MODELS.keys())}"
        )

    def test_orchestrator_routes_to_deepseek_r3(self):
        """orchestrator 应路由到 deepseek-r3。"""
        assert DEFAULT_STEP_MODELS["orchestrator"] == "deepseek-r3"

    def test_reasoner_routes_to_deepseek_v4(self):
        """reasoner 应路由到 deepseek-v4。"""
        assert DEFAULT_STEP_MODELS["reasoner"] == "deepseek-v4"

    def test_mentor_routes_to_glm_5_2(self):
        """mentor 应路由到 glm-5.2。"""
        assert DEFAULT_STEP_MODELS["mentor"] == "glm-5.2"

    def test_inspire_routes_to_glm_5_2_flash(self):
        """inspire 应路由到 glm-5.2-flash。"""
        assert DEFAULT_STEP_MODELS["inspire"] == "glm-5.2-flash"

    def test_report_routes_to_claude_opus_5(self):
        """report 应路由到 claude-opus-5。"""
        assert DEFAULT_STEP_MODELS["report"] == "claude-opus-5"

    def test_search_routes_to_gpt_5_mini(self):
        """search 应路由到 gpt-5-mini。"""
        assert DEFAULT_STEP_MODELS["search"] == "gpt-5-mini"

    def test_thesis_writer_routes_to_gpt_5(self):
        """thesis_writer 应路由到 gpt-5。"""
        assert DEFAULT_STEP_MODELS["thesis_writer"] == "gpt-5"

    def test_all_step_models_exist_in_registry(self):
        """所有步骤路由的模型 ID 应存在于注册表。"""
        ids = _get_model_ids()
        for purpose, mid in DEFAULT_STEP_MODELS.items():
            assert mid in ids, f"步骤 {purpose} 的模型 {mid} 不在注册表中"


# ============================================================
# 第十部分：具体模型配置验证
# ============================================================

class TestSpecificModelConfigs:
    """验证关键模型的具体配置。

    使用 mock 绕过 data/config.json 用户配置，直接测试 DEFAULT_MODELS。
    """

    @pytest.fixture(autouse=True)
    def _mock_settings(self):
        """每个测试自动 mock Settings，使用 DEFAULT_MODELS/DEFAULT_STEP_MODELS。"""
        _reset_settings_singleton()
        with patch("backend.config.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.step_models = DEFAULT_STEP_MODELS
            mock_s.models = copy.deepcopy(DEFAULT_MODELS)
            mock_s.ai_model = "deepseek-v4"
            mock_settings.return_value = mock_s
            yield
        _reset_settings_singleton()

    def test_deepseek_v4_config(self):
        """deepseek-v4 配置应正确。"""
        m = get_model_config("deepseek-v4")
        assert m is not None
        assert m["provider"] == "deepseek"
        assert m["agent_default"] == "reasoner"
        assert m["context_length"] == 256000
        assert m["capabilities"]["deep_thinking"] is True
        assert m["capabilities"]["web_search"] is True
        assert m["capabilities"]["streaming"] is True
        assert m["pricing"]["input"] == 4
        assert m["pricing"]["cached_input"] == 1
        assert m["pricing"]["output"] == 16

    def test_deepseek_r3_config(self):
        """deepseek-r3 配置应正确。"""
        m = get_model_config("deepseek-r3")
        assert m is not None
        assert m["agent_default"] == "orchestrator"
        assert m["context_length"] == 128000
        assert m["capabilities"]["deep_thinking"] is True
        assert m["pricing"]["input"] == 8
        assert m["pricing"]["output"] == 32

    def test_glm_5_2_config(self):
        """glm-5.2 配置应正确。"""
        m = get_model_config("glm-5.2")
        assert m is not None
        assert m["provider"] == "zhipu"
        assert m["agent_default"] == "mentor"
        assert m["context_length"] == 200000
        assert m["pricing"]["input"] == 5
        assert m["pricing"]["output"] == 15

    def test_gpt_5_config(self):
        """gpt-5 配置应正确（thesis_writer 角色）。"""
        m = get_model_config("gpt-5")
        assert m is not None
        assert m["provider"] == "openai"
        assert m["agent_default"] == "thesis_writer"
        assert m["context_length"] == 400000
        assert m["pricing"]["input"] == 40
        assert m["pricing"]["output"] == 120

    def test_claude_opus_5_config(self):
        """claude-opus-5 配置应正确。"""
        m = get_model_config("claude-opus-5")
        assert m is not None
        assert m["provider"] == "anthropic"
        assert m["agent_default"] == "report"
        assert m["context_length"] == 200000
        assert m["capabilities"]["deep_thinking"] is True
        assert m["pricing"]["input"] == 60
        assert m["pricing"]["output"] == 180

    def test_gemini_3_pro_context_2m(self):
        """gemini-3-pro 应有 200 万超长上下文。"""
        m = get_model_config("gemini-3-pro")
        assert m is not None
        assert m["context_length"] == 2000000

    def test_doubao_2_0_pro_streaming_only(self):
        """doubao-2.0-pro 应仅支持 streaming。"""
        m = get_model_config("doubao-2.0-pro")
        assert m is not None
        assert m["capabilities"]["streaming"] is True
        assert m["capabilities"]["deep_thinking"] is False
        assert m["capabilities"]["web_search"] is False


# ============================================================
# 第十一部分：get_step_model 函数验证
# ============================================================

class TestGetStepModelV9:
    """测试 get_step_model 函数支持 thesis_writer 角色。

    使用 mock 绕过 data/config.json 用户配置，直接测试 DEFAULT_STEP_MODELS。
    """

    @pytest.fixture(autouse=True)
    def _mock_settings(self):
        """每个测试自动 mock Settings，使用 DEFAULT_MODELS/DEFAULT_STEP_MODELS。"""
        _reset_settings_singleton()
        with patch("backend.config.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.step_models = DEFAULT_STEP_MODELS
            mock_s.models = copy.deepcopy(DEFAULT_MODELS)
            mock_s.ai_model = "deepseek-v4"
            mock_settings.return_value = mock_s
            yield
        _reset_settings_singleton()

    def test_get_step_model_thesis_writer(self):
        """get_step_model 应支持 thesis_writer 用途。"""
        model_id = get_step_model("thesis_writer")
        assert model_id == "gpt-5"

    def test_get_step_model_orchestrator(self):
        """get_step_model 应返回 orchestrator 模型。"""
        model_id = get_step_model("orchestrator")
        assert model_id == "deepseek-r3"


# ============================================================
# 第十二部分：模型 ID 唯一性验证
# ============================================================

class TestModelIdUniqueness:
    """验证模型 ID 唯一性。"""

    def test_model_ids_unique(self):
        """所有模型 ID 应唯一。"""
        ids = [m["id"] for m in DEFAULT_MODELS]
        assert len(ids) == len(set(ids)), "存在重复的模型 ID"

    def test_model_ids_match_whitelist(self):
        """模型 ID 集合应与 2026.06 白名单完全匹配。"""
        assert _get_model_ids() == NEW_MODEL_IDS
