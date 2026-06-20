"""Task 1 测试：验证 v8.0 模型注册表更新

验证：
- 旧模型（gpt-4o-mini / gpt-4o / deepseek-chat）已移除
- 2026 最新模型已加入
- 每个模型含 agent_default 与 release_year 字段
- DEFAULT_STEP_MODELS 包含 orchestrator 键
"""
import pytest

from backend.config import DEFAULT_MODELS, DEFAULT_STEP_MODELS, get_settings


# 旧模型 ID 黑名单（应已移除）
OLD_MODEL_IDS = {"gpt-4o-mini", "gpt-4o", "deepseek-chat", "deepseek-reasoner", "qwen-plus", "qwen-max", "deepseek-chat-v3"}

# 2026 新模型 ID 白名单（应已加入）
NEW_MODEL_IDS = {
    "gpt-4.1-mini",
    "gpt-4.1",
    "deepseek-v3.2",
    "deepseek-r2",
    "claude-sonnet-4.5",
    "claude-opus-4.5",
    "qwen3-max",
    "gemini-2.5-pro",
    "glm-4.6",
    "doubao-1.5-pro",
}


class TestModelRegistryV8:
    """v8.0 模型注册表测试"""

    def test_old_models_removed(self):
        """旧模型应已从 DEFAULT_MODELS 移除"""
        current_ids = {m["id"] for m in DEFAULT_MODELS}
        for old_id in OLD_MODEL_IDS:
            # gpt-4.1-mini 和 gpt-4.1 是保留的，不属于旧模型
            if old_id in ("gpt-4.1-mini", "gpt-4.1"):
                continue
            assert old_id not in current_ids, f"旧模型 {old_id} 应已移除"

    def test_new_models_added(self):
        """2026 最新模型应已加入 DEFAULT_MODELS"""
        current_ids = {m["id"] for m in DEFAULT_MODELS}
        for new_id in NEW_MODEL_IDS:
            assert new_id in current_ids, f"新模型 {new_id} 应已加入"

    def test_every_model_has_agent_default(self):
        """每个模型应含 agent_default 字段"""
        for model in DEFAULT_MODELS:
            assert "agent_default" in model, f"模型 {model['id']} 缺少 agent_default 字段"
            assert model["agent_default"] in (
                "reasoner",
                "mentor",
                "inspire",
                "report",
                "search",
                "orchestrator",
            ), f"模型 {model['id']} 的 agent_default 值非法: {model['agent_default']}"

    def test_every_model_has_release_year(self):
        """每个模型应含 release_year 字段"""
        for model in DEFAULT_MODELS:
            assert "release_year" in model, f"模型 {model['id']} 缺少 release_year 字段"
            assert model["release_year"] in (2025, 2026), (
                f"模型 {model['id']} 的 release_year 应为 2025 或 2026，实际: {model['release_year']}"
            )

    def test_step_models_has_orchestrator(self):
        """DEFAULT_STEP_MODELS 应包含 orchestrator 键"""
        assert "orchestrator" in DEFAULT_STEP_MODELS, "step_models 应包含 orchestrator 键"
        assert DEFAULT_STEP_MODELS["orchestrator"] == "claude-sonnet-4.5"

    def test_step_models_all_keys_present(self):
        """DEFAULT_STEP_MODELS 应包含所有 6 个键"""
        expected_keys = {"orchestrator", "reasoner", "mentor", "inspire", "report", "search"}
        assert set(DEFAULT_STEP_MODELS.keys()) == expected_keys

    def test_step_models_reference_valid_models(self):
        """step_models 中的模型 ID 应都在 DEFAULT_MODELS 中存在"""
        valid_ids = {m["id"] for m in DEFAULT_MODELS}
        for purpose, model_id in DEFAULT_STEP_MODELS.items():
            assert model_id in valid_ids, (
                f"step_models[{purpose}] = {model_id} 不在模型注册表中"
            )

    def test_default_ai_model_updated(self):
        """默认 ai_model 应更新为 2026 模型"""
        settings = get_settings()
        assert settings.ai_model != "gpt-4o-mini", "默认 ai_model 仍为旧值 gpt-4o-mini"

    def test_at_least_8_models(self):
        """应至少有 8 个模型"""
        assert len(DEFAULT_MODELS) >= 8, f"模型数量应 ≥8，实际: {len(DEFAULT_MODELS)}"

    def test_deepseek_models_support_cache(self):
        """DeepSeek 模型应支持缓存优化（用于 ≥95% 缓存命中）"""
        deepseek_models = [m for m in DEFAULT_MODELS if "deepseek" in m["id"]]
        assert len(deepseek_models) >= 2, "应至少有 2 个 DeepSeek 模型"
        for m in deepseek_models:
            assert m["max_context"] >= 64000, f"DeepSeek 模型 {m['id']} 上下文应 ≥64000"

    def test_claude_models_added(self):
        """Claude 4.5 系列应已加入"""
        current_ids = {m["id"] for m in DEFAULT_MODELS}
        assert "claude-sonnet-4.5" in current_ids
        assert "claude-opus-4.5" in current_ids

    def test_get_model_config_returns_new_model(self):
        """get_model_config 应能返回新模型配置"""
        from backend.config import get_model_config

        config = get_model_config("deepseek-v3.2")
        assert config is not None, "deepseek-v3.2 配置应存在"
        assert config["release_year"] == 2026
        assert config["agent_default"] == "search"

    def test_get_step_model_orchestrator(self):
        """get_step_model 应支持 orchestrator 用途"""
        from backend.config import get_step_model

        model_id = get_step_model("orchestrator")
        assert model_id == "claude-sonnet-4.5"
