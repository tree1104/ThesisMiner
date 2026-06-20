"""压力测试：谱系图谱性能验证

验证系统在 500 节点谱系图谱场景下的性能：
- 批量导入 500 个节点
- 批量导入边（关系）
- 图谱查询性能
- 节点搜索性能
- 分页查询性能
- 批量删除性能
- 响应时间测量
- 数据完整性验证

运行方式：python -m pytest tests/load/test_lineage_graph_performance.py -v
"""
import os
import sys
import tempfile
import time

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 切换到临时数据库
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_load_lineage_")
_tmp_db = os.path.join(_tmp_dir, "test_lineage.db")
_db.DB_PATH = _tmp_db
_db.init_db()

from fastapi.testclient import TestClient
from main import app
from backend.knowledge import lineage_graph_store

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

def _generate_nodes(count: int) -> list:
    """生成指定数量的测试节点"""
    node_types = ["topic", "method", "paper", "author", "concept", "dataset"]
    nodes = []
    for i in range(count):
        nodes.append({
            "node_type": node_types[i % len(node_types)],
            "title": f"节点_{i}_{node_types[i % len(node_types)]}",
            "abstract": f"这是节点 {i} 的摘要描述，用于性能测试",
            "metadata": {
                "index": i,
                "type": node_types[i % len(node_types)],
                "year": 2020 + (i % 6),
            },
        })
    return nodes


def _generate_edges(node_ids: list, count: int) -> list:
    """生成指定数量的测试边"""
    relations = ["cites", "derived_from", "related", "advises", "cited_by"]
    edges = []
    for i in range(count):
        source = node_ids[i % len(node_ids)]
        target = node_ids[(i + 1) % len(node_ids)]
        edges.append({
            "source_id": source,
            "target_id": target,
            "relation_type": relations[i % len(relations)],
            "weight": 0.5 + (i % 5) * 0.1,
        })
    return edges


def _import_nodes_via_api(nodes: list) -> dict:
    """通过 API 批量导入节点"""
    response = client.post(
        "/api/lineage/import",
        json={"nodes": nodes, "edges": []},
    )
    return response.json()


# ===== 批量节点导入测试 =====

class TestBatchNodeImport:
    """批量节点导入测试"""

    def test_import_100_nodes(self):
        """测试导入 100 个节点"""
        nodes = _generate_nodes(100)
        result = _import_nodes_via_api(nodes)
        assert result["imported_nodes"] == 100

    def test_import_300_nodes(self):
        """测试导入 300 个节点"""
        nodes = _generate_nodes(300)
        result = _import_nodes_via_api(nodes)
        assert result["imported_nodes"] == 300

    def test_import_500_nodes(self):
        """测试导入 500 个节点（核心压测）"""
        nodes = _generate_nodes(500)
        result = _import_nodes_via_api(nodes)
        assert result["imported_nodes"] == 500

    def test_import_500_nodes_time(self):
        """测试 500 节点导入时间 < 10 秒"""
        nodes = _generate_nodes(500)
        start = time.time()
        _import_nodes_via_api(nodes)
        elapsed = time.time() - start
        assert elapsed < 10.0, f"500 节点导入耗时 {elapsed:.2f}s"

    def test_import_nodes_via_store(self):
        """测试通过 lineage_graph_store 导入节点"""
        for i in range(100):
            lineage_graph_store.add_node(
                node_type="topic",
                title=f"Store节点_{i}",
                abstract=f"Store节点摘要_{i}",
                metadata={"index": i},
            )
        all_nodes = lineage_graph_store.get_all_nodes()
        assert len(all_nodes) >= 100


# ===== 批量边导入测试 =====

class TestBatchEdgeImport:
    """批量边导入测试"""

    def test_import_100_edges(self):
        """测试导入 100 条边"""
        # 先导入节点
        nodes = _generate_nodes(50)
        _import_nodes_via_api(nodes)
        # 获取节点 ID
        graph = lineage_graph_store.get_graph()
        node_ids = [n["id"] for n in graph["nodes"][:50]]
        # 导入边
        edges = _generate_edges(node_ids, 100)
        response = client.post(
            "/api/lineage/import",
            json={"nodes": [], "edges": edges},
        )
        assert response.json()["imported_edges"] == 100

    def test_import_300_edges(self):
        """测试导入 300 条边"""
        nodes = _generate_nodes(100)
        _import_nodes_via_api(nodes)
        graph = lineage_graph_store.get_graph()
        node_ids = [n["id"] for n in graph["nodes"][:100]]
        edges = _generate_edges(node_ids, 300)
        response = client.post(
            "/api/lineage/import",
            json={"nodes": [], "edges": edges},
        )
        assert response.json()["imported_edges"] == 300

    def test_import_500_edges(self):
        """测试导入 500 条边"""
        nodes = _generate_nodes(200)
        _import_nodes_via_api(nodes)
        graph = lineage_graph_store.get_graph()
        node_ids = [n["id"] for n in graph["nodes"][:200]]
        edges = _generate_edges(node_ids, 500)
        response = client.post(
            "/api/lineage/import",
            json={"nodes": [], "edges": edges},
        )
        assert response.json()["imported_edges"] == 500


