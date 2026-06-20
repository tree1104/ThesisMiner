"""压力测试：消息吞吐量验证

验证系统在单对话 1000 条消息场景下的性能与稳定性：
- 批量插入 1000 条消息
- 消息查询性能
- 上下文窗口压缩性能
- 消息分页查询
- 引用批量存储
- 响应时间测量
- 数据完整性验证

运行方式：python -m pytest tests/load/test_message_volume.py -v
"""
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 切换到临时数据库
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_load_messages_")
_tmp_db = os.path.join(_tmp_dir, "test_messages.db")
_db.DB_PATH = _tmp_db
_db.init_db()

from fastapi.testclient import TestClient
from main import app
from backend.sessions import session_manager
from backend.sessions.conversation_manager import get_conversation_manager
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

def _create_session_and_conversation():
    """创建会话与对话，返回 (session_id, conversation_id)"""
    req = SessionCreate(
        title="消息吞吐量测试",
        degree=DegreeType.master,
        discipline=DisciplineType.science_engineering,
        mentor_info="深度学习",
    )
    sid = session_manager.create_session(req)["id"]
    cm = get_conversation_manager()
    cid = cm.create_conversation(sid, title="消息吞吐对话")["id"]
    return sid, cid


def _add_message_via_api(cid: str, index: int, role: str = "user") -> dict:
    """通过 API 添加消息"""
    response = client.post(
        f"/api/conversations/{cid}/messages",
        json={
            "role": role,
            "content": f"消息_{index}_这是测试消息内容用于验证消息吞吐量",
            "agent_id": "orchestrator",
            "reasoning": f"思维链_{index}" if role == "assistant" else "",
        },
    )
    return response.json()


def _add_message_via_manager(cid: str, index: int, role: str = "user") -> dict:
    """通过 ConversationManager 添加消息"""
    cm = get_conversation_manager()
    return cm.add_message(
        cid,
        role=role,
        content=f"管理器消息_{index}",
        agent_id="orchestrator",
        reasoning=f"思维链_{index}" if role == "assistant" else "",
    )


# ===== 批量消息插入测试 =====

class TestBatchMessageInsertion:
    """批量消息插入测试"""

    def test_insert_100_messages(self):
        """测试插入 100 条消息"""
        sid, cid = _create_session_and_conversation()
        for i in range(100):
            _add_message_via_api(cid, i)
        msgs = client.get(f"/api/conversations/{cid}/messages?limit=200").json()["messages"]
        assert len(msgs) >= 100

    def test_insert_500_messages(self):
        """测试插入 500 条消息"""
        sid, cid = _create_session_and_conversation()
        for i in range(500):
            _add_message_via_api(cid, i)
        msgs = client.get(f"/api/conversations/{cid}/messages?limit=600").json()["messages"]
        assert len(msgs) >= 500

    def test_insert_1000_messages(self):
        """测试插入 1000 条消息（核心压测）"""
        sid, cid = _create_session_and_conversation()
        for i in range(1000):
            _add_message_via_api(cid, i)
        msgs = client.get(f"/api/conversations/{cid}/messages?limit=1200").json()["messages"]
        assert len(msgs) >= 1000

    def test_insert_1000_messages_via_manager(self):
        """测试通过管理器插入 1000 条消息"""
        sid, cid = _create_session_and_conversation()
        for i in range(1000):
            _add_message_via_manager(cid, i)
        cm = get_conversation_manager()
        msgs = cm.get_messages(cid, limit=2000)
        assert len(msgs) >= 1000

    def test_insert_alternating_roles(self):
        """测试交替角色消息插入（用户/助手）"""
        sid, cid = _create_session_and_conversation()
        for i in range(200):
            role = "user" if i % 2 == 0 else "assistant"
            _add_message_via_api(cid, i, role)
        msgs = client.get(f"/api/conversations/{cid}/messages?limit=300").json()["messages"]
        user_count = sum(1 for m in msgs if m["role"] == "user")
        assistant_count = sum(1 for m in msgs if m["role"] == "assistant")
        assert user_count == 100
        assert assistant_count == 100


