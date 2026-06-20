"""集成测试：v8 API 端点全覆盖验证

覆盖所有 v8 API 端点，使用 FastAPI TestClient 进行测试：
- 配置接口：GET/POST /api/config, GET /api/status, GET/POST/PUT/DELETE /api/models
- 谱系接口：GET /api/lineage, POST /api/lineage/import, GET /api/lineage/graph
- 创意接口：POST /api/creativity/inspire, POST /api/creativity/cross-domain
- 论题接口：GET /api/proposals, GET /api/proposals/{id}
- 约束接口：POST /api/constraints/validate-title, GET /api/constraints/calendar/{degree}
- 会话接口：POST/GET /api/sessions, GET/DELETE /api/sessions/{id}
- 预算接口：GET /api/budgets/ledger, GET /api/budgets/summary
- 缓存接口：GET /api/cache-stats
- 引用接口：GET /api/messages/{mid}/citations
- 对话接口：POST/GET /api/sessions/{sid}/conversations, GET/PUT/DELETE /api/conversations/{cid}
- Agent 接口：GET /api/agents

运行方式：python -m pytest tests/integration/test_api_endpoints.py -v
"""
import os
import sys
import tempfile

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 在导入 backend 模块前，切换到临时数据库
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_api_test_")
_tmp_db = os.path.join(_tmp_dir, "test_api.db")
_db.DB_PATH = _tmp_db
_db.init_db()

from fastapi.testclient import TestClient
from main import app
from backend.sessions import session_manager
from backend.models import SessionCreate, DegreeType, DisciplineType

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_db_path():
    """确保每个测试使用本文件的临时数据库。

    多个测试文件在模块导入时各自设置 _db.DB_PATH，后导入的文件会覆盖先前的设置。
    此夹具在每个测试运行前重新将 DB_PATH 指向本文件的临时数据库，确保数据隔离。
    测试结束后恢复原始值，避免影响其他测试文件。
    """
    _original_path = _db.DB_PATH
    _db.DB_PATH = _tmp_db
    yield
    _db.DB_PATH = _original_path


# ===== 辅助函数 =====

def _create_test_session(title: str = "API测试会话") -> str:
    """创建测试会话，返回 session_id"""
    req = SessionCreate(
        title=title,
        degree=DegreeType.master,
        discipline=DisciplineType.science_engineering,
        mentor_info="API测试导师",
    )
    session = session_manager.create_session(req)
    return session["id"]


def _create_test_conversation(session_id: str, title: str = "API测试对话") -> str:
    """创建测试对话，返回 conversation_id"""
    response = client.post(
        f"/api/sessions/{session_id}/conversations",
        json={"title": title, "agent_id": "orchestrator"},
    )
    data = response.json()
    return data["id"]


# ===== 配置接口测试 =====

class TestConfigEndpoints:
    """配置接口测试"""

    def test_get_config(self):
        """测试获取配置"""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "ai_api_key_configured" in data
        assert "ai_base_url" in data
        assert "ai_model" in data
        assert "degree_models" in data
        assert "literature_baseline" in data
        assert "academic_calendar" in data

    def test_get_status(self):
        """测试获取服务状态"""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "ai_configured" in data

    def test_get_models(self):
        """测试获取模型列表"""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "count" in data
        assert isinstance(data["models"], list)

    def test_get_step_models(self):
        """测试获取步骤路由配置"""
        response = client.get("/api/step-models")
        assert response.status_code == 200
        data = response.json()
        assert "step_models" in data


# ===== 谱系接口测试 =====

