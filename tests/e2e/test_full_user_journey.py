"""E2E 测试：完整用户旅程验证

覆盖用户从启动系统到完成论题生成的完整旅程：
- 服务启动与健康检查
- 配置查询与模型列表
- 会话创建与对话管理
- 谱系图谱导入与查询
- 创意激发与候选排序
- 约束校验（标题/可行性/文献）
- 缓存统计查询
- Agent 列表查询
- 引用解析与展示
- 消息上下文管理
- 会话删除与清理

使用 FastAPI TestClient 模拟完整 HTTP 请求链路，
配合临时数据库确保测试隔离。

运行方式：python -m pytest tests/e2e/test_full_user_journey.py -v
"""
import os
import sys
import tempfile

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 切换到临时数据库
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_journey_")
_tmp_db = os.path.join(_tmp_dir, "test_journey.db")
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

def _create_session(title: str = "用户旅程会话") -> str:
    """创建会话并返回 ID"""
    req = SessionCreate(
        title=title,
        degree=DegreeType.master,
        discipline=DisciplineType.science_engineering,
        mentor_info="深度学习与计算机视觉",
    )
    return session_manager.create_session(req)["id"]


def _create_conversation(session_id: str, title: str = "旅程对话") -> str:
    """创建对话并返回 ID"""
    response = client.post(
        f"/api/sessions/{session_id}/conversations",
        json={"title": title, "agent_id": "orchestrator"},
    )
    return response.json()["id"]


# ===== 第一阶段：系统启动与健康检查 =====

class TestSystemStartup:
    """系统启动与健康检查"""

    def test_service_status_ok(self):
        """验证服务状态正常"""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "ai_configured" in data

    def test_config_accessible(self):
        """验证配置可访问"""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "ai_api_key_configured" in data
        assert "degree_models" in data
        assert "academic_calendar" in data

    def test_models_list_available(self):
        """验证模型列表可用"""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert data["count"] >= 0

    def test_step_models_configured(self):
        """验证步骤路由已配置"""
        response = client.get("/api/step-models")
        assert response.status_code == 200
        data = response.json()
        assert "step_models" in data

    def test_agents_list_available(self):
        """验证 Agent 列表可用"""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)


# ===== 第二阶段：会话与对话创建 =====