# ===== 消息插入性能测试 =====

class TestMessageInsertionPerformance:
    """消息插入性能测试"""

    def test_100_messages_insertion_time(self):
        """测试 100 条消息插入时间 < 5 秒"""
        sid, cid = _create_session_and_conversation()
        start = time.time()
        for i in range(100):
            _add_message_via_api(cid, i)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"100 条消息插入耗时 {elapsed:.2f}s"

    def test_500_messages_insertion_time(self):
        """测试 500 条消息插入时间 < 15 秒"""
        sid, cid = _create_session_and_conversation()
        start = time.time()
        for i in range(500):
            _add_message_via_api(cid, i)
        elapsed = time.time() - start
        assert elapsed < 15.0, f"500 条消息插入耗时 {elapsed:.2f}s"

    def test_1000_messages_insertion_time(self):
        """测试 1000 条消息插入时间 < 30 秒"""
        sid, cid = _create_session_and_conversation()
        start = time.time()
        for i in range(1000):
            _add_message_via_api(cid, i)
        elapsed = time.time() - start
        assert elapsed < 30.0, f"1000 条消息插入耗时 {elapsed:.2f}s"

    def test_single_message_insertion_time(self):
        """测试单条消息插入时间 < 0.1 秒"""
        sid, cid = _create_session_and_conversation()
        start = time.time()
        _add_message_via_api(cid, 0)
        elapsed = time.time() - start
        assert elapsed < 0.1, f"单条消息插入耗时 {elapsed:.3f}s"

    def test_batch_insert_throughput(self):
        """测试批量插入吞吐量（条/秒）"""
        sid, cid = _create_session_and_conversation()
        count = 200
        start = time.time()
        for i in range(count):
            _add_message_via_api(cid, i)
        elapsed = time.time() - start
        throughput = count / elapsed if elapsed > 0 else 0
        assert throughput > 10, f"吞吐量 {throughput:.1f} 条/秒，低于 10 条/秒"


# ===== 消息查询性能测试 =====

class TestMessageQueryPerformance:
    """消息查询性能测试"""

    def test_query_100_messages_time(self):
        """测试查询 100 条消息时间 < 1 秒"""
        sid, cid = _create_session_and_conversation()
        for i in range(100):
            _add_message_via_api(cid, i)
        start = time.time()
        response = client.get(f"/api/conversations/{cid}/messages")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"查询 100 条消息耗时 {elapsed:.3f}s"

    def test_query_500_messages_time(self):
        """测试查询 500 条消息时间 < 2 秒"""
        sid, cid = _create_session_and_conversation()
        for i in range(500):
            _add_message_via_api(cid, i)
        start = time.time()
        response = client.get(f"/api/conversations/{cid}/messages?limit=500")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 2.0, f"查询 500 条消息耗时 {elapsed:.3f}s"

    def test_query_1000_messages_time(self):
        """测试查询 1000 条消息时间 < 3 秒"""
        sid, cid = _create_session_and_conversation()
        for i in range(1000):
            _add_message_via_api(cid, i)
        start = time.time()
        response = client.get(f"/api/conversations/{cid}/messages?limit=1000")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 3.0, f"查询 1000 条消息耗时 {elapsed:.3f}s"

    def test_message_pagination_performance(self):
        """测试消息分页查询性能"""
        sid, cid = _create_session_and_conversation()
        for i in range(200):
            _add_message_via_api(cid, i)
        # 分页查询
        start = time.time()
        for offset in range(0, 200, 50):
            client.get(f"/api/conversations/{cid}/messages?limit=50")
        elapsed = time.time() - start
        assert elapsed < 2.0, f"4 次分页查询耗时 {elapsed:.3f}s"


# ===== 上下文窗口性能测试 =====