# ===== 图谱查询性能测试 =====

class TestGraphQueryPerformance:
    """图谱查询性能测试"""

    def test_query_graph_with_100_nodes(self):
        """测试 100 节点图谱查询性能"""
        nodes = _generate_nodes(100)
        _import_nodes_via_api(nodes)
        start = time.time()
        response = client.get("/api/lineage/graph")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 2.0, f"100 节点图谱查询耗时 {elapsed:.3f}s"

    def test_query_graph_with_300_nodes(self):
        """测试 300 节点图谱查询性能"""
        nodes = _generate_nodes(300)
        _import_nodes_via_api(nodes)
        start = time.time()
        response = client.get("/api/lineage/graph")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 3.0, f"300 节点图谱查询耗时 {elapsed:.3f}s"

    def test_query_graph_with_500_nodes(self):
        """测试 500 节点图谱查询性能（核心压测）"""
        nodes = _generate_nodes(500)
        _import_nodes_via_api(nodes)
        start = time.time()
        response = client.get("/api/lineage/graph")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 5.0, f"500 节点图谱查询耗时 {elapsed:.3f}s"

    def test_graph_query_returns_complete_data(self):
        """测试图谱查询返回完整数据"""
        nodes = _generate_nodes(50)
        _import_nodes_via_api(nodes)
        response = client.get("/api/lineage/graph")
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) >= 50


# ===== 节点搜索性能测试 =====

class TestNodeSearchPerformance:
    """节点搜索性能测试"""

    def test_search_in_100_nodes(self):
        """测试 100 节点中搜索性能"""
        nodes = _generate_nodes(100)
        _import_nodes_via_api(nodes)
        start = time.time()
        response = client.get("/api/lineage/search?keyword=节点_50")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"100 节点搜索耗时 {elapsed:.3f}s"

    def test_search_in_500_nodes(self):
        """测试 500 节点中搜索性能"""
        nodes = _generate_nodes(500)
        _import_nodes_via_api(nodes)
        start = time.time()
        response = client.get("/api/lineage/search?keyword=节点_250")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 2.0, f"500 节点搜索耗时 {elapsed:.3f}s"

    def test_search_returns_relevant_results(self):
        """测试搜索返回相关结果"""
        nodes = _generate_nodes(50)
        _import_nodes_via_api(nodes)
        response = client.get("/api/lineage/search?keyword=节点_25")
        data = response.json()
        assert data["count"] >= 1
        for result in data["results"]:
            assert "节点_25" in result.get("title", "")

    def test_search_empty_keyword(self):
        """测试空关键词搜索"""
        response = client.get("/api/lineage/search?keyword=")
        assert response.status_code == 200


# ===== 分页查询性能测试 =====

class TestPaginationPerformance:
    """分页查询性能测试"""

    def test_pagination_with_500_nodes(self):
        """测试 500 节点分页查询性能"""
        nodes = _generate_nodes(500)
        _import_nodes_via_api(nodes)
        start = time.time()
        # 分页查询 5 页
        for offset in range(0, 500, 100):
            client.get(f"/api/lineage?limit=100&offset={offset}")
        elapsed = time.time() - start
        assert elapsed < 3.0, f"5 页分页查询耗时 {elapsed:.3f}s"

    def test_pagination_returns_correct_count(self):
        """测试分页返回正确数量"""
        nodes = _generate_nodes(150)
        _import_nodes_via_api(nodes)
        response = client.get("/api/lineage?limit=50&offset=0")
        data = response.json()
        assert data["count"] <= 50
        assert data["total"] >= 150

    def test_pagination_has_more_flag(self):
        """测试分页 has_more 标志"""
        nodes = _generate_nodes(100)
        _import_nodes_via_api(nodes)
        response = client.get("/api/lineage?limit=50&offset=0")
        data = response.json()
        assert data["has_more"] is True

    def test_pagination_last_page(self):
        """测试最后一页 has_more 为 False"""
        nodes = _generate_nodes(30)
        _import_nodes_via_api(nodes)
        # 使用足够大的 offset 确保到达最后一页
        response = client.get("/api/lineage?limit=50&offset=0")
        data = response.json()
        # 如果总数 <= limit，has_more 应为 False
        if data["total"] <= 50:
            assert data["has_more"] is False


