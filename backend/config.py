"""配置管理模块

负责加载 .env 环境变量与 data/config.json 用户配置，
提供全局单例 Settings 与按学位分级的模型路由常量。
"""
import copy
import json
import os
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 文件（若存在）
load_dotenv()

# 用户配置文件路径
CONFIG_FILE_PATH = "data/config.json"

# 应用版本号（v9.0.0：2026.06 最新模型批次 + thesis_writer 角色）
APP_VERSION = "9.0.0"
APP_TITLE = "ThesisMiner v9.0"


# 按学位分级路由的模型映射
DEGREE_MODELS = {
    "master": "中等成本模型",
    "doctor": "高上下文模型",
}

# 文献基线数量（硕士/博士）
LITERATURE_BASELINE = {
    "master": 30,
    "doctor": 50,
}

# 学术日历（学位对应的最大年限与说明）
ACADEMIC_CALENDAR = {
    "master": {"max_years": 1, "description": "硕士1年内出结果"},
    "doctor": {"max_years": 2, "description": "博士2年内出结果"},
}

# 默认多模型注册表（v9.0 更新：移除全部 2025/旧 2026 模型，新增 2026.06 最新批次）
# 每个模型包含新结构字段（name/provider/context_length/capabilities/pricing{input,cached_input,output}/description）
# 同时保留旧字段别名（label/base_url/max_context/supports_*/pricing.input_cny_per_million 等）以兼容既有代码
DEFAULT_MODELS = [
    # ===== 1. DeepSeek V4（2026.06）- 高性价比通用 + 推理模型 =====
    {
        "id": "deepseek-v4",
        "name": "DeepSeek V4",
        "label": "DeepSeek V4 (2026.06)",
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "description": "DeepSeek 2026.06 最新通用模型，支持深度思考与联网搜索，高性价比",
        "pricing": {
            "input": 4,
            "cached_input": 1,
            "output": 16,
            "input_cny_per_million": 4,
            "cached_input_cny_per_million": 1,
            "output_cny_per_million": 16,
        },
        "context_length": 256000,
        "max_context": 256000,
        "default_temperature": 0.7,
        "agent_default": "reasoner",
        "release_year": 2026,
        "capabilities": {
            "deep_thinking": True,
            "web_search": True,
            "streaming": True,
        },
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": True,
    },
    # ===== 2. DeepSeek R3（2026.06）- 深度推理模型 =====
    {
        "id": "deepseek-r3",
        "name": "DeepSeek R3",
        "label": "DeepSeek R3 Reasoner (2026.06)",
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "description": "DeepSeek 2026.06 最新推理模型，支持深度思考链，适合复杂逻辑编排",
        "pricing": {
            "input": 8,
            "cached_input": 2,
            "output": 32,
            "input_cny_per_million": 8,
            "cached_input_cny_per_million": 2,
            "output_cny_per_million": 32,
        },
        "context_length": 128000,
        "max_context": 128000,
        "default_temperature": 0.0,
        "agent_default": "orchestrator",
        "release_year": 2026,
        "capabilities": {
            "deep_thinking": True,
            "web_search": False,
            "streaming": True,
        },
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": False,
    },
    # ===== 3. GLM-5.2（智谱，2026.06）- 全能导师模型 =====
    {
        "id": "glm-5.2",
        "name": "GLM-5.2",
        "label": "GLM-5.2 (2026.06)",
        "provider": "zhipu",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "",
        "description": "智谱 2026.06 最新 GLM 模型，支持思考/联网/流式，适合导师对话",
        "pricing": {
            "input": 5,
            "cached_input": 1,
            "output": 15,
            "input_cny_per_million": 5,
            "cached_input_cny_per_million": 1,
            "output_cny_per_million": 15,
        },
        "context_length": 200000,
        "max_context": 200000,
        "default_temperature": 0.7,
        "agent_default": "mentor",
        "release_year": 2026,
        "capabilities": {
            "deep_thinking": True,
            "web_search": True,
            "streaming": True,
        },
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": True,
    },
    # ===== 4. GLM-5.2 Flash（智谱，2026.06）- 快速低成本模型 =====
    {
        "id": "glm-5.2-flash",
        "name": "GLM-5.2 Flash",
        "label": "GLM-5.2 Flash (2026.06)",
        "provider": "zhipu",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "",
        "description": "智谱 2026.06 Flash 模型，快速低成本，适合创意激发与批量任务",
        "pricing": {
            "input": 1,
            "cached_input": 0.2,
            "output": 4,
            "input_cny_per_million": 1,
            "cached_input_cny_per_million": 0.2,
            "output_cny_per_million": 4,
        },
        "context_length": 128000,
        "max_context": 128000,
        "default_temperature": 0.7,
        "agent_default": "inspire",
        "release_year": 2026,
        "capabilities": {
            "deep_thinking": False,
            "web_search": True,
            "streaming": True,
        },
        "supports_streaming": True,
        "supports_thinking": False,
        "supports_web_search": True,
    },
    # ===== 5. GPT-5（OpenAI，2026.06）- 顶级论文写作模型 =====
    {
        "id": "gpt-5",
        "name": "GPT-5",
        "label": "GPT-5 (2026.06)",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "description": "OpenAI 2026.06 最新旗舰模型，支持思考/联网/流式，适合高质量论文写作",
        "pricing": {
            "input": 40,
            "cached_input": 20,
            "output": 120,
            "input_cny_per_million": 40,
            "cached_input_cny_per_million": 20,
            "output_cny_per_million": 120,
        },
        "context_length": 400000,
        "max_context": 400000,
        "default_temperature": 0.7,
        "agent_default": "thesis_writer",
        "release_year": 2026,
        "capabilities": {
            "deep_thinking": True,
            "web_search": True,
            "streaming": True,
        },
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": True,
    },
    # ===== 6. GPT-5 Mini（OpenAI，2026.06）- 快速低成本检索模型 =====
    {
        "id": "gpt-5-mini",
        "name": "GPT-5 Mini",
        "label": "GPT-5 Mini (2026.06)",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "description": "OpenAI 2026.06 Mini 模型，快速低成本，适合文献检索与轻量任务",
        "pricing": {
            "input": 8,
            "cached_input": 4,
            "output": 24,
            "input_cny_per_million": 8,
            "cached_input_cny_per_million": 4,
            "output_cny_per_million": 24,
        },
        "context_length": 128000,
        "max_context": 128000,
        "default_temperature": 0.7,
        "agent_default": "search",
        "release_year": 2026,
        "capabilities": {
            "deep_thinking": False,
            "web_search": True,
            "streaming": True,
        },
        "supports_streaming": True,
        "supports_thinking": False,
        "supports_web_search": True,
    },
    # ===== 7. Claude Opus 5（Anthropic，2026.06）- 顶级报告模型 =====
    {
        "id": "claude-opus-5",
        "name": "Claude Opus 5",
        "label": "Claude Opus 5 (2026.06)",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "description": "Anthropic 2026.06 最新 Opus 模型，支持深度思考，适合高质量报告生成",
        "pricing": {
            "input": 60,
            "cached_input": 30,
            "output": 180,
            "input_cny_per_million": 60,
            "cached_input_cny_per_million": 30,
            "output_cny_per_million": 180,
        },
        "context_length": 200000,
        "max_context": 200000,
        "default_temperature": 0.7,
        "agent_default": "report",
        "release_year": 2026,
        "capabilities": {
            "deep_thinking": True,
            "web_search": False,
            "streaming": True,
        },
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": False,
    },
    # ===== 8. Qwen3 Max 2026（阿里通义，2026.06）- 全能推理模型 =====
    {
        "id": "qwen3-max-2026",
        "name": "Qwen3 Max 2026",
        "label": "Qwen3 Max 2026 (2026.06)",
        "provider": "qwen",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "",
        "description": "阿里通义 2026.06 最新 Max 模型，支持思考/联网/流式，适合复杂推理",
        "pricing": {
            "input": 6,
            "cached_input": 1.5,
            "output": 18,
            "input_cny_per_million": 6,
            "cached_input_cny_per_million": 1.5,
            "output_cny_per_million": 18,
        },
        "context_length": 256000,
        "max_context": 256000,
        "default_temperature": 0.7,
        "agent_default": "reasoner",
        "release_year": 2026,
        "capabilities": {
            "deep_thinking": True,
            "web_search": True,
            "streaming": True,
        },
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": True,
    },
    # ===== 9. Gemini 3 Pro（Google，2026.06）- 超长上下文检索模型 =====
    {
        "id": "gemini-3-pro",
        "name": "Gemini 3 Pro",
        "label": "Gemini 3 Pro (2026.06)",
        "provider": "google",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": "",
        "description": "Google 2026.06 最新 Gemini Pro 模型，200 万超长上下文，适合长文档检索",
        "pricing": {
            "input": 35,
            "cached_input": 10,
            "output": 105,
            "input_cny_per_million": 35,
            "cached_input_cny_per_million": 10,
            "output_cny_per_million": 105,
        },
        "context_length": 2000000,
        "max_context": 2000000,
        "default_temperature": 0.7,
        "agent_default": "search",
        "release_year": 2026,
        "capabilities": {
            "deep_thinking": True,
            "web_search": True,
            "streaming": True,
        },
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": True,
    },
    # ===== 10. Doubao 2.0 Pro（字节豆包，2026.06）- 低成本流式模型 =====
    {
        "id": "doubao-2.0-pro",
        "name": "Doubao 2.0 Pro",
        "label": "Doubao 2.0 Pro (2026.06)",
        "provider": "bytecode",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key": "",
        "description": "字节豆包 2026.06 最新模型，支持流式输出，低成本，适合创意激发",
        "pricing": {
            "input": 3,
            "cached_input": 0.8,
            "output": 9,
            "input_cny_per_million": 3,
            "cached_input_cny_per_million": 0.8,
            "output_cny_per_million": 9,
        },
        "context_length": 128000,
        "max_context": 128000,
        "default_temperature": 0.7,
        "agent_default": "inspire",
        "release_year": 2026,
        "capabilities": {
            "deep_thinking": False,
            "web_search": False,
            "streaming": True,
        },
        "supports_streaming": True,
        "supports_thinking": False,
        "supports_web_search": False,
    },
]