class TestLineageEndpoints:
    """谱系接口测试"""

    def test_list_lineage_nodes(self):
        """测试列出谱系节点"""
        response = client.get("/api/lineage")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "count" in data
        assert "total" in data

    def test_list_lineage_with_pagination(self):
        """测试谱系节点分页"""
        response = client.get("/api/lineage?limit=5&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 0

    def test_import_lineage_nodes(self):
        """测试导入谱系节点"""
        payload = {
            "nodes": [
                {
                    "node_type": "mentor_project",
                    "title": "国家自然科学基金项目",
                    "abstract": "深度学习医学影像研究",
                    "metadata": {"year": 2024},
                },
                {
                    "node_type": "student_thesis",
                    "title": "基于CNN的检测系统",
                    "abstract": "卷积神经网络目标检测",
                    "metadata": {"year": 2023, "degree": "master"},
                },
            ],
            "edges": [],
        }
        response = client.post("/api/lineage/import", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["imported_nodes"] == 2

    def test_get_lineage_graph(self):
        """测试获取完整图谱"""
        response = client.get("/api/lineage/graph")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

    def test_search_lineage_nodes(self):
        """测试搜索谱系节点"""
        # 先导入节点
        client.post(
            "/api/lineage/import",
            json={
                "nodes": [
                    {
                        "node_type": "topic",
                        "title": "深度学习图像识别",
                        "abstract": "使用深度学习进行图像识别",
                        "metadata": {},
                    },
                ],
                "edges": [],
            },
        )
        response = client.get("/api/lineage/search?keyword=深度学习")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "count" in data

    def test_batch_delete_lineage_nodes(self):
        """测试批量删除谱系节点"""
        # DELETE 请求不支持 json 参数，使用 request 方法
        response = client.request(
            "DELETE", "/api/lineage/batch", json={"node_ids": []}
        )
        assert response.status_code == 200

    def test_lineage_cards(self):
        """测试知识卡片接口"""
        # 新增卡片
        response = client.post(
            "/api/lineage/cards",
            json={
                "title": "测试卡片",
                "content": "卡片内容",
                "tags": ["测试"],
                "source": "API测试",
            },
        )
        assert response.status_code == 200
        # 列出卡片
        response = client.get("/api/lineage/cards")
        assert response.status_code == 200
        data = response.json()
        assert "cards" in data
        assert "count" in data


# ===== 创意接口测试 =====

class TestCreativityEndpoints:
    """创意接口测试"""

    def test_creativity_inspire(self):
        """测试激发创意"""
        response = client.post(
            "/api/creativity/inspire",
            json={
                "degree": "master",
                "discipline": "science_engineering",
                "mentor_info": "深度学习",
                "context": "",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # 接口应返回候选列表或错误信息
        assert "candidates" in data or "success" in data

    def test_creativity_cross_domain(self):
        """测试跨域联想"""
        response = client.post(
            "/api/creativity/cross-domain",
            json={"domain_a": "计算机科学", "domain_b": "生物学"},
        )
        assert response.status_code == 200

    def test_creativity_trend_graft(self):
        """测试趋势嫁接"""
        response = client.post(
            "/api/creativity/trend-graft",
            json={"keywords": ["深度学习", "图神经网络"]},
        )
        assert response.status_code == 200

    def test_creativity_rank(self):
        """测试候选排序"""
        response = client.post(
            "/api/creativity/rank",
            json={
                "candidates": [
                    {"title": "候选1", "inspiration_source": "来源1"},
                    {"title": "候选2", "inspiration_source": "来源2"},
                ],
                "degree": "master",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "ranked_candidates" in data
        assert "count" in data

    def test_creativity_candidates(self):
        """测试获取示例候选"""
        response = client.get(
            "/api/creativity/candidates?degree=master&discipline=science_engineering&mentor_info=深度学习"
        )
        assert response.status_code == 200
        data = response.json()
        assert "candidates" in data


# ===== 约束接口测试 =====

class TestConstraintsEndpoints:
    """约束接口测试"""

    def test_validate_title(self):
        """测试标题格式校验"""
        response = client.post(
            "/api/constraints/validate-title",
            json={"title": "基于深度学习的图像识别研究", "degree": "master"},
        )
        assert response.status_code == 200

    def test_check_feasibility(self):
        """测试可行性校验"""
        response = client.post(
            "/api/constraints/check-feasibility",
            json={
                "degree": "master",
                "timeframe_months": 12,
                "research_content": ["文献调研", "实验设计", "数据分析"],
            },
        )
        assert response.status_code == 200

    def test_check_literature(self):
        """测试文献基线校验"""
        response = client.post(
            "/api/constraints/check-literature",
            json={"degree": "master", "count": 30},
        )
        assert response.status_code == 200

    def test_search_status(self):
        """测试检索状态查询"""
        response = client.get("/api/constraints/search-status")
        assert response.status_code == 200
        data = response.json()
        assert "real_search_enabled" in data
        assert "configured" in data

    def test_get_calendar(self):
        """测试获取学术日历"""
        response = client.get("/api/constraints/calendar/master")
        assert response.status_code == 200

    def test_get_baseline(self):
        """测试获取文献基线"""
        response = client.get("/api/constraints/baseline/master")
        assert response.status_code == 200
        data = response.json()
        assert "degree" in data
        assert "baseline" in data


# ===== 会话接口测试 =====

class TestSessionEndpoints:
    """会话接口测试"""

    def test_create_session(self):
        """测试创建会话"""
        response = client.post(
            "/api/sessions",
            json={
                "title": "API测试会话",
                "degree": "master",
                "discipline": "science_engineering",
                "mentor_info": "测试导师",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "API测试会话"

    def test_list_sessions(self):
        """测试列出会话"""
        # 先创建一个会话
        _create_test_session("列表测试会话")
        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "count" in data
        assert isinstance(data["sessions"], list)

    def test_list_sessions_with_pagination(self):
        """测试会话列表分页"""
        response = client.get("/api/sessions?limit=5&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 0

    def test_get_session(self):
        """测试获取会话详情"""
        sid = _create_test_session("详情测试会话")
        response = client.get(f"/api/sessions/{sid}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sid

    def test_get_session_not_found(self):
        """测试获取不存在的会话返回 404"""
        response = client.get("/api/sessions/nonexistent-session-id")
        assert response.status_code == 404

    def test_delete_session(self):
        """测试删除会话"""
        sid = _create_test_session("删除测试会话")
        response = client.delete(f"/api/sessions/{sid}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_session_status(self):
        """测试更新会话状态"""
        sid = _create_test_session("状态更新测试会话")
        response = client.patch(
            f"/api/sessions/{sid}/status",
            json={"status": "completed"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ===== 对话接口测试 =====

class TestConversationEndpoints:
    """对话接口测试"""

    def test_create_conversation(self):
        """测试创建对话"""
        sid = _create_test_session("对话创建测试")
        response = client.post(
            f"/api/sessions/{sid}/conversations",
            json={"title": "新对话", "agent_id": "orchestrator"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "新对话"

    def test_list_conversations(self):
        """测试列出对话"""
        sid = _create_test_session("对话列表测试")
        _create_test_conversation(sid, "对话1")
        response = client.get(f"/api/sessions/{sid}/conversations")
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data
        assert len(data["conversations"]) >= 1

    def test_get_conversation(self):
        """测试获取对话详情"""
        sid = _create_test_session("对话详情测试")
        cid = _create_test_conversation(sid, "详情对话")
        response = client.get(f"/api/conversations/{cid}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cid

    def test_get_conversation_not_found(self):
        """测试获取不存在的对话返回 404"""
        response = client.get("/api/conversations/nonexistent-conv-id")
        assert response.status_code == 404

    def test_rename_conversation(self):
        """测试重命名对话"""
        sid = _create_test_session("对话重命名测试")
        cid = _create_test_conversation(sid, "原名称")
        response = client.put(
            f"/api/conversations/{cid}",
            json={"title": "新名称"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "新名称"

    def test_delete_conversation(self):
        """测试删除对话"""
        sid = _create_test_session("对话删除测试")
        cid = _create_test_conversation(sid, "待删除对话")
        response = client.delete(f"/api/conversations/{cid}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

    def test_delete_conversation_not_found(self):
        """测试删除不存在的对话返回 404"""
        response = client.delete("/api/conversations/nonexistent-conv-id")
        assert response.status_code == 404

    def test_add_message_to_conversation(self):
        """测试添加消息到对话"""
        sid = _create_test_session("消息添加测试")
        cid = _create_test_conversation(sid, "消息对话")
        response = client.post(
            f"/api/conversations/{cid}/messages",
            json={
                "role": "user",
                "content": "测试消息内容",
                "agent_id": "orchestrator",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    def test_get_conversation_messages(self):
        """测试获取对话消息列表"""
        sid = _create_test_session("消息列表测试")
        cid = _create_test_conversation(sid, "消息列表对话")
        # 添加消息
        client.post(
            f"/api/conversations/{cid}/messages",
            json={"role": "user", "content": "消息1", "agent_id": "orchestrator"},
        )
        client.post(
            f"/api/conversations/{cid}/messages",
            json={"role": "assistant", "content": "回复1", "agent_id": "orchestrator"},
        )
        response = client.get(f"/api/conversations/{cid}/messages")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) >= 2

    def test_get_conversation_context(self):
        """测试获取对话上下文窗口"""
        sid = _create_test_session("上下文窗口测试")
        cid = _create_test_conversation(sid, "上下文对话")
        client.post(
            f"/api/conversations/{cid}/messages",
            json={"role": "user", "content": "上下文测试", "agent_id": "orchestrator"},
        )
        response = client.get(f"/api/conversations/{cid}/context?max_tokens=4000")
        assert response.status_code == 200
        data = response.json()
        assert "context" in data

    def test_set_active_conversation(self):
        """测试设置激活对话"""
        sid = _create_test_session("激活对话测试")
        cid = _create_test_conversation(sid, "激活对话")
        response = client.put(
            f"/api/sessions/{sid}/active-conversation",
            params={"cid": cid},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["active_conversation_id"] == cid

    def test_get_conversation_citations(self):
        """测试获取对话引用"""
        sid = _create_test_session("对话引用测试")
        cid = _create_test_conversation(sid, "引用对话")
        response = client.get(f"/api/conversations/{cid}/citations")
        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert "citations" in data


# ===== Agent 接口测试 =====

class TestAgentEndpoints:
    """Agent 接口测试"""

    def test_list_agents(self):
        """测试列出所有 Agent"""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)

    def test_list_agents_has_metadata(self):
        """测试 Agent 列表含元数据字段"""
        response = client.get("/api/agents")
        data = response.json()
        if len(data["agents"]) > 0:
            agent = data["agents"][0]
            assert "id" in agent
            assert "name" in agent


# ===== 预算接口测试 =====

class TestBudgetEndpoints:
    """预算接口测试"""

    def test_get_ledger(self):
        """测试获取账本明细"""
        response = client.get("/api/budgets/ledger")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "count" in data

    def test_get_ledger_with_pagination(self):
        """测试账本分页"""
        response = client.get("/api/budgets/ledger?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_get_summary(self):
        """测试获取账本汇总"""
        response = client.get("/api/budgets/summary")
        assert response.status_code == 200

    def test_get_pricing(self):
        """测试获取模型定价表"""
        response = client.get("/api/budgets/pricing")
        assert response.status_code == 200
        data = response.json()
        assert "pricing" in data
        assert "currency" in data

    def test_estimate_budget(self):
        """测试预算估算"""
        response = client.post(
            "/api/budgets/estimate",
            json={
                "degree": "master",
                "mode": "quick",
                "count": 5,
            },
        )
        assert response.status_code == 200

    def test_get_session_cost(self):
        """测试获取会话费用"""
        sid = _create_test_session("费用测试会话")
        response = client.get(f"/api/budgets/session/{sid}")
        assert response.status_code == 200


# ===== 缓存统计接口测试 =====

class TestCacheStatsEndpoint:
    """缓存统计接口测试"""

    def test_get_cache_stats(self):
        """测试获取缓存统计"""
        response = client.get("/api/cache-stats")
        assert response.status_code == 200
        data = response.json()
        assert "avg_hit_rate" in data
        assert "total_calls" in data
        assert "total_cached" in data
        assert "total_prompt" in data

    def test_cache_stats_returns_valid_types(self):
        """测试缓存统计返回有效类型"""
        response = client.get("/api/cache-stats")
        data = response.json()
        assert isinstance(data["avg_hit_rate"], (int, float))
        assert isinstance(data["total_calls"], int)
        assert isinstance(data["total_cached"], int)
        assert isinstance(data["total_prompt"], int)


# ===== 引用接口测试 =====

class TestCitationEndpoints:
    """引用接口测试"""

    def test_get_message_citations(self):
        """测试获取消息引用"""
        # 先创建会话、对话、消息
        sid = _create_test_session("引用接口测试")
        cid = _create_test_conversation(sid, "引用对话")
        msg_response = client.post(
            f"/api/conversations/{cid}/messages",
            json={
                "role": "assistant",
                "content": "参见 [示例](https://example.com)",
                "agent_id": "searcher",
                "citations": [
                    {
                        "url": "https://example.com",
                        "title": "示例文献",
                        "snippet": "示例摘要",
                        "source_domain": "example.com",
                    }
                ],
            },
        )
        msg_data = msg_response.json()
        msg_id = msg_data["id"]
        response = client.get(f"/api/messages/{msg_id}/citations")
        assert response.status_code == 200
        data = response.json()
        assert data["message_id"] == msg_id
        assert "citations" in data

    def test_get_citations_nonexistent_message(self):
        """测试获取不存在消息的引用（返回空列表）"""
        response = client.get("/api/messages/nonexistent-msg-id/citations")
        assert response.status_code == 200
        data = response.json()
        assert data["citations"] == []


# ===== 论题接口测试 =====

class TestProposalEndpoints:
    """论题接口测试"""

    def test_list_proposals(self):
        """测试列出论题"""
        response = client.get("/api/proposals")
        assert response.status_code == 200
        data = response.json()
        assert "proposals" in data
        assert "count" in data

    def test_list_proposals_with_pagination(self):
        """测试论题列表分页"""
        response = client.get("/api/proposals?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_list_proposals_by_session(self):
        """测试按会话过滤论题"""
        sid = _create_test_session("论题过滤测试")
        response = client.get(f"/api/proposals?session_id={sid}")
        assert response.status_code == 200
        data = response.json()
        assert "proposals" in data

    def test_get_proposal_not_found(self):
        """测试获取不存在的论题返回 404"""
        response = client.get("/api/proposals/nonexistent-proposal-id")
        assert response.status_code == 404

    def test_delete_proposal(self):
        """测试删除论题"""
        response = client.delete("/api/proposals/nonexistent-proposal-id")
        assert response.status_code == 200


# ===== 模型管理接口测试 =====

class TestModelManagementEndpoints:
    """模型管理接口测试"""

    def test_add_and_delete_model(self):
        """测试新增与删除模型"""
        # 新增模型
        response = client.post(
            "/api/models",
            json={
                "id": "test-model-api-001",
                "label": "测试模型",
                "base_url": "https://api.test.com",
                "api_key": "test-key",
                "supports_streaming": True,
                "supports_thinking": False,
                "supports_web_search": False,
                "max_context": 32768,
                "default_temperature": 0.7,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 删除模型
        response = client.delete("/api/models/test-model-api-001")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_add_duplicate_model_fails(self):
        """测试新增重复模型 ID 失败"""
        # 先获取现有模型列表
        response = client.get("/api/models")
        existing_models = response.json()["models"]
        if existing_models:
            existing_id = existing_models[0]["id"]
            response = client.post(
                "/api/models",
                json={
                    "id": existing_id,
                    "label": "重复模型",
                    "base_url": "",
                    "api_key": "",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_update_model(self):
        """测试更新模型配置"""
        # 先新增一个模型
        client.post(
            "/api/models",
            json={
                "id": "test-update-model-001",
                "label": "原标签",
                "base_url": "",
                "api_key": "",
            },
        )
        # 更新
        response = client.put(
            "/api/models/test-update-model-001",
            json={
                "id": "test-update-model-001",
                "label": "更新后标签",
                "base_url": "https://updated.com",
                "api_key": "new-key",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 清理
        client.delete("/api/models/test-update-model-001")

    def test_update_nonexistent_model_fails(self):
        """测试更新不存在的模型失败"""
        response = client.put(
            "/api/models/nonexistent-model-id",
            json={
                "id": "nonexistent-model-id",
                "label": "标签",
                "base_url": "",
                "api_key": "",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_currency_switch(self):
        """测试货币切换"""
        response = client.put("/api/currency", json={"currency": "CNY"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_currency_switch_invalid(self):
        """测试无效货币切换失败"""
        response = client.put("/api/currency", json={"currency": "EUR"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


# ===== 集成场景测试 =====

class TestAPIIntegrationScenarios:
    """API 集成场景测试"""

    def test_full_session_conversation_flow(self):
        """测试完整会话-对话流程"""
        # 1. 创建会话
        sid = _create_test_session("完整流程测试")
        # 2. 创建对话
        cid = _create_test_conversation(sid, "完整流程对话")
        # 3. 添加消息
        client.post(
            f"/api/conversations/{cid}/messages",
            json={"role": "user", "content": "用户提问", "agent_id": "orchestrator"},
        )
        client.post(
            f"/api/conversations/{cid}/messages",
            json={"role": "assistant", "content": "助手回复", "agent_id": "orchestrator"},
        )
        # 4. 获取消息列表
        response = client.get(f"/api/conversations/{cid}/messages")
        assert response.status_code == 200
        assert len(response.json()["messages"]) >= 2
        # 5. 获取上下文
        response = client.get(f"/api/conversations/{cid}/context")
        assert response.status_code == 200
        # 6. 删除对话
        response = client.delete(f"/api/conversations/{cid}")
        assert response.status_code == 200

    def test_multi_conversation_in_session(self):
        """测试同一会话下多对话"""
        sid = _create_test_session("多对话测试")
        cid1 = _create_test_conversation(sid, "对话1")
        cid2 = _create_test_conversation(sid, "对话2")
        # 列出对话
        response = client.get(f"/api/sessions/{sid}/conversations")
        assert response.status_code == 200
        convs = response.json()["conversations"]
        assert len(convs) >= 2
        # 各对话独立添加消息
        client.post(
            f"/api/conversations/{cid1}/messages",
            json={"role": "user", "content": "对话1消息", "agent_id": "orchestrator"},
        )
        client.post(
            f"/api/conversations/{cid2}/messages",
            json={"role": "user", "content": "对话2消息", "agent_id": "reasoner"},
        )
        # 验证消息隔离
        msgs1 = client.get(f"/api/conversations/{cid1}/messages").json()["messages"]
        msgs2 = client.get(f"/api/conversations/{cid2}/messages").json()["messages"]
        assert all(m["content"] == "对话1消息" for m in msgs1)
        assert all(m["content"] == "对话2消息" for m in msgs2)

    def test_lineage_import_and_query_flow(self):
        """测试谱系导入与查询流程"""
        # 导入节点
        client.post(
            "/api/lineage/import",
            json={
                "nodes": [
                    {
                        "node_type": "topic",
                        "title": "图神经网络研究",
                        "abstract": "GNN 在社交网络中的应用",
                        "metadata": {"year": 2024},
                    },
                ],
                "edges": [],
            },
        )
        # 查询图谱
        response = client.get("/api/lineage/graph")
        assert response.status_code == 200
        # 搜索
        response = client.get("/api/lineage/search?keyword=图神经网络")
        assert response.status_code == 200

    def test_config_and_status_flow(self):
        """测试配置与状态查询流程"""
        # 获取状态
        status = client.get("/api/status").json()
        assert status["status"] == "ok"
        # 获取配置
        config = client.get("/api/config").json()
        assert "ai_api_key_configured" in config
        # 获取模型列表
        models = client.get("/api/models").json()
        assert models["count"] >= 0
        # 获取步骤路由
        step_models = client.get("/api/step-models").json()
        assert "step_models" in step_models


# ===== 错误处理测试 =====

class TestAPIErrorHandling:
    """API 错误处理测试"""

    def test_invalid_json_body(self):
        """测试无效 JSON 请求体"""
        response = client.post(
            "/api/sessions",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_missing_required_fields(self):
        """测试缺少必填字段"""
        response = client.post(
            "/api/sessions",
            json={"title": "缺少字段"},
        )
        assert response.status_code == 422

    def test_404_for_unknown_route(self):
        """测试未知路由返回 404"""
        response = client.get("/api/nonexistent-endpoint")
        assert response.status_code == 404

    def test_conversation_messages_with_invalid_conversation(self):
        """测试向不存在的对话添加消息（外键约束失败）"""
        # 外键约束失败会抛出 IntegrityError，验证异常被触发
        with pytest.raises(Exception):
            client.post(
                "/api/conversations/nonexistent-id/messages",
                json={"role": "user", "content": "测试", "agent_id": "orchestrator"},
            )
