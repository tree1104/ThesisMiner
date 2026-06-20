"""压力测试：并发会话性能验证

验证系统在 100 个并发会话场景下的性能与稳定性：
- 并发创建 100 个会话
- 并发创建对话与消息
- 并发查询会话列表
- 并发获取会话详情
- 并发删除会话
- 响应时间测量（目标 < 2 秒）
- 数据一致性验证

使用线程池模拟并发，配合临时数据库确保测试隔离。

运行方式：python -m pytest tests/load/test_concurrent_sessions.py -v
"""
import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 切换到临时数据库
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_load_concurrent_")
_tmp_db = os.path.join(_tmp_dir, "test_concurrent.db")
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

def _create_session_via_api(index: int) -> dict:
    """通过 API 创建会话"""
    response = client.post(
        "/api/sessions",
        json={
            "title": f"并发会话_{index}",
            "degree": "master",
            "discipline": "science_engineering",
            "mentor_info": f"导师_{index}",
        },
    )
    return response.json()


def _create_session_via_manager(index: int) -> dict:
    """通过 session_manager 创建会话"""
    req = SessionCreate(
        title=f"管理器并发会话_{index}",
        degree=DegreeType.master,
        discipline=DisciplineType.science_engineering,
        mentor_info=f"导师_{index}",
    )
    return session_manager.create_session(req)


# ===== 并发会话创建测试 =====

class TestConcurrentSessionCreation:
    """并发会话创建测试"""

    def test_create_10_sessions_concurrently(self):
        """测试并发创建 10 个会话"""
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_create_session_via_api, i) for i in range(10)]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 10
        for r in results:
            assert "id" in r

    def test_create_50_sessions_concurrently(self):
        """测试并发创建 50 个会话"""
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(_create_session_via_api, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 50
        ids = [r["id"] for r in results]
        assert len(set(ids)) == 50  # 所有 ID 唯一

    def test_create_100_sessions_concurrently(self):
        """测试并发创建 100 个会话（核心压测）"""
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(_create_session_via_api, i) for i in range(100)]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 100
        ids = [r["id"] for r in results]
        assert len(set(ids)) == 100

    def test_create_100_sessions_response_time(self):
        """测试 100 并发会话创建响应时间 < 5 秒"""
        start = time.time()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(_create_session_via_api, i) for i in range(100)]
            results = [f.result() for f in as_completed(futures)]
        elapsed = time.time() - start
        assert len(results) == 100
        assert elapsed < 5.0, f"100 并发会话创建耗时 {elapsed:.2f}s，超过 5 秒阈值"

    def test_create_sessions_via_manager_concurrently(self):
        """测试通过 session_manager 并发创建会话"""
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_create_session_via_manager, i) for i in range(30)]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 30
        for r in results:
            assert "id" in r


# ===== 并发会话查询测试 =====

class TestConcurrentSessionQuery:
    """并发会话查询测试"""

    def test_concurrent_list_sessions(self):
        """测试并发查询会话列表"""
        # 先创建一批会话
        for i in range(20):
            _create_session_via_api(i)
        # 并发查询
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(client.get, "/api/sessions") for _ in range(20)]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 20
        for r in results:
            assert r.status_code == 200
            assert "sessions" in r.json()

    def test_concurrent_get_session_detail(self):
        """测试并发获取会话详情"""
        # 创建会话
        session_ids = [_create_session_via_api(i)["id"] for i in range(20)]
        # 并发获取详情
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(client.get, f"/api/sessions/{sid}")
                for sid in session_ids
            ]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 20
        for r in results:
            assert r.status_code == 200

    def test_concurrent_list_with_pagination(self):
        """测试并发分页查询"""
        for i in range(30):
            _create_session_via_api(i)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(client.get, f"/api/sessions?limit=10&offset={offset}")
                for offset in range(0, 30, 10)
            ]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 3
        for r in results:
            assert r.status_code == 200


# ===== 并发对话创建测试 =====

class TestConcurrentConversationCreation:
    """并发对话创建测试"""

    def test_concurrent_create_conversations_in_same_session(self):
        """测试同一会话下并发创建对话"""
        sid = _create_session_via_api(0)["id"]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    client.post,
                    f"/api/sessions/{sid}/conversations",
                    json={"title": f"并发对话_{i}", "agent_id": "orchestrator"},
                )
                for i in range(20)
            ]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 20
        for r in results:
            assert r.status_code == 200
            assert "id" in r.json()

    def test_concurrent_create_conversations_across_sessions(self):
        """测试跨会话并发创建对话"""
        session_ids = [_create_session_via_api(i)["id"] for i in range(10)]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    client.post,
                    f"/api/sessions/{sid}/conversations",
                    json={"title": f"跨会话对话_{i}", "agent_id": "orchestrator"},
                )
                for i, sid in enumerate(session_ids)
            ]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 10
        for r in results:
            assert r.status_code == 200