# 各步骤默认模型映射（v9.0 更新：使用 2026.06 最新模型，新增 thesis_writer 角色）
DEFAULT_STEP_MODELS = {
    "orchestrator": "deepseek-r3",
    "reasoner": "deepseek-v4",
    "mentor": "glm-5.2",
    "inspire": "glm-5.2-flash",
    "report": "claude-opus-5",
    "search": "gpt-5-mini",
    "thesis_writer": "gpt-5",
}


# ===== 智能上下文压缩设置（v9.0）=====
# 与三段式 Prompt 缓存协同：压缩后的历史进入稳定前缀（缓存），
# 仅最近 N 轮进入动态尾部，目标缓存命中率 ≥95%。
COMPACT_THRESHOLD = int(os.getenv("COMPACT_THRESHOLD", "10"))  # 触发压缩的轮数
COMPACT_CHARS = int(os.getenv("COMPACT_CHARS", "100"))  # 每条压缩消息的目标字符数
COMPACT_KEEP_RECENT = int(os.getenv("COMPACT_KEEP_RECENT", "3"))  # 保留为原始的最近轮数
COMPACT_ENABLED = os.getenv("COMPACT_ENABLED", "true").lower() == "true"


def get_compact_config() -> dict:
    """返回智能上下文压缩配置字典。

    集中读取环境变量，便于 smart_compact 与测试统一引用。
    所有字段均可通过环境变量覆盖。

    Returns:
        包含 enabled / compact_threshold / compact_chars /
        compact_keep_recent 四个键的字典。
    """
    return {
        "enabled": os.getenv("COMPACT_ENABLED", "true").lower() == "true",
        "compact_threshold": int(os.getenv("COMPACT_THRESHOLD", "10")),
        "compact_chars": int(os.getenv("COMPACT_CHARS", "100")),
        "compact_keep_recent": int(os.getenv("COMPACT_KEEP_RECENT", "3")),
    }