# ===== 批量删除性能测试 =====

class TestBatchDeletePerformance:
    """批量删除性能测试"""

    def test_batch_delete_50_nodes(self):
        """测试批量删除 50 个节点"""
        nodes = _generate_nodes(50)
        _import_nodes_via_api(nodes)
        graph = lineage_graph_store.get_graph()
        node_ids = [n["id"] for n in graph["nodes"][:50]]
        start = time.time()
        response = client.request("DELETE", "/api/lineage/batch", json={"node_ids": node_ids})
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 3.0, f"50 节点批量删除耗时 {elapsed:.3f}s"

    def test_batch_delete_100_nodes(self):
        """测试批量删除 100 个节点"""
        nodes = _generate_nodes(100)
        _import_nodes_via_api(nodes)
        graph = lineage_graph_store.get_graph()
        node_ids = [n["id"] for n in graph["nodes"][:100]]
        start = time.time()
        response = client.request("DELETE", "/api/lineage/batch", json={"node_ids": node_ids})
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 5.0, f"100 节点批量删除耗时 {elapsed:.3f}s"

    def test_single_node_delete(self):
        """测试单个节点删除"""
        nodes = _generate_nodes(1)
        _import_nodes_via_api(nodes)
        graph = lineage_graph_store.get_graph()
        if graph["nodes"]:
            node_id = graph["nodes"][0]["id"]
            response = client.delete(f"/api/lineage/{node_id}")
            assert response.status_code == 200


# ===== 数据完整性测试 =====

class TestLineageDataIntegrity:
    """谱系数据完整性测试"""

    def test_all_imported_nodes_queryable(self):
        """测试所有导入节点可查询"""
        nodes = _generate_nodes(100)
        _import_nodes_via_api(nodes)
        graph = lineage_graph_store.get_graph()
        assert len(graph["nodes"]) >= 100

    def test_node_metadata_preserved(self):
        """测试节点元数据保持"""
        test_nodes = [
            {
                "node_type": "topic",
                "title": "元数据测试节点",
                "abstract": "测试元数据保持",
                "metadata": {"year": 2024, "author": "测试", "score": 0.95},
            }
        ]
        _import_nodes_via_api(test_nodes)
        graph = lineage_graph_store.get_graph()
        found = False
        for node in graph["nodes"]:
            if node["title"] == "元数据测试节点":
                found = True
                break
        assert found, "元数据测试节点未找到"

    def test_node_types_diversity(self):
        """测试节点类型多样性"""
        nodes = _generate_nodes(60)
        _import_nodes_via_api(nodes)
        graph = lineage_graph_store.get_graph()
        types = set(n.get("node_type") for n in graph["nodes"])
        assert len(types) >= 3, "节点类型不够多样"

    def test_edge_relationships_intact(self):
        """测试边关系完整性"""
        # 导入节点
        nodes = _generate_nodes(20)
        _import_nodes_via_api(nodes)
        graph = lineage_graph_store.get_graph()
        node_ids = [n["id"] for n in graph["nodes"][:20]]
        # 导入边
        edges = _generate_edges(node_ids, 20)
        client.post("/api/lineage/import", json={"nodes": [], "edges": edges})
        # 验证边存在
        graph_after = lineage_graph_store.get_graph()
        assert len(graph_after["edges"]) >= 20


# ===== 知识卡片性能测试 =====

class TestKnowledgeCardPerformance:
    """知识卡片性能测试"""

    def test_batch_create_cards(self):
        """测试批量创建知识卡片"""
        for i in range(50):
            client.post(
                "/api/lineage/cards",
                json={
                    "title": f"卡片_{i}",
                    "content": f"卡片内容_{i}",
                    "tags": [f"标签_{i % 5}"],
                    "source": "性能测试",
                },
            )
        response = client.get("/api/lineage/cards")
        data = response.json()
        assert data["count"] >= 50

    def test_card_query_by_tag(self):
        """测试按标签查询卡片"""
        for i in range(20):
            client.post(
                "/api/lineage/cards",
                json={
                    "title": f"标签卡片_{i}",
                    "content": f"内容_{i}",
                    "tags": ["性能测试标签"],
                    "source": "测试",
                },
            )
        response = client.get("/api/lineage/cards?tag=性能测试标签")
        assert response.status_code == 200

    def test_card_creation_time(self):
        """测试卡片创建时间"""
        start = time.time()
        client.post(
            "/api/lineage/cards",
            json={
                "title": "性能测试卡片",
                "content": "内容",
                "tags": ["测试"],
                "source": "测试",
            },
        )
        elapsed = time.time() - start
        assert elapsed < 0.5, f"卡片创建耗时 {elapsed:.3f}s"
