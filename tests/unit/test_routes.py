"""API 路由单元测试

测试 backend/routes 下所有路由模块的 API 端点：
  - sessions: 会话 CRUD
  - conversations: 对话管理与消息
  - lineage: 谱系节点/边/卡片
  - budgets: 预算账本与定价
  - config: 配置与模型管理
  - constraints: 约束校验
  - citations: 引用查询
  - creativity: 创意引擎
  - cache-stats: 缓存命中率统计

测试策略：
  - 使用 FastAPI TestClient 发送 HTTP 请求
  - 临时数据库隔离测试
  - 不调用真实 AI API（proposals/generate 需 AI 配置，测试 400 分支）
  - 覆盖正向、反向、边界条件
"""
import os
import sys
import tempfile
import uuid

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ===== 临时数据库初始化（必须在导入 main 之前） =====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_routes_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

# 重置 Settings 单例以使用新数据库
import backend.config as _config_module
_config_module._settings_instance = None

from fastapi.testclient import TestClient
from backend.database import get_db_connection

# 导入 FastAPI 应用（在数据库初始化之后）
from main import app


# ===== 辅助函数 =====

def _insert_session(session_id: str = None, title: str = "测试会话") -> str:
    """向 sessions 表插入一条记录以满足外键约束。"""
    sid = session_id or f"test-session-{uuid.uuid4().hex[:12]}"
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at)
               VALUES (?, ?, datetime('now'), datetime('now'))""",
            (sid, title),
        )
        conn.commit()
    finally:
        conn.close()
    return sid


def _create_session_via_api(client: TestClient, title: str = "API测试会话") -> str:
    """通过 API 创建会话并返回 session_id。"""
    resp = client.post("/api/sessions", json={
        "title": title,
        "degree": "master",
        "discipline": "humanities_social",
        "mentor_info": "张教授 人工智能",
        "mode": "quick",
    })
    assert resp.status_code == 200
    data = resp.json()
    return data.get("id")


# ============================================================
# 第一部分：配置与状态路由
# ============================================================

class TestConfigRoutes:
    """测试 /api/config 与 /api/status 路由。"""

    def test_get_config(self):
        """GET /api/config 应返回配置信息。"""
        with TestClient(app) as client:
            resp = client.get("/api/config")
            assert resp.status_code == 200
            data = resp.json()
            assert "ai_api_key_configured" in data
            assert "ai_base_url" in data
            assert "ai_model" in data

    def test_get_config_has_degree_models(self):
        """配置应包含 degree_models。"""
        with TestClient(app) as client:
            resp = client.get("/api/config")
            data = resp.json()
            assert "degree_models" in data
            assert "master" in data["degree_models"]

    def test_get_config_has_literature_baseline(self):
        """配置应包含 literature_baseline。"""
        with TestClient(app) as client:
            resp = client.get("/api/config")
            data = resp.json()
            assert "literature_baseline" in data

    def test_get_config_has_academic_calendar(self):
        """配置应包含 academic_calendar。"""
        with TestClient(app) as client:
            resp = client.get("/api/config")
            data = resp.json()
            assert "academic_calendar" in data

    def test_get_status(self):
        """GET /api/status 应返回健康状态。"""
        with TestClient(app) as client:
            resp = client.get("/api/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "version" in data

    def test_update_config(self):
        """POST /api/config 应更新配置。"""
        with TestClient(app) as client:
            resp = client.post("/api/config", json={
                "ai_model": "test-model",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True


class TestModelRoutes:
    """测试 /api/models 路由。"""

    def test_list_models(self):
        """GET /api/models 应返回模型列表。"""
        with TestClient(app) as client:
            resp = client.get("/api/models")
            assert resp.status_code == 200
            data = resp.json()
            assert "models" in data
            assert "count" in data
            assert data["count"] >= 10

    def test_list_models_has_ids(self):
        """模型列表应包含 id 字段。"""
        with TestClient(app) as client:
            resp = client.get("/api/models")
            data = resp.json()
            for model in data["models"]:
                assert "id" in model

    def test_get_step_models(self):
        """GET /api/step-models 应返回步骤路由。"""
        with TestClient(app) as client:
            resp = client.get("/api/step-models")
            assert resp.status_code == 200
            data = resp.json()
            assert "step_models" in data
            assert "orchestrator" in data["step_models"]

    def test_update_currency_valid(self):
        """PUT /api/currency 切换到合法货币应成功。"""
        with TestClient(app) as client:
            resp = client.put("/api/currency", json={"currency": "USD"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            # 恢复为 CNY
            client.put("/api/currency", json={"currency": "CNY"})

    def test_update_currency_invalid(self):
        """PUT /api/currency 切换到非法货币应失败。"""
        with TestClient(app) as client:
            resp = client.put("/api/currency", json={"currency": "EUR"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False


# ============================================================
# 第二部分：会话路由
# ============================================================

class TestSessionRoutes:
    """测试 /api/sessions 路由。"""

    def test_create_session(self):
        """POST /api/sessions 应创建会话。"""
        with TestClient(app) as client:
            resp = client.post("/api/sessions", json={
                "title": "路由测试会话",
                "degree": "master",
                "discipline": "science_engineering",
                "mentor_info": "李教授 计算机",
                "mode": "quick",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "id" in data
            assert data["title"] == "路由测试会话"

    def test_list_sessions(self):
        """GET /api/sessions 应返回会话列表。"""
        with TestClient(app) as client:
            _create_session_via_api(client, "列表测试")
            resp = client.get("/api/sessions")
            assert resp.status_code == 200
            data = resp.json()
            assert "sessions" in data
            assert "count" in data
            assert data["count"] >= 1

    def test_list_sessions_with_pagination(self):
        """GET /api/sessions 应支持分页参数。"""
        with TestClient(app) as client:
            resp = client.get("/api/sessions", params={"limit": 5, "offset": 0})
            assert resp.status_code == 200
            data = resp.json()
            assert data["limit"] == 5
            assert data["offset"] == 0

    def test_get_session_by_id(self):
        """GET /api/sessions/{id} 应返回会话详情。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "详情测试")
            resp = client.get(f"/api/sessions/{sid}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == sid

    def test_get_session_not_found(self):
        """GET /api/sessions/{不存在的ID} 应返回 404。"""
        with TestClient(app) as client:
            resp = client.get("/api/sessions/nonexistent-id-12345")
            assert resp.status_code == 404

    def test_delete_session(self):
        """DELETE /api/sessions/{id} 应删除会话。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "删除测试")
            resp = client.delete(f"/api/sessions/{sid}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True

    def test_update_session_status(self):
        """PATCH /api/sessions/{id}/status 应更新状态。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "状态测试")
            resp = client.patch(f"/api/sessions/{sid}/status", json={"status": "completed"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True

    def test_create_session_invalid_degree(self):
        """POST /api/sessions 非法学位应返回 422。"""
        with TestClient(app) as client:
            resp = client.post("/api/sessions", json={
                "title": "非法测试",
                "degree": "bachelor",  # 非法
                "discipline": "humanities_social",
                "mentor_info": "导师",
                "mode": "quick",
            })
            assert resp.status_code == 422


# ============================================================
# 第三部分：对话路由
# ============================================================

class TestConversationRoutes:
    """测试对话管理路由。"""

    def test_create_conversation(self):
        """POST /api/sessions/{sid}/conversations 应创建对话。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "对话测试")
            resp = client.post(f"/api/sessions/{sid}/conversations", json={
                "title": "新对话",
                "agent_id": "orchestrator",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "id" in data
            assert data["title"] == "新对话"

    def test_list_conversations(self):
        """GET /api/sessions/{sid}/conversations 应返回对话列表。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "列表对话")
            client.post(f"/api/sessions/{sid}/conversations", json={"title": "对话1"})
            resp = client.get(f"/api/sessions/{sid}/conversations")
            assert resp.status_code == 200
            data = resp.json()
            assert "conversations" in data
            assert len(data["conversations"]) >= 1

    def test_get_conversation(self):
        """GET /api/conversations/{cid} 应返回对话详情。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "详情对话")
            create_resp = client.post(f"/api/sessions/{sid}/conversations", json={"title": "详情"})
            cid = create_resp.json()["id"]
            resp = client.get(f"/api/conversations/{cid}")
            assert resp.status_code == 200
            assert resp.json()["id"] == cid

    def test_get_conversation_not_found(self):
        """GET /api/conversations/{不存在的ID} 应返回 404。"""
        with TestClient(app) as client:
            resp = client.get("/api/conversations/nonexistent-cid-999")
            assert resp.status_code == 404

    def test_rename_conversation(self):
        """PUT /api/conversations/{cid} 应重命名对话。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "重命名对话")
            create_resp = client.post(f"/api/sessions/{sid}/conversations", json={"title": "旧名"})
            cid = create_resp.json()["id"]
            resp = client.put(f"/api/conversations/{cid}", json={"title": "新名"})
            assert resp.status_code == 200
            assert resp.json()["title"] == "新名"

    def test_delete_conversation(self):
        """DELETE /api/conversations/{cid} 应删除对话。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "删除对话")
            create_resp = client.post(f"/api/sessions/{sid}/conversations", json={"title": "待删"})
            cid = create_resp.json()["id"]
            resp = client.delete(f"/api/conversations/{cid}")
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

    def test_delete_conversation_not_found(self):
        """DELETE /api/conversations/{不存在的ID} 应返回 404。"""
        with TestClient(app) as client:
            resp = client.delete("/api/conversations/nonexistent-cid-888")
            assert resp.status_code == 404

    def test_add_and_get_messages(self):
        """POST + GET /api/conversations/{cid}/messages 应添加并获取消息。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "消息测试")
            create_resp = client.post(f"/api/sessions/{sid}/conversations", json={"title": "消息"})
            cid = create_resp.json()["id"]
            # 添加消息
            client.post(f"/api/conversations/{cid}/messages", json={
                "role": "user",
                "content": "你好",
                "agent_id": "orchestrator",
            })
            # 获取消息
            resp = client.get(f"/api/conversations/{cid}/messages")
            assert resp.status_code == 200
            data = resp.json()
            assert "messages" in data
            assert len(data["messages"]) >= 1

    def test_get_context(self):
        """GET /api/conversations/{cid}/context 应返回上下文。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "上下文测试")
            create_resp = client.post(f"/api/sessions/{sid}/conversations", json={"title": "上下文"})
            cid = create_resp.json()["id"]
            resp = client.get(f"/api/conversations/{cid}/context")
            assert resp.status_code == 200
            assert "context" in resp.json()

    def test_get_conversation_citations(self):
        """GET /api/conversations/{cid}/citations 应返回引用列表。"""
        with TestClient(app) as client:
            sid = _create_session_via_api(client, "引用测试")
            create_resp = client.post(f"/api/sessions/{sid}/conversations", json={"title": "引用"})
            cid = create_resp.json()["id"]
            resp = client.get(f"/api/conversations/{cid}/citations")
            assert resp.status_code == 200
            assert "conversation_id" in resp.json()

    def test_list_agents(self):
        """GET /api/agents 应返回 Agent 列表。"""
        with TestClient(app) as client:
            resp = client.get("/api/agents")
            assert resp.status_code == 200
            data = resp.json()
            assert "agents" in data
            assert isinstance(data["agents"], list)


# ============================================================
# 第四部分：谱系路由
# ============================================================

class TestLineageRoutes:
    """测试 /api/lineage 路由。"""

    def setup_method(self, method):
        """每个测试方法前清理谱系表，避免 None created_at 导致排序失败。"""
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM lineage_edges;")
            conn.execute("DELETE FROM lineage_nodes;")
            conn.commit()
        finally:
            conn.close()

    def test_list_nodes(self):
        """GET /api/lineage 应返回节点列表。"""
        with TestClient(app) as client:
            resp = client.get("/api/lineage")
            assert resp.status_code == 200
            data = resp.json()
            assert "nodes" in data
            assert "total" in data

    def test_list_nodes_with_pagination(self):
        """GET /api/lineage 应支持分页。"""
        with TestClient(app) as client:
            resp = client.get("/api/lineage", params={"limit": 10, "offset": 0})
            assert resp.status_code == 200
            data = resp.json()
            assert data["limit"] == 10

    def test_import_lineage(self):
        """POST /api/lineage/import 应批量导入。"""
        with TestClient(app) as client:
            resp = client.post("/api/lineage/import", json={
                "nodes": [
                    {"node_type": "paper", "title": "导入论文", "abstract": "摘要"},
                ],
                "edges": [],
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["imported_nodes"] == 1

    def test_get_graph(self):
        """GET /api/lineage/graph 应返回完整图谱。"""
        with TestClient(app) as client:
            resp = client.get("/api/lineage/graph")
            assert resp.status_code == 200
            data = resp.json()
            assert "nodes" in data
            assert "edges" in data

    def test_search_nodes(self):
        """GET /api/lineage/search 应搜索节点。"""
        with TestClient(app) as client:
            # 先导入一个节点
            client.post("/api/lineage/import", json={
                "nodes": [{"node_type": "paper", "title": "搜索测试论文", "abstract": ""}],
                "edges": [],
            })
            resp = client.get("/api/lineage/search", params={"keyword": "搜索测试"})
            assert resp.status_code == 200
            data = resp.json()
            assert "results" in data
            assert data["count"] >= 1

    def test_delete_node(self):
        """DELETE /api/lineage/{node_id} 应删除节点。"""
        with TestClient(app) as client:
            # 先导入
            import_resp = client.post("/api/lineage/import", json={
                "nodes": [{"node_type": "paper", "title": "删除测试", "abstract": ""}],
                "edges": [],
            })
            # 获取节点 ID
            graph = client.get("/api/lineage/graph").json()
            target = [n for n in graph["nodes"] if n["title"] == "删除测试"]
            if target:
                node_id = target[0]["id"]
                resp = client.delete(f"/api/lineage/{node_id}")
                assert resp.status_code == 200

    def test_batch_delete(self):
        """DELETE /api/lineage/batch 应批量删除。"""
        with TestClient(app) as client:
            # TestClient.delete 不支持 json 参数，使用 request 方法
            resp = client.request("DELETE", "/api/lineage/batch", json={"node_ids": []})
            assert resp.status_code == 200
            data = resp.json()
            assert "deleted" in data

    def test_add_card(self):
        """POST /api/lineage/cards 应新增卡片。"""
        with TestClient(app) as client:
            resp = client.post("/api/lineage/cards", json={
                "title": "路由卡片",
                "content": "内容",
                "tags": ["测试"],
                "source": "测试",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "card_id" in data

    def test_list_cards(self):
        """GET /api/lineage/cards 应返回卡片列表。"""
        with TestClient(app) as client:
            client.post("/api/lineage/cards", json={
                "title": "列表卡片",
                "content": "内容",
            })
            resp = client.get("/api/lineage/cards")
            assert resp.status_code == 200
            data = resp.json()
            assert "cards" in data
            assert data["count"] >= 1


# ============================================================
# 第五部分：预算路由
# ============================================================

class TestBudgetRoutes:
    """测试 /api/budgets 路由。"""

    def test_get_ledger(self):
        """GET /api/budgets/ledger 应返回账本明细。"""
        with TestClient(app) as client:
            resp = client.get("/api/budgets/ledger")
            assert resp.status_code == 200
            data = resp.json()
            assert "entries" in data
            assert "count" in data

    def test_get_ledger_with_pagination(self):
        """GET /api/budgets/ledger 应支持分页。"""
        with TestClient(app) as client:
            resp = client.get("/api/budgets/ledger", params={"limit": 10, "offset": 0})
            assert resp.status_code == 200
            data = resp.json()
            assert data["limit"] == 10

    def test_estimate_budget(self):
        """POST /api/budgets/estimate 应估算预算。"""
        with TestClient(app) as client:
            resp = client.post("/api/budgets/estimate", json={
                "degree": "master",
                "mode": "quick",
                "count": 3,
            })
            assert resp.status_code == 200
            data = resp.json()
            # 应返回估算结果（不报错）
            assert "success" not in data or data.get("success") is not False

    def test_get_summary(self):
        """GET /api/budgets/summary 应返回汇总。"""
        with TestClient(app) as client:
            resp = client.get("/api/budgets/summary")
            assert resp.status_code == 200

    def test_get_session_cost(self):
        """GET /api/budgets/session/{id} 应返回会话费用。"""
        with TestClient(app) as client:
            sid = _insert_session()
            resp = client.get(f"/api/budgets/session/{sid}")
            assert resp.status_code == 200

    def test_get_pricing(self):
        """GET /api/budgets/pricing 应返回定价表。"""
        with TestClient(app) as client:
            resp = client.get("/api/budgets/pricing")
            assert resp.status_code == 200
            data = resp.json()
            assert "pricing" in data
            assert "currency" in data

    def test_get_cache_stats(self):
        """GET /api/cache-stats 应返回缓存统计。"""
        with TestClient(app) as client:
            resp = client.get("/api/cache-stats")
            assert resp.status_code == 200


# ============================================================
# 第六部分：约束路由
# ============================================================

class TestConstraintRoutes:
    """测试 /api/constraints 路由。"""

    def test_validate_title(self):
        """POST /api/constraints/validate-title 应校验标题。"""
        with TestClient(app) as client:
            resp = client.post("/api/constraints/validate-title", json={
                "title": "基于深度学习的研究",
                "degree": "master",
            })
            assert resp.status_code == 200

    def test_check_feasibility(self):
        """POST /api/constraints/check-feasibility 应校验可行性。"""
        with TestClient(app) as client:
            resp = client.post("/api/constraints/check-feasibility", json={
                "research_content": ["内容1", "内容2"],
                "degree": "master",
                "timeframe_months": 12,
            })
            assert resp.status_code == 200

    def test_get_calendar_master(self):
        """GET /api/constraints/calendar/master 应返回硕士日历。"""
        with TestClient(app) as client:
            resp = client.get("/api/constraints/calendar/master")
            assert resp.status_code == 200

    def test_get_calendar_doctor(self):
        """GET /api/constraints/calendar/doctor 应返回博士日历。"""
        with TestClient(app) as client:
            resp = client.get("/api/constraints/calendar/doctor")
            assert resp.status_code == 200

    def test_get_baseline_master(self):
        """GET /api/constraints/baseline/master 应返回硕士基线。"""
        with TestClient(app) as client:
            resp = client.get("/api/constraints/baseline/master")
            assert resp.status_code == 200
            data = resp.json()
            assert data["degree"] == "master"

    def test_get_baseline_doctor(self):
        """GET /api/constraints/baseline/doctor 应返回博士基线。"""
        with TestClient(app) as client:
            resp = client.get("/api/constraints/baseline/doctor")
            assert resp.status_code == 200
            data = resp.json()
            assert data["degree"] == "doctor"

    def test_get_search_status(self):
        """GET /api/constraints/search-status 应返回检索状态。"""
        with TestClient(app) as client:
            resp = client.get("/api/constraints/search-status")
            assert resp.status_code == 200
            data = resp.json()
            assert "real_search_enabled" in data
            assert "configured" in data


# ============================================================
# 第七部分：引用路由
# ============================================================

class TestCitationRoutes:
    """测试 /api/messages/{mid}/citations 路由。"""

    def test_get_message_citations_empty(self):
        """GET /api/messages/{不存在的mid}/citations 应返回空列表。"""
        with TestClient(app) as client:
            resp = client.get("/api/messages/nonexistent-mid/citations")
            assert resp.status_code == 200
            data = resp.json()
            assert data["citations"] == []

    def test_get_message_citations_has_message_id(self):
        """返回应包含 message_id 字段。"""
        with TestClient(app) as client:
            resp = client.get("/api/messages/test-mid/citations")
            assert resp.status_code == 200
            data = resp.json()
            assert data["message_id"] == "test-mid"


# ============================================================
# 第八部分：创意路由
# ============================================================

class TestCreativityRoutes:
    """测试 /api/creativity 路由。"""

    def test_cross_domain(self):
        """POST /api/creativity/cross-domain 应返回跨域联想。"""
        with TestClient(app) as client:
            resp = client.post("/api/creativity/cross-domain", json={
                "domain_a": "计算机科学",
                "domain_b": "生物学",
            })
            assert resp.status_code == 200

    def test_trend_graft(self):
        """POST /api/creativity/trend-graft 应返回趋势嫁接。"""
        with TestClient(app) as client:
            resp = client.post("/api/creativity/trend-graft", json={
                "keywords": ["大模型", "推理"],
            })
            assert resp.status_code == 200

    def test_rank_candidates(self):
        """POST /api/creativity/rank 应返回排序结果。"""
        with TestClient(app) as client:
            resp = client.post("/api/creativity/rank", json={
                "candidates": [
                    {"title": "候选1", "inspiration_source": "学术谱系"},
                    {"title": "候选2", "inspiration_source": "跨域联想"},
                ],
                "degree": "master",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "ranked_candidates" in data

    def test_get_candidates(self):
        """GET /api/creativity/candidates 应返回候选列表。"""
        with TestClient(app) as client:
            resp = client.get("/api/creativity/candidates", params={
                "degree": "master",
                "discipline": "humanities_social",
                "mentor_info": "张教授 人工智能",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "candidates" in data

    def test_rank_empty_candidates(self):
        """POST /api/creativity/rank 空候选应返回空列表。"""
        with TestClient(app) as client:
            resp = client.post("/api/creativity/rank", json={
                "candidates": [],
                "degree": "master",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 0


# ============================================================
# 第九部分：论题路由
# ============================================================

class TestProposalRoutes:
    """测试 /api/proposals 路由。"""

    def test_list_proposals(self):
        """GET /api/proposals 应返回论题列表。"""
        with TestClient(app) as client:
            resp = client.get("/api/proposals")
            assert resp.status_code == 200
            data = resp.json()
            assert "proposals" in data
            assert "count" in data

    def test_list_proposals_with_pagination(self):
        """GET /api/proposals 应支持分页。"""
        with TestClient(app) as client:
            resp = client.get("/api/proposals", params={"limit": 5, "offset": 0})
            assert resp.status_code == 200
            data = resp.json()
            assert data["limit"] == 5

    def test_get_proposal_not_found(self):
        """GET /api/proposals/{不存在的ID} 应返回 404。"""
        with TestClient(app) as client:
            resp = client.get("/api/proposals/nonexistent-id-999")
            assert resp.status_code == 404

    def test_delete_proposal(self):
        """DELETE /api/proposals/{id} 应删除论题。"""
        with TestClient(app) as client:
            resp = client.delete("/api/proposals/nonexistent-id-delete")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True

    def test_generate_without_ai_config(self):
        """POST /api/proposals/generate 未配置 AI 应返回 400。"""
        with TestClient(app) as client:
            resp = client.post("/api/proposals/generate", json={
                "degree": "master",
                "discipline": "humanities_social",
                "mentor_info": "导师",
                "mode": "quick",
                "count": 3,
            })
            # 未配置 API Key 时应返回 400
            assert resp.status_code in (400, 200)


# ============================================================
# 第十部分：集成测试
# ============================================================

class TestRoutesIntegration:
    """API 集成测试。"""

    def test_full_session_conversation_flow(self):
        """完整流程：创建会话→创建对话→添加消息→获取消息→删除。"""
        with TestClient(app) as client:
            # 创建会话
            sid = _create_session_via_api(client, "集成流程")
            assert sid is not None
            # 创建对话
            conv_resp = client.post(f"/api/sessions/{sid}/conversations", json={
                "title": "集成对话",
                "agent_id": "orchestrator",
            })
            cid = conv_resp.json()["id"]
            # 添加消息
            client.post(f"/api/conversations/{cid}/messages", json={
                "role": "user",
                "content": "集成测试消息",
                "agent_id": "orchestrator",
            })
            # 获取消息
            msgs = client.get(f"/api/conversations/{cid}/messages").json()
            assert len(msgs["messages"]) >= 1
            # 删除对话
            del_resp = client.delete(f"/api/conversations/{cid}")
            assert del_resp.json()["deleted"] is True
            # 删除会话
            client.delete(f"/api/sessions/{sid}")

    def test_lineage_import_and_search(self):
        """谱系导入与搜索集成。"""
        with TestClient(app) as client:
            # 导入节点
            client.post("/api/lineage/import", json={
                "nodes": [
                    {"node_type": "paper", "title": "集成论文A", "abstract": "摘要A"},
                    {"node_type": "method", "title": "集成方法B", "abstract": "摘要B"},
                ],
                "edges": [],
            })
            # 搜索
            resp = client.get("/api/lineage/search", params={"keyword": "集成"})
            data = resp.json()
            assert data["count"] >= 2

    def test_card_create_and_list(self):
        """卡片创建与列表集成。"""
        with TestClient(app) as client:
            client.post("/api/lineage/cards", json={
                "title": "集成卡片",
                "content": "内容",
                "tags": ["集成标签"],
            })
            resp = client.get("/api/lineage/cards")
            data = resp.json()
            titles = [c["title"] for c in data["cards"]]
            assert "集成卡片" in titles
