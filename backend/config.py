"""配置管理模块

负责加载 .env 环境变量与 data/config.json 用户配置，
提供全局单例 Settings 与按学位分级的模型路由常量。
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 文件（若存在）
load_dotenv()

# 用户配置文件路径
CONFIG_FILE_PATH = "data/config.json"


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
        self.ai_model: str = os.getenv("AI_MODEL", "gpt-4o-mini")
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


# 单例缓存
_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """返回全局 Settings 单例。"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


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
