"""论题生成路由模块

提供论题的生成、查询、详情获取与删除接口。
生成时调用 reasoner_proposal 批量生成论题并持久化到 proposals 表。
"""
import datetime
import json
import uuid

from fastapi import APIRouter, HTTPException

from backend.agents import reasoner_proposal
from backend.ai.ai_proxy import check_api_configured
from backend.database import execute_insert, fetch_all, fetch_one, execute_query
from backend.models import ApiResponse, ProposalGenerateRequest

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


def _enum_to_str(value) -> str:
    """将枚举值转换为字符串，非枚举则直接转为字符串。"""
    return value.value if hasattr(value, "value") else str(value)


def _deserialize_proposal_fields(row: dict) -> None:
    """反序列化 proposal 行中的 JSON 字段（原地修改）。

    将 research_significance 与 research_content 字段从 JSON 字符串
    还原为 dict / list。
    """
    for field in ("research_significance", "research_content"):
        raw = row.get(field)
        if isinstance(raw, str):
            try:
                row[field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                # 解析失败时保留原始字符串
                pass


@router.post("/generate")
async def generate_proposals(req: ProposalGenerateRequest) -> dict:
    """生成论题提案。

    调用 reasoner_proposal 批量生成论题，并将结果写入 proposals 表。
    若 AI 未配置则返回 400 错误。
    """
    try:
        # 检查 AI 是否已配置
        if not check_api_configured():
            raise HTTPException(
                status_code=400,
                detail="AI API Key 未配置，请在设置页配置",
            )

        # 枚举类型转换为字符串
        degree = _enum_to_str(req.degree)
        discipline = _enum_to_str(req.discipline)

        # 调用批量生成
        proposals = reasoner_proposal.generate_multiple(
            degree=degree,
            discipline=discipline,
            mentor_info=req.mentor_info,
            candidates=None,
            count=req.count,
            session_id=req.session_id,
        )

        # 将生成的论题存入数据库
        now = datetime.datetime.now().isoformat()
        for proposal in proposals:
            proposal["id"] = uuid.uuid4().hex
            proposal["session_id"] = req.session_id
            proposal["created_at"] = now
            execute_insert("proposals", proposal)

        return {
            "proposals": proposals,
            "count": len(proposals),
            "session_id": req.session_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("")
async def list_proposals(
    limit: int = 20, offset: int = 0, session_id: str = None
) -> dict:
    """分页查询论题列表，可选按会话过滤。"""
    try:
        if session_id:
            rows = fetch_all(
                "SELECT * FROM proposals WHERE session_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?;",
                (session_id, limit, offset),
            )
        else:
            rows = fetch_all(
                "SELECT * FROM proposals ORDER BY created_at DESC LIMIT ? OFFSET ?;",
                (limit, offset),
            )

        # 反序列化 JSON 字段
        for row in rows:
            _deserialize_proposal_fields(row)

        return {
            "proposals": rows,
            "count": len(rows),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/{proposal_id}")
async def get_proposal(proposal_id: str) -> dict:
    """获取单个论题详情。"""
    try:
        row = fetch_one("SELECT * FROM proposals WHERE id = ?;", (proposal_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="论题不存在")

        # 反序列化 JSON 字段
        _deserialize_proposal_fields(row)
        return row
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("/{proposal_id}")
async def delete_proposal(proposal_id: str) -> ApiResponse:
    """删除指定论题。"""
    try:
        execute_query("DELETE FROM proposals WHERE id = ?;", (proposal_id,))
        return ApiResponse(success=True, message="论题已删除")
    except Exception as e:
        return ApiResponse(success=False, error=str(e))
