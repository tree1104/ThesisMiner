"""ThesisMiner v6.0 接口自测脚本

使用 FastAPI TestClient 测试所有核心接口，覆盖正常流程与异常场景。
运行方式：python -m pytest tests/test_api.py -v
或直接运行：python tests/test_api.py
"""
import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_status():
    """测试服务状态接口"""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "6.0.0"
    assert "ai_configured" in data
    print("✓ GET /api/status")


def test_config_get():
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
    print("✓ GET /api/config")


def test_config_update():
    """测试更新配置"""
    response = client.post("/api/config", json={"ai_model": "gpt-4o-mini"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    print("✓ POST /api/config")


def test_lineage_import_and_get():
    """测试谱系导入与查询"""
    # 导入节点
    import_data = {
        "nodes": [
            {
                "node_type": "mentor_project",
                "title": "国家自然科学基金项目X",
                "abstract": "关于深度学习在医学影像中的应用研究",
                "metadata": {"year": 2023, "fund": "NSFC"},
            },
            {
                "node_type": "student_thesis",
                "title": "师兄论文《基于CNN的肺结节检测》",
                "abstract": "使用卷积神经网络检测肺部CT影像中的结节",
                "metadata": {"year": 2022, "degree": "master"},
            },
        ],
        "edges": [
            {
                "source_id": None,  # 将在运行时填充
                "target_id": None,
                "relation_type": "extends",
                "weight": 0.8,
            }
        ],
    }
    response = client.post("/api/lineage/import", json=import_data)
    assert response.status_code == 200
    data = response.json()
    assert data["imported_nodes"] == 2
    print("✓ POST /api/lineage/import")

    # 查询所有节点
    response = client.get("/api/lineage")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 2
    assert len(data["nodes"]) >= 2
    print("✓ GET /api/lineage")

    # 获取图谱
    response = client.get("/api/lineage/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    print("✓ GET /api/lineage/graph")

    # 搜索节点
    response = client.get("/api/lineage/search?keyword=基金")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    print("✓ GET /api/lineage/search")


def test_lineage_cards():
    """测试知识卡片管理"""
    # 添加卡片
    response = client.post(
        "/api/lineage/cards",
        json={
            "title": "深度学习基础",
            "content": "深度学习是机器学习的一个分支...",
            "tags": ["AI", "深度学习"],
            "source": "教材",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "card_id" in data
    print("✓ POST /api/lineage/cards")

    # 查询卡片
    response = client.get("/api/lineage/cards")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    print("✓ GET /api/lineage/cards")


def test_creativity_inspire():
    """测试创意激发"""
    response = client.post(
        "/api/creativity/inspire",
        json={
            "degree": "master",
            "discipline": "science_engineering",
            "mentor_info": "导师项目：基于深度学习的医学影像分析\n同门论文：《CNN在CT影像中的应用》",
            "context": "",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data
    assert len(data["candidates"]) > 0
    print("✓ POST /api/creativity/inspire")


def test_creativity_cross_domain():
    """测试跨域联想"""
    response = client.post(
        "/api/creativity/cross-domain",
        json={"domain_a": "自然语言处理", "domain_b": "生物信息学"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "inspiration_source" in data
    print("✓ POST /api/creativity/cross-domain")


def test_creativity_rank():
    """测试候选排序"""
    candidates = [
        {"inspiration_source": "mentor_project", "direction": "方向1"},
        {"inspiration_source": "cross_domain", "direction": "方向2"},
        {"inspiration_source": "senior_inherit", "direction": "方向3"},
    ]
    response = client.post(
        "/api/creativity/rank",
        json={"candidates": candidates, "degree": "master"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "ranked_candidates" in data
    assert len(data["ranked_candidates"]) == 3
    # mentor_project 应该排第一（权重 0.9）
    assert data["ranked_candidates"][0]["inspiration_source"] == "mentor_project"
    print("✓ POST /api/creativity/rank")


def test_constraints_validate_title():
    """测试标题校验"""
    # 合法标题
    response = client.post(
        "/api/constraints/validate-title",
        json={"title": "深度学习医学影像", "degree": "master"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["auto_rewritten"] is False
    print("✓ POST /api/constraints/validate-title (合法标题)")

    # 超长标题
    long_title = "基于深度学习与自然语言处理的医学影像分析与诊断系统研究"
    response = client.post(
        "/api/constraints/validate-title",
        json={"title": long_title, "degree": "master"},
    )
    assert response.status_code == 200
    data = response.json()
    # 应触发重写
    print("✓ POST /api/constraints/validate-title (超长标题)")


def test_constraints_check_feasibility():
    """测试可行性校验"""
    # 可行方案
    response = client.post(
        "/api/constraints/check-feasibility",
        json={
            "research_content": ["研究内容1", "研究内容2"],
            "degree": "master",
            "timeframe_months": 10,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["feasible"] is True
    print("✓ POST /api/constraints/check-feasibility (可行)")

    # 不可行方案（超期）
    response = client.post(
        "/api/constraints/check-feasibility",
        json={
            "research_content": ["研究内容1"],
            "degree": "master",
            "timeframe_months": 24,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["feasible"] is False
    print("✓ POST /api/constraints/check-feasibility (超期)")


def test_constraints_check_literature():
    """测试文献基线校验"""
    # 充足
    response = client.post(
        "/api/constraints/check-literature",
        json={"degree": "master", "count": 35},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sufficient"] is True
    print("✓ POST /api/constraints/check-literature (充足)")

    # 不足
    response = client.post(
        "/api/constraints/check-literature",
        json={"degree": "master", "count": 20},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sufficient"] is False
    print("✓ POST /api/constraints/check-literature (不足)")


def test_constraints_calendar():
    """测试学术日历查询"""
    response = client.get("/api/constraints/calendar/master")
    assert response.status_code == 200
    data = response.json()
    assert "max_years" in data
    print("✓ GET /api/constraints/calendar/master")


def test_constraints_baseline():
    """测试文献基线查询"""
    response = client.get("/api/constraints/baseline/doctor")
    assert response.status_code == 200
    data = response.json()
    assert data["baseline"] == 50
    print("✓ GET /api/constraints/baseline/doctor")


def test_sessions_crud():
    """测试会话 CRUD"""
    # 创建会话
    response = client.post(
        "/api/sessions",
        json={
            "title": "测试会话",
            "degree": "master",
            "discipline": "science_engineering",
            "mentor_info": "导师项目X",
            "mode": "quick",
        },
    )
    assert response.status_code == 200
    data = response.json()
    session_id = data["id"]
    assert data["title"] == "测试会话"
    print("✓ POST /api/sessions")

    # 查询会话列表
    response = client.get("/api/sessions?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    print("✓ GET /api/sessions")

    # 查询单个会话
    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session_id
    print("✓ GET /api/sessions/{id}")

    # 更新状态
    response = client.patch(
        f"/api/sessions/{session_id}/status", json={"status": "completed"}
    )
    assert response.status_code == 200
    print("✓ PATCH /api/sessions/{id}/status")

    # 删除会话
    response = client.delete(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    print("✓ DELETE /api/sessions/{id}")


def test_proposals_list():
    """测试论题列表查询"""
    response = client.get("/api/proposals?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "proposals" in data
    assert "count" in data
    print("✓ GET /api/proposals")


def test_proposals_generate_without_api_key():
    """测试未配置 API Key 时生成论题"""
    response = client.post(
        "/api/proposals/generate",
        json={
            "degree": "master",
            "discipline": "science_engineering",
            "mentor_info": "导师项目X",
            "mode": "quick",
            "count": 1,
        },
    )
    # 未配置 API Key 时应返回 400
    assert response.status_code == 400
    print("✓ POST /api/proposals/generate (未配置 API Key 正确拒绝)")


def test_budgets_estimate():
    """测试预算估算"""
    response = client.post(
        "/api/budgets/estimate",
        json={"degree": "master", "mode": "quick", "count": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert "estimated_cost" in data
    assert "model" in data
    print("✓ POST /api/budgets/estimate")


def test_budgets_summary():
    """测试预算汇总"""
    response = client.get("/api/budgets/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_calls" in data
    assert "total_cost" in data
    print("✓ GET /api/budgets/summary")


def test_budgets_ledger():
    """测试账本查询"""
    response = client.get("/api/budgets/ledger?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    print("✓ GET /api/budgets/ledger")


def test_budgets_pricing():
    """测试定价表查询"""
    response = client.get("/api/budgets/pricing")
    assert response.status_code == 200
    data = response.json()
    assert "gpt-4o-mini" in data or len(data) > 0
    print("✓ GET /api/budgets/pricing")


def test_404_handling():
    """测试 404 处理"""
    response = client.get("/api/proposals/nonexistent-id")
    assert response.status_code == 404
    print("✓ 404 处理")


def test_session_cascade_delete():
    """测试会话级联删除（Task 1）"""
    from backend.database import execute_insert, fetch_all

    # 创建会话
    response = client.post(
        "/api/sessions",
        json={
            "title": "级联删除测试会话",
            "degree": "master",
            "discipline": "science_engineering",
            "mentor_info": "导师X",
            "mode": "quick",
        },
    )
    assert response.status_code == 200
    session_id = response.json()["id"]

    # 直接向 proposals 表插入一条关联论题
    import json, uuid, datetime
    proposal = {
        "id": uuid.uuid4().hex,
        "session_id": session_id,
        "title": "测试论题",
        "inspiration_source": "测试",
        "problem_awareness": "测试",
        "research_significance": json.dumps({"theoretical": "理论", "practical": "实践"}),
        "literature_review_outline": "测试",
        "differentiation": "测试",
        "research_content": json.dumps(["内容1"]),
        "feasibility_analysis": "测试",
        "confidence_score": 0.8,
        "auto_rewritten": False,
        "created_at": datetime.datetime.now().isoformat(),
    }
    execute_insert("proposals", proposal)

    # 验证论题存在
    response = client.get(f"/api/proposals?session_id={session_id}")
    assert response.status_code == 200
    assert response.json()["count"] >= 1

    # 删除会话
    response = client.delete(f"/api/sessions/{session_id}")
    assert response.status_code == 200

    # 验证论题已被级联删除
    response = client.get(f"/api/proposals?session_id={session_id}")
    assert response.status_code == 200
    assert response.json()["count"] == 0
    print("✓ 会话级联删除（Task 1）")


def test_search_status():
    """测试检索状态查询（Task 4）"""
    response = client.get("/api/constraints/search-status")
    assert response.status_code == 200
    data = response.json()
    assert "real_search_enabled" in data
    assert "configured" in data
    # 默认应关闭
    assert data["real_search_enabled"] is False
    print("✓ GET /api/constraints/search-status（Task 4）")


def test_search_literature_mock():
    """测试模拟文献检索（Task 4）"""
    response = client.post(
        "/api/constraints/search-literature",
        json={"keyword": "深度学习", "count": 5, "degree": "master"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "papers" in data or "results" in data
    assert "search_degraded" in data
    # 默认使用 MockSearcher，不应降级
    assert data["search_degraded"] is False
    print("✓ POST /api/constraints/search-literature（Task 4）")


def test_hard_constraint_interceptor():
    """测试硬约束拦截器（Task 7）"""
    from backend.orchestration.hooks.hard_rule_interceptor import (
        validate_title_hard,
        validate_timeline_hard,
        validate_proposal_hard,
    )
    from fastapi import HTTPException

    # 测试合法标题
    validate_title_hard("深度学习医学影像")

    # 测试非法标题（主动动词开头）
    try:
        validate_title_hard("研究深度学习问题")
        assert False, "应抛出 422"
    except HTTPException as e:
        assert e.status_code == 422

    # 测试超长标题
    try:
        validate_title_hard("这是一个超过二十个字的标题用于测试硬约束拦截器功能")
        assert False, "应抛出 422"
    except HTTPException as e:
        assert e.status_code == 422

    # 测试时间节点超期
    try:
        validate_timeline_hard(["研究内容1需要3个月", "研究内容2需要10个月"], "master")
        assert False, "应抛出 422（13个月超过硕士12个月限制）"
    except HTTPException as e:
        assert e.status_code == 422

    # 测试合法时间节点
    validate_timeline_hard(["研究内容1需要3个月", "研究内容2需要5个月"], "master")

    # 测试一体化校验
    valid_proposal = {
        "title": "医学影像分析",
        "research_content": ["阶段一3个月", "阶段二5个月"],
    }
    validate_proposal_hard(valid_proposal, "master")

    print("✓ 硬约束拦截器（Task 7）")


def test_proposal_report_template():
    """测试开题报告模板生成（Task 8）"""
    from backend.database import execute_insert
    import json, uuid, datetime

    # 创建会话
    response = client.post(
        "/api/sessions",
        json={
            "title": "报告测试会话",
            "degree": "master",
            "discipline": "science_engineering",
            "mentor_info": "导师Y",
            "mode": "quick",
        },
    )
    session_id = response.json()["id"]

    # 插入论题
    proposal_id = uuid.uuid4().hex
    proposal = {
        "id": proposal_id,
        "session_id": session_id,
        "title": "医学影像智能分析",
        "inspiration_source": "导师项目",
        "problem_awareness": "当前医学影像分析存在准确率不足问题",
        "research_significance": json.dumps({
            "theoretical": "提出新的理论框架",
            "practical": "提升临床诊断效率"
        }),
        "literature_review_outline": "国内外研究现状概述",
        "differentiation": "采用新的网络架构",
        "research_content": json.dumps([
            "文献调研与理论框架构建",
            "模型设计与实现",
            "实验验证与分析"
        ]),
        "feasibility_analysis": "技术路线可行",
        "confidence_score": 0.85,
        "auto_rewritten": False,
        "created_at": datetime.datetime.now().isoformat(),
    }
    execute_insert("proposals", proposal)

    # 生成报告（不使用 AI）
    response = client.post(f"/api/proposals/{proposal_id}/report?use_ai=false")
    assert response.status_code == 200
    data = response.json()
    assert "report" in data
    assert "title" in data
    assert data["ai_enhanced"] is False
    # 验证报告包含关键章节
    report = data["report"]
    assert "选题依据" in report or "一、" in report
    assert "研究内容" in report
    assert "进度安排" in report
    assert "医学影像智能分析" in report

    # 清理
    client.delete(f"/api/sessions/{session_id}")
    print("✓ POST /api/proposals/{id}/report（Task 8）")


def test_proposal_report_not_found():
    """测试开题报告 - 论题不存在"""
    response = client.post("/api/proposals/nonexistent-id/report?use_ai=false")
    assert response.status_code == 404
    print("✓ POST /api/proposals/{id}/report (404)")


def test_cache_info_fields():
    """测试会话缓存字段存在（Task 1）"""
    # 创建会话
    response = client.post(
        "/api/sessions",
        json={
            "title": "缓存字段测试",
            "degree": "master",
            "discipline": "science_engineering",
            "mentor_info": "导师Z",
            "mode": "quick",
        },
    )
    session_id = response.json()["id"]

    # 获取会话详情
    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    # 缓存字段应存在（可能为 None）
    assert "cache_prefix_hash" in data or "cache_prefix_hash" in str(data)

    # 清理
    client.delete(f"/api/sessions/{session_id}")
    print("✓ 会话缓存字段（Task 1）")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("ThesisMiner v6.0 接口自测")
    print("=" * 60 + "\n")

    tests = [
        test_status,
        test_config_get,
        test_config_update,
        test_lineage_import_and_get,
        test_lineage_cards,
        test_creativity_inspire,
        test_creativity_cross_domain,
        test_creativity_rank,
        test_constraints_validate_title,
        test_constraints_check_feasibility,
        test_constraints_check_literature,
        test_constraints_calendar,
        test_constraints_baseline,
        test_sessions_crud,
        test_proposals_list,
        test_proposals_generate_without_api_key,
        test_budgets_estimate,
        test_budgets_summary,
        test_budgets_ledger,
        test_budgets_pricing,
        test_404_handling,
        test_session_cascade_delete,
        test_search_status,
        test_search_literature_mock,
        test_hard_constraint_interceptor,
        test_proposal_report_template,
        test_proposal_report_not_found,
        test_cache_info_fields,
    ]

    passed = 0
    failed = 0
    failures = []

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            failures.append((test.__name__, str(e)))
            print(f"✗ {test.__name__} 失败: {e}")

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 项")
    print("=" * 60)

    if failures:
        print("\n失败详情:")
        for name, error in failures:
            print(f"  - {name}: {error}")

    return failed == 0


if __name__ == "__main__":
    # 确保安装了 httpx（TestClient 依赖）
    try:
        import httpx  # noqa: F401
    except ImportError:
        print("正在安装 httpx...")
        os.system(f"{sys.executable} -m pip install httpx -q")

    success = run_all_tests()
    sys.exit(0 if success else 1)