def _str_to_bool(value: str) -> bool:
    """将字符串解析为布尔值，支持 true/1/yes 等常见真值。"""
    return str(value).strip().lower() in ("true", "1", "yes", "on")


class Settings:
    """全局配置项。

    优先级：data/config.json 用户配置 > .env 环境变量 > 默认值。
    """

    def __init__(self) -> None:
        # 默认值
        self.ai_api_key: str = os.getenv("AI_API_KEY", "")
        self.ai_base_url: str = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
        self.ai_model: str = os.getenv("AI_MODEL", "deepseek-v4")
        self.db_path: str = os.getenv("DB_PATH", "data/thesis_miner.db")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.flask_env: str = os.getenv("FLASK_ENV", "production")

        # 真实文献检索配置（v6.0 新增）
        # 默认关闭，需显式开启才调用真实 API
        self.real_search_enabled: bool = _str_to_bool(
            os.getenv("REAL_SEARCH_ENABLED", "false")
        )
        self.search_api_keys: dict = {
            "arxiv": os.getenv("SEARCH_API_KEYS_ARXIV", ""),
            "semantic_scholar": os.getenv("SEARCH_API_KEYS_SEMANTIC_SCHOLAR", ""),
        }

        # 多模型注册表与步骤路由（v7.0 新增）
        # ai_api_key / ai_base_url / ai_model 作为默认模型，
        # 当某模型的 api_key 为空时回退到 settings.ai_api_key
        self.auto_open_browser: bool = _str_to_bool(
            os.getenv("AUTO_OPEN_BROWSER", "true")
        )
        self.models: list[dict] = copy.deepcopy(DEFAULT_MODELS)
        self.step_models: dict = copy.deepcopy(DEFAULT_STEP_MODELS)
        self.currency: str = os.getenv("CURRENCY", "CNY")

        # 若存在用户配置文件，则覆盖默认值
        self._load_user_config()

    def _load_user_config(self) -> None:
        """从 data/config.json 加载用户配置覆盖默认值。"""
        config_path = Path(CONFIG_FILE_PATH)
        if not config_path.exists():
            return
        try:
            with config_path.open("r", encoding="utf-8") as f:
                user_config = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        if "ai_api_key" in user_config:
            self.ai_api_key = user_config["ai_api_key"]
        if "ai_base_url" in user_config:
            self.ai_base_url = user_config["ai_base_url"]
        if "ai_model" in user_config:
            self.ai_model = user_config["ai_model"]
        if "db_path" in user_config:
            self.db_path = user_config["db_path"]
        if "log_level" in user_config:
            self.log_level = user_config["log_level"]
        if "flask_env" in user_config:
            self.flask_env = user_config["flask_env"]

        # 真实文献检索配置（v6.0 新增）
        if "real_search_enabled" in user_config:
            self.real_search_enabled = bool(user_config["real_search_enabled"])
        if "search_api_keys" in user_config and isinstance(
            user_config["search_api_keys"], dict
        ):
            # 合并而非整体覆盖，保留默认键结构
            saved = user_config["search_api_keys"]
            self.search_api_keys = {
                "arxiv": saved.get("arxiv", self.search_api_keys.get("arxiv", "")),
                "semantic_scholar": saved.get(
                    "semantic_scholar",
                    self.search_api_keys.get("semantic_scholar", ""),
                ),
            }

        # 多模型注册表与步骤路由（v7.0/v8.0/v9.0 新增）
        if "models" in user_config and isinstance(user_config["models"], list):
            self.models = user_config["models"]
        if "step_models" in user_config and isinstance(
            user_config["step_models"], dict
        ):
            # 合并，保留默认键（v9.0 新增 thesis_writer 键）
            saved = user_config["step_models"]
            self.step_models = {
                "orchestrator": saved.get(
                    "orchestrator", DEFAULT_STEP_MODELS["orchestrator"]
                ),
                "reasoner": saved.get("reasoner", DEFAULT_STEP_MODELS["reasoner"]),
                "mentor": saved.get("mentor", DEFAULT_STEP_MODELS["mentor"]),
                "inspire": saved.get("inspire", DEFAULT_STEP_MODELS["inspire"]),
                "report": saved.get("report", DEFAULT_STEP_MODELS["report"]),
                "search": saved.get("search", DEFAULT_STEP_MODELS["search"]),
                "thesis_writer": saved.get(
                    "thesis_writer", DEFAULT_STEP_MODELS["thesis_writer"]
                ),
            }
        if "currency" in user_config:
            self.currency = (
                user_config["currency"]
                if user_config["currency"] in ("CNY", "USD")
                else "CNY"
            )
        if "auto_open_browser" in user_config:
            self.auto_open_browser = bool(user_config["auto_open_browser"])


