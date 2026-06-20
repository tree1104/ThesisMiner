"""配置与状态路由模块

提供配置查询、更新与服务健康状态检查接口。
v7.0 新增模型管理、步骤路由与货币切换接口。
v9.0 模型管理接口返回统一的能力开关字段（capabilities）。
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.ai.ai_proxy import check_api_configured
from backend.config import (
    ACADEMIC_CALENDAR,
    DEGREE_MODELS,
    LITERATURE_BASELINE,
    get_model_config,
    get_settings,
    get_step_model,
    save_config,
)
from backend.models import ApiResponse, ConfigUpdate

router = APIRouter(prefix="/api", tags=["config"])


# ---------------- v7.0 模型管理请求模型 ----------------


class ModelConfig(BaseModel):
    """模型配置请求体。"""

    id: str
    label: str = ""
    name: str = ""
    provider: str = ""
    base_url: str = ""
    api_key: str = ""
    pricing: dict = Field(
        default_factory=lambda: {
            "input_cny_per_million": 0,
            "output_cny_per_million": 0,
        }
    )
    context_length: int = 0
    capabilities: dict = Field(
        default_factory=lambda: {
            "deep_thinking": False,
            "web_search": False,
            "streaming": True,
        }
    )
    agent_default: str = ""
    release_year: int = 0
    supports_streaming: bool = True
    supports_thinking: bool = False
    supports_web_search: bool = False
    max_context: int = 32768
    default_temperature: float = 0.7


class StepModelsUpdate(BaseModel):
    """步骤路由更新请求体。"""

    reasoner: Optional[str] = None
    mentor: Optional[str] = None
    inspire: Optional[str] = None
    report: Optional[str] = None
    search: Optional[str] = None


class CurrencyUpdate(BaseModel):
    """货币切换请求体。"""

    currency: str  # "CNY" or "USD"


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
            "currency": settings.currency,
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
            "version": "7.0.0",
            "rag_enabled": False,
            "ai_configured": check_api_configured(),
        }
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


# ---------------- v7.0 模型管理接口 ----------------


def _normalize_model_for_response(model: dict) -> dict:
    """将模型配置字典归一化为 GET /api/models 响应条目（v9.0）。

    统一字段命名并补全 capabilities 字段：优先使用已有的 capabilities 字典，
    若缺失则从旧字段别名（supports_thinking/supports_web_search/supports_streaming）回退构造。

    Args:
        model: 原始模型配置字典。

    Returns:
        归一化后的模型字典，至少包含 id/name/provider/pricing/context_length/
        capabilities/agent_default/release_year 字段。
    """
    capabilities = model.get("capabilities")
    if not isinstance(capabilities, dict):
        capabilities = {
            "deep_thinking": bool(model.get("supports_thinking", False)),
            "web_search": bool(model.get("supports_web_search", False)),
            "streaming": bool(model.get("supports_streaming", True)),
        }
    else:
        # 补全可能缺失的键
        capabilities = {
            "deep_thinking": bool(
                capabilities.get(
                    "deep_thinking", model.get("supports_thinking", False)
                )
            ),
            "web_search": bool(
                capabilities.get(
                    "web_search", model.get("supports_web_search", False)
                )
            ),
            "streaming": bool(
                capabilities.get(
                    "streaming", model.get("supports_streaming", True)
                )
            ),
        }

    return {
        "id": model.get("id", ""),
        "name": model.get("name", model.get("label", "")),
        "provider": model.get("provider", ""),
        "pricing": model.get("pricing", {}),
        "context_length": model.get(
            "context_length", model.get("max_context", 0)
        ),
        "capabilities": capabilities,
        "agent_default": model.get("agent_default", ""),
        "release_year": model.get("release_year", 0),
    }


@router.get("/models")
async def list_models() -> dict:
    """获取所有模型配置（v9.0 返回统一的能力开关字段）。

    每个模型条目包含：id、name、provider、pricing、context_length、
    capabilities、agent_default、release_year。
    """
    settings = get_settings()
    normalized_models = [
        _normalize_model_for_response(m) for m in settings.models
    ]
    return {"models": normalized_models, "count": len(normalized_models)}


@router.post("/models")
async def add_model(model: ModelConfig) -> dict:
    """新增模型。"""
    settings = get_settings()
    # 检查 ID 是否已存在
    for m in settings.models:
        if m.get("id") == model.id:
            return {"success": False, "error": f"模型 ID '{model.id}' 已存在"}
    # 添加模型
    new_model = model.model_dump()
    settings.models.append(new_model)
    save_config({"models": settings.models})
    return {"success": True, "model": new_model}


@router.put("/models/{model_id}")
async def update_model(model_id: str, model: ModelConfig) -> dict:
    """更新模型配置。"""
    settings = get_settings()
    for i, m in enumerate(settings.models):
        if m.get("id") == model_id:
            # 更新对应位置的模型配置
            updated = model.model_dump()
            settings.models[i] = updated
            save_config({"models": settings.models})
            return {"success": True, "model": updated}
    return {"success": False, "error": f"模型 '{model_id}' 不存在"}


@router.delete("/models/{model_id}")
async def delete_model(model_id: str) -> dict:
    """删除模型（若为步骤路由当前使用则拒绝）。"""
    settings = get_settings()
    # 检查是否被步骤路由使用
    for purpose, mid in settings.step_models.items():
        if mid == model_id:
            return {
                "success": False,
                "error": f"模型 '{model_id}' 正被步骤 '{purpose}' 使用，无法删除",
            }
    # 删除模型
    original_len = len(settings.models)
    settings.models = [m for m in settings.models if m.get("id") != model_id]
    if len(settings.models) == original_len:
        return {"success": False, "error": f"模型 '{model_id}' 不存在"}
    save_config({"models": settings.models})
    return {"success": True, "message": f"模型 '{model_id}' 已删除"}


@router.get("/step-models")
async def get_step_models() -> dict:
    """获取步骤路由配置。"""
    settings = get_settings()
    return {"step_models": settings.step_models}


@router.put("/step-models")
async def update_step_models(req: StepModelsUpdate) -> dict:
    """更新步骤路由配置。"""
    settings = get_settings()
    # 仅更新非 None 的字段
    update_data = req.model_dump(exclude_none=True)
    for purpose, model_id in update_data.items():
        # 验证模型存在
        if not get_model_config(model_id):
            return {
                "success": False,
                "error": f"模型 '{model_id}' 不存在，无法用于步骤 '{purpose}'",
            }
        settings.step_models[purpose] = model_id
    save_config({"step_models": settings.step_models})
    return {"success": True, "step_models": settings.step_models}


@router.put("/currency")
async def update_currency(req: CurrencyUpdate) -> dict:
    """切换计价货币。"""
    if req.currency not in ("CNY", "USD"):
        return {"success": False, "error": "货币仅支持 CNY 或 USD"}
    save_config({"currency": req.currency})
    return {"success": True, "currency": req.currency}
