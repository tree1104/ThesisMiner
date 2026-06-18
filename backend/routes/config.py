"""配置与状态路由模块

提供配置查询、更新与服务健康状态检查接口。
"""
from fastapi import APIRouter

from backend.ai.ai_proxy import check_api_configured
from backend.config import (
    ACADEMIC_CALENDAR,
    DEGREE_MODELS,
    LITERATURE_BASELINE,
    get_settings,
    save_config,
)
from backend.models import ApiResponse, ConfigUpdate

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def get_config():
    """返回当前配置，隐藏 ai_api_key 仅显示是否已配置。"""
    try:
        settings = get_settings()
        return {
            "ai_api_key_configured": bool(settings.ai_api_key),
            "ai_base_url": settings.ai_base_url,
            "ai_model": settings.ai_model,
            "db_path": settings.db_path,
            "log_level": settings.log_level,
            "flask_env": settings.flask_env,
            "degree_models": DEGREE_MODELS,
            "literature_baseline": LITERATURE_BASELINE,
            "academic_calendar": ACADEMIC_CALENDAR,
        }
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/config")
def update_config(payload: ConfigUpdate):
    """更新配置并持久化到 data/config.json。"""
    try:
        # 仅保存非空字段，避免覆盖已有配置
        update_dict = payload.model_dump(exclude_none=True)
        save_config(update_dict)
        return ApiResponse(success=True, message="配置已更新")
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.get("/status")
def get_status():
    """返回服务健康状态。"""
    try:
        return {
            "status": "ok",
            "version": "6.0.0",
            "rag_enabled": False,
            "ai_configured": check_api_configured(),
        }
    except Exception as e:
        return ApiResponse(success=False, error=str(e))