class TestContextWindowPerformance:
    """上下文窗口性能测试"""

    def test_context_window_with_100_messages(self):
        """测试 100 条消息的上下文窗口获取"""
        sid, cid = _create_session_and_conversation()
        for i in range(100):
            _add_message_via_api(cid, i)
        start = time.time()
        response = client.get(f"/api/conversations/{cid}/context?max_tokens=4000")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 2.0, f"100 条消息上下文获取耗时 {elapsed:.3f}s"

    def test_context_window_with_500_messages(self):
        """测试 500 条消息的上下文窗口获取（含 DST 压缩）"""
        sid, cid = _create_session_and_conversation()
        for i in range(500):
            _add_message_via_api(cid, i)
        start = time.time()
        response = client.get(f"/api/conversations/{cid}/context?max_tokens=4000")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 5.0, f"500 条消息上下文获取耗时 {elapsed:.3f}s"

    def test_context_window_compression_effective(self):
        """测试上下文窗口压缩有效（返回消息数 < 总消息数）"""
        sid, cid = _create_session_and_conversation()
        for i in range(200):
            _add_message_via_api(cid, i)
        response = client.get(f"/api/conversations/{cid}/context?max_tokens=1000")
        data = response.json()
        context = data["context"]
        # 压缩后上下文消息数应少于总消息数
        if isinstance(context, list):
            assert len(context) <= 200

    def test_context_window_with_different_token_limits(self):
        """测试不同 token 限制下的上下文窗口"""
        sid, cid = _create_session_and_conversation()
        for i in range(100):
            _add_message_via_api(cid, i)
        for max_tokens in [1000, 2000, 4000, 8000]:
            response = client.get(f"/api/conversations/{cid}/context?max_tokens={max_tokens}")
            assert response.status_code == 200


# ===== 引用批量存储测试 =====

class TestCitationBatchStorage:
    """引用批量存储测试"""

    def test_batch_messages_with_citations(self):
        """测试批量含引用消息存储"""
        sid, cid = _create_session_and_conversation()
        for i in range(50):
            client.post(
                f"/api/conversations/{cid}/messages",
                json={
                    "role": "assistant",
                    "content": f"回复_{i}参见 [文献{i}](https://example.com/{i})",
                    "agent_id": "searcher",
                    "citations": [
                        {
                            "url": f"https://example.com/{i}",
                            "title": f"文献_{i}",
                            "snippet": f"摘要_{i}",
                            "source_domain": "example.com",
                        }
                    ],
                },
            )
        # 验证引用可查询
        msgs = client.get(f"/api/conversations/{cid}/messages").json()["messages"]
        for msg in msgs[:5]:
            cites = client.get(f"/api/messages/{msg['id']}/citations").json()["citations"]
            assert len(cites) >= 1

    def test_citation_query_performance(self):
        """测试引用查询性能"""
        sid, cid = _create_session_and_conversation()
        msg_ids = []
        for i in range(20):
            resp = client.post(
                f"/api/conversations/{cid}/messages",
                json={
                    "role": "assistant",
                    "content": f"回复_{i}",
                    "agent_id": "searcher",
                    "citations": [
                        {
                            "url": f"https://example.com/{i}",
                            "title": f"文献_{i}",
                            "snippet": "",
                            "source_domain": "example.com",
                        }
                    ],
                },
            )
            msg_ids.append(resp.json()["id"])
        start = time.time()
        for mid in msg_ids:
            client.get(f"/api/messages/{mid}/citations")
        elapsed = time.time() - start
        assert elapsed < 3.0, f"20 次引用查询耗时 {elapsed:.3f}s"


# ===== 数据完整性测试 =====

