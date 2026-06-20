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

# 应用版本号（v8.0.0：多 Agent 架构版）
APP_VERSION = "8.0.0"
APP_TITLE = "ThesisMiner v8.0"


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

# 默认多模型注册表（v8.0 更新：移除老旧模型，新增 2026 最新模型）
# 每个模型包含定价、能力标记、上下文长度、Agent 角色偏好与发布年份
DEFAULT_MODELS = [
    # ===== OpenAI GPT-4.1 系列（2025）=====
    {
        "id": "gpt-4.1-mini",
        "label": "GPT-4.1 Mini",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "pricing": {"input_cny_per_million": 0.7, "output_cny_per_million": 2.8},
        "supports_streaming": True,
        "supports_thinking": False,
        "supports_web_search": False,
        "max_context": 1000000,
        "default_temperature": 0.7,
        "agent_default": "mentor",
        "release_year": 2025,
    },
    {
        "id": "gpt-4.1",
        "label": "GPT-4.1",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "pricing": {"input_cny_per_million": 14, "output_cny_per_million": 56},
        "supports_streaming": True,
        "supports_thinking": False,
        "supports_web_search": False,
        "max_context": 1000000,
        "default_temperature": 0.7,
        "agent_default": "mentor",
        "release_year": 2025,
    },
    # ===== DeepSeek 系列（2026 最新）=====
    {
        "id": "deepseek-v3.2",
        "label": "DeepSeek V3.2 (2026)",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "pricing": {"input_cny_per_million": 1, "output_cny_per_million": 4},
        "supports_streaming": True,
        "supports_thinking": False,
        "supports_web_search": True,
        "max_context": 128000,
        "default_temperature": 0.7,
        "agent_default": "search",
        "release_year": 2026,
    },
    {
        "id": "deepseek-r2",
        "label": "DeepSeek R2 Reasoner (2026)",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "pricing": {"input_cny_per_million": 4, "output_cny_per_million": 16},
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": False,
        "max_context": 128000,
        "default_temperature": 0.0,
        "agent_default": "reasoner",
        "release_year": 2026,
    },
    # ===== Anthropic Claude 系列（2026 最新）=====
    {
        "id": "claude-sonnet-4.5",
        "label": "Claude Sonnet 4.5 (2026)",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "pricing": {"input_cny_per_million": 22, "output_cny_per_million": 110},
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": True,
        "max_context": 200000,
        "default_temperature": 0.7,
        "agent_default": "orchestrator",
        "release_year": 2026,
    },
    {
        "id": "claude-opus-4.5",
        "label": "Claude Opus 4.5 (2026)",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "pricing": {"input_cny_per_million": 110, "output_cny_per_million": 550},
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": True,
        "max_context": 200000,
        "default_temperature": 0.7,
        "agent_default": "report",
        "release_year": 2026,
    },
    # ===== 阿里通义 Qwen 系列（2026 最新）=====
    {
        "id": "qwen3-max",
        "label": "Qwen3 Max (2026)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "",
        "pricing": {"input_cny_per_million": 2.4, "output_cny_per_million": 9.6},
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": True,
        "max_context": 131072,
        "default_temperature": 0.7,
        "agent_default": "inspire",
        "release_year": 2026,
    },
    # ===== Google Gemini 系列（2026 最新）=====
    {
        "id": "gemini-2.5-pro",
        "label": "Gemini 2.5 Pro (2026)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": "",
        "pricing": {"input_cny_per_million": 9, "output_cny_per_million": 36},
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": True,
        "max_context": 2000000,
        "default_temperature": 0.7,
        "agent_default": "reasoner",
        "release_year": 2026,
    },
    # ===== 智谱 GLM 系列（2026 最新）=====
    {
        "id": "glm-4.6",
        "label": "GLM-4.6 (2026)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "",
        "pricing": {"input_cny_per_million": 5, "output_cny_per_million": 5},
        "supports_streaming": True,
        "supports_thinking": True,
        "supports_web_search": True,
        "max_context": 131072,
        "default_temperature": 0.7,
        "agent_default": "mentor",
        "release_year": 2026,
    },
    # ===== 字节豆包系列（2026 最新）=====
    {
        "id": "doubao-1.5-pro",
        "label": "Doubao 1.5 Pro (2026)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key": "",
        "pricing": {"input_cny_per_million": 0.8, "output_cny_per_million": 2},
        "supports_streaming": True,
        "supports_thinking": False,
        "supports_web_search": True,
        "max_context": 131072,
        "default_temperature": 0.7,
        "agent_default": "search",
        "release_year": 2026,
    },
]

# 各步骤默认模型映射（v8.0 更新：使用 2026 最新模型）
DEFAULT_STEP_MODELS = {
    "orchestrator": "claude-sonnet-4.5",
    "reasoner": "deepseek-r2",
    "mentor": "gpt-4.1",
    "inspire": "qwen3-max",
    "report": "claude-opus-4.5",
    "search": "deepseek-v3.2",
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
        self.ai_model: str = os.getenv("AI_MODEL", "deepseek-v3.2")
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

        # 多模型注册表与步骤路由（v7.0/v8.0 新增）
        if "models" in user_config and isinstance(user_config["models"], list):
            self.models = user_config["models"]
        if "step_models" in user_config and isinstance(
            user_config["step_models"], dict
        ):
            # 合并，保留默认键（v8.0 新增 orchestrator 键）
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