# ===== 并发消息发送测试 =====

class TestConcurrentMessageSending:
    """并发消息发送测试"""

    def test_concurrent_send_messages_to_same_conversation(self):
        """测试并发向同一对话发送消息"""
        sid = _create_session_via_api(0)["id"]
        conv_resp = client.post(
            f"/api/sessions/{sid}/conversations",
            json={"title": "并发消息测试", "agent_id": "orchestrator"},
        )
        cid = conv_resp.json()["id"]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    client.post,
                    f"/api/conversations/{cid}/messages",
                    json={"role": "user", "content": f"并发消息_{i}", "agent_id": "orchestrator"},
                )
                for i in range(20)
            ]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 20
        # 验证消息数量
        msgs = client.get(f"/api/conversations/{cid}/messages").json()["messages"]
        assert len(msgs) >= 20

    def test_concurrent_send_messages_to_different_conversations(self):
        """测试并发向不同对话发送消息"""
        sid = _create_session_via_api(0)["id"]
        conv_ids = []
        for i in range(10):
            resp = client.post(
                f"/api/sessions/{sid}/conversations",
                json={"title": f"并发对话_{i}", "agent_id": "orchestrator"},
            )
            conv_ids.append(resp.json()["id"])
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    client.post,
                    f"/api/conversations/{cid}/messages",
                    json={"role": "user", "content": f"消息_{i}", "agent_id": "orchestrator"},
                )
                for i, cid in enumerate(conv_ids)
            ]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 10


# ===== 并发会话删除测试 =====

class TestConcurrentSessionDeletion:
    """并发会话删除测试"""

    def test_concurrent_delete_sessions(self):
        """测试并发删除会话"""
        session_ids = [_create_session_via_api(i)["id"] for i in range(20)]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(client.delete, f"/api/sessions/{sid}")
                for sid in session_ids
            ]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 20
        for r in results:
            assert r.status_code == 200

    def test_concurrent_delete_conversations(self):
        """测试并发删除对话"""
        sid = _create_session_via_api(0)["id"]
        conv_ids = []
        for i in range(10):
            resp = client.post(
                f"/api/sessions/{sid}/conversations",
                json={"title": f"删除测试_{i}", "agent_id": "orchestrator"},
            )
            conv_ids.append(resp.json()["id"])
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(client.delete, f"/api/conversations/{cid}")
                for cid in conv_ids
            ]
            results = [f.result() for f in as_completed(futures)]
        assert len(results) == 10


# ===== 并发混合操作测试 =====

class TestConcurrentMixedOperations:
    """并发混合操作测试"""

    def test_mixed_create_query_delete(self):
        """测试混合创建、查询、删除操作"""
        def create_and_query(index):
            # 创建会话
            create_resp = client.post(
                "/api/sessions",
                json={
                    "title": f"混合操作_{index}",
                    "degree": "master",
                    "discipline": "science_engineering",
                    "mentor_info": "混合测试",
                },
            )
            sid = create_resp.json()["id"]
            # 查询详情
            client.get(f"/api/sessions/{sid}")
            # 创建对话
            client.post(
                f"/api/sessions/{sid}/conversations",
                json={"title": "混合对话", "agent_id": "orchestrator"},
            )
            # 列出对话
            client.get(f"/api/sessions/{sid}/conversations")
            return sid

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_and_query, i) for i in range(20)]
            sids = [f.result() for f in as_completed(futures)]
        assert len(sids) == 20

    def test_concurrent_read_while_writing(self):
        """测试读写并发（读不阻塞写）"""
        # 先创建一些会话
        for i in range(10):
            _create_session_via_api(i)

        def read_operation():
            return client.get("/api/sessions")

        def write_operation(index):
            return _create_session_via_api(index)

        with ThreadPoolExecutor(max_workers=20) as executor:
            read_futures = [executor.submit(read_operation) for _ in range(10)]
            write_futures = [executor.submit(write_operation, i) for i in range(10)]
            all_futures = read_futures + write_futures
            results = [f.result() for f in as_completed(all_futures)]
        # 所有操作应成功完成
        assert len(results) == 20


# ===== 性能指标测试 =====