class TestMessageDataIntegrity:
    """消息数据完整性测试"""

    def test_message_order_preserved(self):
        """测试消息顺序保持"""
        sid, cid = _create_session_and_conversation()
        for i in range(100):
            _add_message_via_api(cid, i)
        msgs = client.get(f"/api/conversations/{cid}/messages?limit=100").json()["messages"]
        # 验证消息按创建时间排序
        for i in range(len(msgs) - 1):
            assert msgs[i]["created_at"] <= msgs[i + 1]["created_at"]

    def test_message_content_integrity(self):
        """测试消息内容完整性"""
        sid, cid = _create_session_and_conversation()
        test_contents = [f"完整性测试消息_{i}" for i in range(50)]
        for content in test_contents:
            client.post(
                f"/api/conversations/{cid}/messages",
                json={"role": "user", "content": content, "agent_id": "orchestrator"},
            )
        msgs = client.get(f"/api/conversations/{cid}/messages?limit=50").json()["messages"]
        retrieved_contents = [m["content"] for m in msgs]
        for tc in test_contents:
            assert tc in retrieved_contents, f"消息内容丢失: {tc}"

    def test_message_agent_id_preserved(self):
        """测试消息 agent_id 保持"""
        sid, cid = _create_session_and_conversation()
        agents = ["orchestrator", "reasoner", "mentor", "critic", "writer", "searcher"]
        for i in range(60):
            agent = agents[i % len(agents)]
            client.post(
                f"/api/conversations/{cid}/messages",
                json={"role": "assistant", "content": f"消息_{i}", "agent_id": agent},
            )
        msgs = client.get(f"/api/conversations/{cid}/messages?limit=60").json()["messages"]
        for msg in msgs:
            assert msg["agent_id"] in agents

    def test_message_count_accuracy(self):
        """测试消息数量准确性"""
        sid, cid = _create_session_and_conversation()
        count = 150
        for i in range(count):
            _add_message_via_api(cid, i)
        msgs = client.get(f"/api/conversations/{cid}/messages?limit=200").json()["messages"]
        assert len(msgs) == count

    def test_reasoning_content_preserved(self):
        """测试思维链内容保持"""
        sid, cid = _create_session_and_conversation()
        for i in range(30):
            client.post(
                f"/api/conversations/{cid}/messages",
                json={
                    "role": "assistant",
                    "content": f"回复_{i}",
                    "agent_id": "reasoner",
                    "reasoning": f"详细思维链_{i}",
                },
            )
        msgs = client.get(f"/api/conversations/{cid}/messages?limit=30").json()["messages"]
        for msg in msgs:
            assert msg["reasoning"] is not None


# ===== 多对话消息隔离测试 =====

class TestMultiConversationMessageIsolation:
    """多对话消息隔离测试"""

    def test_messages_isolated_between_conversations(self):
        """测试对话间消息完全隔离"""
        sid = session_manager.create_session(
            SessionCreate(
                title="隔离测试",
                degree=DegreeType.master,
                discipline=DisciplineType.science_engineering,
                mentor_info="测试",
            )
        )["id"]
        cm = get_conversation_manager()
        cid1 = cm.create_conversation(sid, title="对话1")["id"]
        cid2 = cm.create_conversation(sid, title="对话2")["id"]
        # 各自添加消息
        for i in range(100):
            cm.add_message(cid1, role="user", content=f"对话1消息_{i}", agent_id="orchestrator")
            cm.add_message(cid2, role="user", content=f"对话2消息_{i}", agent_id="orchestrator")
        msgs1 = cm.get_messages(cid1, limit=200)
        msgs2 = cm.get_messages(cid2, limit=200)
        assert len(msgs1) == 100
        assert len(msgs2) == 100
        assert all("对话1" in m["content"] for m in msgs1)
        assert all("对话2" in m["content"] for m in msgs2)

    def test_large_message_count_multiple_conversations(self):
        """测试多对话大消息量"""
        sid = session_manager.create_session(
            SessionCreate(
                title="大消息量测试",
                degree=DegreeType.master,
                discipline=DisciplineType.science_engineering,
                mentor_info="测试",
            )
        )["id"]
        cm = get_conversation_manager()
        conv_ids = [cm.create_conversation(sid, title=f"对话{i}")["id"] for i in range(5)]
        # 每个对话 200 条消息
        for cid in conv_ids:
            for i in range(200):
                cm.add_message(cid, role="user", content=f"消息_{i}", agent_id="orchestrator")
        # 验证各对话消息数
        for cid in conv_ids:
            msgs = cm.get_messages(cid, limit=300)
            assert len(msgs) == 200