# 单例缓存
_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """返回全局 Settings 单例。"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def get_model_config(model_id: str) -> dict | None:
    """根据 model_id 获取模型配置。

    Args:
        model_id: 模型唯一标识

    Returns:
        模型配置字典，找不到返回 None
    """
    settings = get_settings()
    for model in settings.models:
        if model.get("id") == model_id:
            return model
    return None


def get_step_model(purpose: str) -> str:
    """根据调用用途获取对应的模型 ID。

    优先级：step_models[purpose] > models[0].id > ai_model

    Args:
        purpose: 调用用途（reasoner/mentor/inspire/report/search）

    Returns:
        模型 ID 字符串
    """
    settings = get_settings()
    model_id = settings.step_models.get(purpose)
    if model_id and get_model_config(model_id):
        return model_id
    # 回退到第一个模型
    if settings.models:
        return settings.models[0].get("id", settings.ai_model)
    return settings.ai_model


def save_config(settings_dict: dict) -> None:
    """将配置字典保存到 data/config.json。

    Args:
        settings_dict: 需要持久化的配置键值对。
    """
    config_path = Path(CONFIG_FILE_PATH)
    # 确保目录存在
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # 读取已有配置（若存在），合并后写回
    existing_config: dict = {}
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                existing_config = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing_config = {}

    existing_config.update(settings_dict)

    with config_path.open("w", encoding="utf-8") as f:
        json.dump(existing_config, f, ensure_ascii=False, indent=2)

    # 重置单例以便下次读取最新配置
    global _settings_instance
    _settings_instance = None