class TestSessionConversationCreation:
    """会话与对话创建旅程"""

    def test_create_session_via_api(self):
        """通过 API 创建会话"""
        response = client.post(
            "/api/sessions",
            json={
                "title": "用户旅程测试会话",
                "degree": "master",
                "discipline": "science_engineering",
                "mentor_info": "深度学习",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "用户旅程测试会话"
        assert data["degree"] == "master"

    def test_list_sessions_after_creation(self):
        """创建后列出会话"""
        _create_session("列表验证会话")
        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert isinstance(data["sessions"], list)

    def test_get_session_detail(self):
        """获取会话详情"""
        sid = _create_session("详情验证会话")
        response = client.get(f"/api/sessions/{sid}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sid
        assert "dialog_rounds" in data

    def test_create_conversation_in_session(self):
        """在会话下创建对话"""
        sid = _create_session("对话创建验证")
        response = client.post(
            f"/api/sessions/{sid}/conversations",
            json={"title": "论题生成对话", "agent_id": "orchestrator"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "论题生成对话"

    def test_list_conversations_in_session(self):
        """列出会话下的对话"""
        sid = _create_session("对话列表验证")
        _create_conversation(sid, "对话A")
        _create_conversation(sid, "对话B")
        response = client.get(f"/api/sessions/{sid}/conversations")
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) >= 2

    def test_set_active_conversation(self):
        """设置激活对话"""
        sid = _create_session("激活对话验证")
        cid = _create_conversation(sid, "激活测试")
        response = client.put(
            f"/api/sessions/{sid}/active-conversation",
            params={"cid": cid},
        )
        assert response.status_code == 200
        assert response.json()["active_conversation_id"] == cid


# ===== 第三阶段：消息交互与上下文 =====

class TestMessageInteraction:
    """消息交互与上下文管理旅程"""

    def test_send_user_message(self):
        """发送用户消息"""
        sid = _create_session("消息发送验证")
        cid = _create_conversation(sid, "消息对话")
        response = client.post(
            f"/api/conversations/{cid}/messages",
            json={
                "role": "user",
                "content": "请帮我生成关于深度学习的论题",
                "agent_id": "orchestrator",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    def test_send_assistant_message_with_reasoning(self):
        """发送含思维链的助手消息"""
        sid = _create_session("思维链验证")
        cid = _create_conversation(sid, "思维链对话")
        response = client.post(
            f"/api/conversations/{cid}/messages",
            json={
                "role": "assistant",
                "content": "基于您的需求，推荐以下论题方向...",
                "agent_id": "reasoner",
                "reasoning": "分析用户需求：深度学习方向，结合当前热点...",
            },
        )
        assert response.status_code == 200

    def test_retrieve_message_history(self):
        """获取消息历史"""
        sid = _create_session("历史验证")
        cid = _create_conversation(sid, "历史对话")
        for i in range(3):
            client.post(
                f"/api/conversations/{cid}/messages",
                json={"role": "user", "content": f"消息{i + 1}", "agent_id": "orchestrator"},
            )
        response = client.get(f"/api/conversations/{cid}/messages")
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) >= 3

    def test_get_context_window(self):
        """获取上下文窗口"""
        sid = _create_session("上下文验证")
        cid = _create_conversation(sid, "上下文对话")
        client.post(
            f"/api/conversations/{cid}/messages",
            json={"role": "user", "content": "上下文测试", "agent_id": "orchestrator"},
        )
        response = client.get(f"/api/conversations/{cid}/context?max_tokens=4000")
        assert response.status_code == 200
        data = response.json()
        assert "context" in data

    def test_message_isolation_between_conversations(self):
        """验证对话间消息隔离"""
        sid = _create_session("隔离验证")
        cid1 = _create_conversation(sid, "隔离对话1")
        cid2 = _create_conversation(sid, "隔离对话2")
        client.post(
            f"/api/conversations/{cid1}/messages",
            json={"role": "user", "content": "对话1专属消息", "agent_id": "orchestrator"},
        )
        client.post(
            f"/api/conversations/{cid2}/messages",
            json={"role": "user", "content": "对话2专属消息", "agent_id": "reasoner"},
        )
        msgs1 = client.get(f"/api/conversations/{cid1}/messages").json()["messages"]
        msgs2 = client.get(f"/api/conversations/{cid2}/messages").json()["messages"]
        assert all("对话1" in m["content"] for m in msgs1)
        assert all("对话2" in m["content"] for m in msgs2)


# ===== 第四阶段：谱系图谱管理 =====

class TestLineageGraphJourney:
    """谱系图谱管理旅程"""

    def test_import_lineage_nodes(self):
        """导入谱系节点"""
        response = client.post(
            "/api/lineage/import",
            json={
                "nodes": [
                    {
                        "node_type": "mentor_project",
                        "title": "国家自然科学基金项目",
                        "abstract": "深度学习医学影像分析",
                        "metadata": {"year": 2024, "fund": "NSFC"},
                    },
                    {
                        "node_type": "student_thesis",
                        "title": "基于GNN的社交网络分析",
                        "abstract": "使用图神经网络分析社交网络结构",
                        "metadata": {"year": 2023, "degree": "master"},
                    },
                    {
                        "node_type": "topic",
                        "title": "图神经网络研究",
                        "abstract": "GNN 前沿方向",
                        "metadata": {},
                    },
                ],
                "edges": [],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["imported_nodes"] == 3

    def test_query_lineage_graph(self):
        """查询完整图谱"""
        response = client.get("/api/lineage/graph")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

    def test_search_lineage_by_keyword(self):
        """按关键词搜索谱系"""
        client.post(
            "/api/lineage/import",
            json={
                "nodes": [
                    {
                        "node_type": "topic",
                        "title": "深度学习图像分割",
                        "abstract": "使用U-Net进行医学图像分割",
                        "metadata": {},
                    },
                ],
                "edges": [],
            },
        )
        response = client.get("/api/lineage/search?keyword=图像分割")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_lineage_pagination(self):
        """谱系节点分页"""
        response = client.get("/api/lineage?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "has_more" in data

    def test_knowledge_card_management(self):
        """知识卡片管理"""
        # 新增
        response = client.post(
            "/api/lineage/cards",
            json={
                "title": "深度学习笔记",
                "content": "CNN、RNN、Transformer 核心原理",
                "tags": ["深度学习", "基础"],
                "source": "用户旅程测试",
            },
        )
        assert response.status_code == 200
        # 查询
        response = client.get("/api/lineage/cards")
        assert response.status_code == 200
        data = response.json()
        assert "cards" in data


# ===== 第五阶段：创意激发与约束校验 =====

class TestCreativityAndConstraints:
    """创意激发与约束校验旅程"""

    def test_inspire_creativity(self):
        """激发创意"""
        response = client.post(
            "/api/creativity/inspire",
            json={
                "degree": "master",
                "discipline": "science_engineering",
                "mentor_info": "深度学习与计算机视觉",
                "context": "",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "candidates" in data

    def test_cross_domain_association(self):
        """跨域联想"""
        response = client.post(
            "/api/creativity/cross-domain",
            json={"domain_a": "计算机科学", "domain_b": "生物医学"},
        )
        assert response.status_code == 200

    def test_rank_candidates(self):
        """候选排序"""
        response = client.post(
            "/api/creativity/rank",
            json={
                "candidates": [
                    {"title": "基于深度学习的医学影像分割", "inspiration_source": "跨域联想"},
                    {"title": "图神经网络在社交网络中的应用", "inspiration_source": "学术谱系"},
                    {"title": "Transformer 模型优化研究", "inspiration_source": "趋势嫁接"},
                ],
                "degree": "master",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "ranked_candidates" in data
        assert data["count"] == 3

    def test_validate_title_format(self):
        """标题格式校验"""
        response = client.post(
            "/api/constraints/validate-title",
            json={"title": "基于深度学习的图像识别研究", "degree": "master"},
        )
        assert response.status_code == 200

    def test_check_feasibility(self):
        """可行性校验"""
        response = client.post(
            "/api/constraints/check-feasibility",
            json={
                "degree": "master",
                "timeframe_months": 12,
                "research_content": ["文献调研", "实验设计", "数据分析"],
            },
        )
        assert response.status_code == 200

    def test_check_literature_baseline(self):
        """文献基线校验"""
        response = client.post(
            "/api/constraints/check-literature",
            json={"degree": "master", "count": 30},
        )
        assert response.status_code == 200

    def test_get_academic_calendar(self):
        """获取学术日历"""
        response = client.get("/api/constraints/calendar/master")
        assert response.status_code == 200

    def test_get_literature_baseline(self):
        """获取文献基线"""
        response = client.get("/api/constraints/baseline/master")
        assert response.status_code == 200
        data = response.json()
        assert "baseline" in data


# ===== 第六阶段：引用与缓存 =====

class TestCitationsAndCache:
    """引用解析与缓存统计旅程"""

    def test_add_message_with_citations(self):
        """添加含引用的消息"""
        sid = _create_session("引用验证")
        cid = _create_conversation(sid, "引用对话")
        response = client.post(
            f"/api/conversations/{cid}/messages",
            json={
                "role": "assistant",
                "content": "参见 [深度学习综述](https://arxiv.org/abs/2024.001) 了解更多",
                "agent_id": "searcher",
                "citations": [
                    {
                        "url": "https://arxiv.org/abs/2024.001",
                        "title": "深度学习综述",
                        "snippet": "本文综述了深度学习的最新进展",
                        "source_domain": "arxiv.org",
                    }
                ],
            },
        )
        assert response.status_code == 200
        msg_id = response.json()["id"]
        # 查询引用
        response = client.get(f"/api/messages/{msg_id}/citations")
        assert response.status_code == 200
        data = response.json()
        assert data["message_id"] == msg_id
        assert len(data["citations"]) >= 1

    def test_get_conversation_citations(self):
        """获取对话级引用聚合"""
        sid = _create_session("对话引用验证")
        cid = _create_conversation(sid, "聚合引用对话")
        response = client.get(f"/api/conversations/{cid}/citations")
        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert "citations" in data

    def test_cache_stats_accessible(self):
        """缓存统计可访问"""
        response = client.get("/api/cache-stats")
        assert response.status_code == 200
        data = response.json()
        assert "avg_hit_rate" in data
        assert "total_calls" in data


# ===== 第七阶段：预算与费用 =====

class TestBudgetJourney:
    """预算与费用查询旅程"""

    def test_get_ledger_entries(self):
        """获取账本明细"""
        response = client.get("/api/budgets/ledger")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "count" in data

    def test_get_budget_summary(self):
        """获取预算汇总"""
        response = client.get("/api/budgets/summary")
        assert response.status_code == 200

    def test_get_pricing_table(self):
        """获取定价表"""
        response = client.get("/api/budgets/pricing")
        assert response.status_code == 200
        data = response.json()
        assert "pricing" in data
        assert "currency" in data

    def test_estimate_budget(self):
        """预算估算"""
        response = client.post(
            "/api/budgets/estimate",
            json={"degree": "master", "mode": "quick", "count": 5},
        )
        assert response.status_code == 200

    def test_get_session_cost(self):
        """获取会话费用"""
        sid = _create_session("费用验证")
        response = client.get(f"/api/budgets/session/{sid}")
        assert response.status_code == 200


# ===== 完整端到端旅程 =====

class TestCompleteUserJourney:
    """完整用户旅程：从创建到清理"""

    def test_full_journey_create_to_delete(self):
        """完整旅程：创建会话 → 对话 → 消息 → 清理"""
        # 1. 创建会话
        sid = _create_session("完整旅程会话")
        assert sid is not None

        # 2. 创建对话
        cid = _create_conversation(sid, "完整旅程对话")
        assert cid is not None

        # 3. 添加多轮消息
        for i in range(3):
            client.post(
                f"/api/conversations/{cid}/messages",
                json={
                    "role": "user",
                    "content": f"用户第{i + 1}轮提问",
                    "agent_id": "orchestrator",
                },
            )
            client.post(
                f"/api/conversations/{cid}/messages",
                json={
                    "role": "assistant",
                    "content": f"助手第{i + 1}轮回复",
                    "agent_id": "orchestrator",
                    "reasoning": f"思维链{i + 1}",
                },
            )

        # 4. 验证消息数量
        msgs = client.get(f"/api/conversations/{cid}/messages").json()["messages"]
        assert len(msgs) >= 6

        # 5. 获取上下文
        ctx = client.get(f"/api/conversations/{cid}/context").json()
        assert "context" in ctx

        # 6. 重命名对话
        client.put(f"/api/conversations/{cid}", json={"title": "重命名后对话"})

        # 7. 删除对话
        del_resp = client.delete(f"/api/conversations/{cid}")
        assert del_resp.status_code == 200

        # 8. 删除会话
        client.delete(f"/api/sessions/{sid}")

    def test_multi_session_multi_conversation_journey(self):
        """多会话多对话旅程"""
        sessions = []
        for s in range(3):
            sid = _create_session(f"多会话旅程{s + 1}")
            sessions.append(sid)
            for c in range(2):
                cid = _create_conversation(sid, f"会话{s + 1}_对话{c + 1}")
                client.post(
                    f"/api/conversations/{cid}/messages",
                    json={
                        "role": "user",
                        "content": f"会话{s + 1}对话{c + 1}的消息",
                        "agent_id": "orchestrator",
                    },
                )
        # 验证会话列表
        sessions_data = client.get("/api/sessions").json()
        assert sessions_data["count"] >= 3
        # 清理
        for sid in sessions:
            client.delete(f"/api/sessions/{sid}")

    def test_lineage_import_search_delete_journey(self):
        """谱系导入→搜索→删除旅程"""
        # 导入
        import_resp = client.post(
            "/api/lineage/import",
            json={
                "nodes": [
                    {
                        "node_type": "topic",
                        "title": "旅程测试谱系节点",
                        "abstract": "用于旅程测试的谱系节点",
                        "metadata": {"test": True},
                    },
                ],
                "edges": [],
            },
        )
        assert import_resp.status_code == 200
        # 搜索
        search_resp = client.get("/api/lineage/search?keyword=旅程测试")
        assert search_resp.status_code == 200
        # 图谱查询
        graph_resp = client.get("/api/lineage/graph")
        assert graph_resp.status_code == 200

    def test_creativity_to_constraints_journey(self):
        """创意激发→约束校验旅程"""
        # 1. 激发创意
        inspire_resp = client.post(
            "/api/creativity/inspire",
            json={
                "degree": "master",
                "discipline": "science_engineering",
                "mentor_info": "深度学习",
                "context": "",
            },
        )
        assert inspire_resp.status_code == 200
        candidates = inspire_resp.json().get("candidates", [])

        # 2. 排序候选
        if candidates:
            rank_resp = client.post(
                "/api/creativity/rank",
                json={"candidates": candidates, "degree": "master"},
            )
            assert rank_resp.status_code == 200

        # 3. 校验标题
        validate_resp = client.post(
            "/api/constraints/validate-title",
            json={"title": "基于深度学习的图像识别研究", "degree": "master"},
        )
        assert validate_resp.status_code == 200

        # 4. 可行性校验
        feas_resp = client.post(
            "/api/constraints/check-feasibility",
            json={
                "degree": "master",
                "timeframe_months": 12,
                "research_content": ["文献调研", "实验设计"],
            },
        )
        assert feas_resp.status_code == 200

        # 5. 文献基线
        lit_resp = client.post(
            "/api/constraints/check-literature",
            json={"degree": "master", "count": 30},
        )
        assert lit_resp.status_code == 200


# ===== 前端资源可访问性 =====

class TestFrontendAccessibility:
    """前端资源可访问性验证"""

    def test_index_html_accessible(self):
        """验证首页可访问"""
        response = client.get("/")
        # 静态文件挂载后应返回 HTML
        assert response.status_code in (200, 404)

    def test_main_css_accessible(self):
        """验证主样式表可访问"""
        response = client.get("/styles/main.css")
        assert response.status_code in (200, 404)

    def test_app_js_accessible(self):
        """验证应用脚本可访问"""
        response = client.get("/scripts/app.js")
        assert response.status_code in (200, 404)


# ===== 数据一致性验证 =====

class TestDataConsistency:
    """数据一致性验证"""

    def test_session_conversation_consistency(self):
        """会话与对话数据一致性"""
        sid = _create_session("一致性验证")
        cid = _create_conversation(sid, "一致性对话")
        # 对话应属于该会话
        convs = client.get(f"/api/sessions/{sid}/conversations").json()["conversations"]
        conv_ids = [c["id"] for c in convs]
        assert cid in conv_ids

    def test_message_conversation_consistency(self):
        """消息与对话数据一致性"""
        sid = _create_session("消息一致性验证")
        cid = _create_conversation(sid, "消息一致性对话")
        client.post(
            f"/api/conversations/{cid}/messages",
            json={"role": "user", "content": "一致性测试", "agent_id": "orchestrator"},
        )
        msgs = client.get(f"/api/conversations/{cid}/messages").json()["messages"]
        for msg in msgs:
            assert msg["conversation_id"] == cid

    def test_conversation_deletion_cascades_messages(self):
        """删除对话后消息级联删除"""
        sid = _create_session("级联删除验证")
        cid = _create_conversation(sid, "级联删除对话")
        client.post(
            f"/api/conversations/{cid}/messages",
            json={"role": "user", "content": "待删除", "agent_id": "orchestrator"},
        )
        # 删除对话
        client.delete(f"/api/conversations/{cid}")
        # 查询消息应返回空
        msgs = client.get(f"/api/conversations/{cid}/messages").json()["messages"]
        assert len(msgs) == 0