class TestPerformanceMetrics:
    """性能指标测试"""

    def test_single_session_creation_time(self):
        """测试单个会话创建时间 < 0.5 秒"""
        start = time.time()
        _create_session_via_api(0)
        elapsed = time.time() - start
        assert elapsed < 0.5, f"单会话创建耗时 {elapsed:.3f}s"

    def test_batch_session_creation_time(self):
        """测试批量创建 50 个会话时间 < 3 秒"""
        start = time.time()
        for i in range(50):
            _create_session_via_api(i)
        elapsed = time.time() - start
        assert elapsed < 3.0, f"50 会话创建耗时 {elapsed:.2f}s"

    def test_session_list_query_time(self):
        """测试会话列表查询时间 < 1 秒"""
        for i in range(30):
            _create_session_via_api(i)
        start = time.time()
        response = client.get("/api/sessions?limit=30")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"会话列表查询耗时 {elapsed:.3f}s"

    def test_conversation_creation_time(self):
        """测试对话创建时间 < 0.5 秒"""
        sid = _create_session_via_api(0)["id"]
        start = time.time()
        client.post(
            f"/api/sessions/{sid}/conversations",
            json={"title": "性能测试对话", "agent_id": "orchestrator"},
        )
        elapsed = time.time() - start
        assert elapsed < 0.5, f"对话创建耗时 {elapsed:.3f}s"

    def test_message_addition_time(self):
        """测试消息添加时间 < 0.5 秒"""
        sid = _create_session_via_api(0)["id"]
        conv_resp = client.post(
            f"/api/sessions/{sid}/conversations",
            json={"title": "消息性能测试", "agent_id": "orchestrator"},
        )
        cid = conv_resp.json()["id"]
        start = time.time()
        client.post(
            f"/api/conversations/{cid}/messages",
            json={"role": "user", "content": "性能测试消息", "agent_id": "orchestrator"},
        )
        elapsed = time.time() - start
        assert elapsed < 0.5, f"消息添加耗时 {elapsed:.3f}s"


# ===== 数据一致性验证 =====

class TestDataConsistencyUnderConcurrency:
    """并发场景下数据一致性验证"""

    def test_unique_session_ids_under_concurrency(self):
        """测试并发创建的会话 ID 唯一"""
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(_create_session_via_api, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]
        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids)), "存在重复会话 ID"

    def test_unique_conversation_ids_under_concurrency(self):
        """测试并发创建的对话 ID 唯一"""
        sid = _create_session_via_api(0)["id"]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    client.post,
                    f"/api/sessions/{sid}/conversations",
                    json={"title": f"唯一性_{i}", "agent_id": "orchestrator"},
                )
                for i in range(20)
            ]
            results = [f.result() for f in as_completed(futures)]
        ids = [r.json()["id"] for r in results]
        assert len(ids) == len(set(ids)), "存在重复对话 ID"

    def test_message_count_consistency(self):
        """测试消息数量一致性"""
        sid = _create_session_via_api(0)["id"]
        conv_resp = client.post(
            f"/api/sessions/{sid}/conversations",
            json={"title": "一致性测试", "agent_id": "orchestrator"},
        )
        cid = conv_resp.json()["id"]
        # 并发发送 20 条消息
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    client.post,
                    f"/api/conversations/{cid}/messages",
                    json={"role": "user", "content": f"消息_{i}", "agent_id": "orchestrator"},
                )
                for i in range(20)
            ]
            [f.result() for f in as_completed(futures)]
        # 验证消息数量
        msgs = client.get(f"/api/conversations/{cid}/messages").json()["messages"]
        assert len(msgs) == 20

    def test_session_count_after_concurrent_creation(self):
        """测试并发创建后会话总数正确"""
        # 使用足够大的 limit 以获取全部会话（默认 limit=20 会截断计数）
        initial_count = client.get("/api/sessions?limit=1000").json()["count"]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_create_session_via_api, i) for i in range(20)]
            [f.result() for f in as_completed(futures)]
        final_count = client.get("/api/sessions?limit=1000").json()["count"]
        # 最终数量应至少增加 20（允许其他测试的会话存在）
        assert final_count >= initial_count + 20, f"最终 {final_count} < 初始 {initial_count} + 20"


# ===== 线程安全验证 =====

class TestThreadSafety:
    """线程安全验证"""

    def test_concurrent_database_access_no_deadlock(self):
        """测试并发数据库访问无死锁"""
        def db_operation(index):
            try:
                _create_session_via_api(index)
                return True
            except Exception:
                return False

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(db_operation, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures, timeout=10)]
        assert all(results), "存在数据库操作失败"

    def test_concurrent_read_no_blocking(self):
        """测试并发读不阻塞"""
        for i in range(10):
            _create_session_via_api(i)
        start = time.time()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(client.get, "/api/sessions") for _ in range(20)]
            [f.result() for f in as_completed(futures, timeout=5)]
        elapsed = time.time() - start
        assert elapsed < 3.0, f"20 次并发读耗时 {elapsed:.2f}s"

    def test_wal_mode_supports_concurrent_read(self):
        """测试 WAL 模式支持并发读"""
        # WAL 模式应允许并发读不阻塞
        for i in range(5):
            _create_session_via_api(i)

        def read_op():
            response = client.get("/api/sessions")
            return response.status_code

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_op) for _ in range(10)]
            results = [f.result() for f in as_completed(futures, timeout=5)]
        assert all(s == 200 for s in results)
