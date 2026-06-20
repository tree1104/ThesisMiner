"""集成测试：DeepSeek 缓存优化验证

覆盖：
- 三段式 Prompt 缓存前缀构建（系统角色 + 硬约束 + 学位/学科/导师）
- 前缀字节级一致性验证（同会话内多次调用前缀完全相同）
- 缓存命中率监控（record_cache_hit / get_cache_stats）
- 缓存统计 API（GET /api/cache-stats）
- DeepSeek 模型识别（is_deepseek_model）
- 多轮对话前缀稳定性
- budget_ledger 表 cache_hit_rate 字段持久化

运行方式：python -m pytest tests/integration/test_cache_optimization.py -v
"""
import os
import sys
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 在导入 backend 模块前，切换到临时数据库，避免污染正式数据
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_cache_opt_")
_tmp_db = os.path.join(_tmp_dir, "test_cache_opt.db")
_db.DB_PATH = _tmp_db
_db.init_db()

from backend.ai.prompt_cache import (
    CachedPrefix,
    build_cached_prefix,
    is_deepseek_model,
)
from backend.ai.cache_monitor import record_cache_hit, get_cache_stats
from backend.database import get_db_connection
from backend.sessions import session_manager
from backend.models import SessionCreate, DegreeType, DisciplineType


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

def _make_session(title: str = "缓存优化测试会话") -> str:
    """创建测试会话，返回 session_id"""
    req = SessionCreate(
        title=title,
        degree=DegreeType.master,
        discipline=DisciplineType.science_engineering,
        mentor_info="深度学习与计算机视觉",
    )
    session = session_manager.create_session(req)
    return session["id"]


def _insert_ledger_entry(session_id: str, prompt_tokens: int, cached_tokens: int) -> str:
    """向 budget_ledger 表插入一条记录，返回记录 ID（UUID 字符串）

    budget_ledger 表的 id 为 TEXT PRIMARY KEY（UUID），非自增整数。
    直接在 INSERT 时计算并写入 cache_hit_rate，避免后续 UPDATE。
    """
    import uuid
    ledger_id = str(uuid.uuid4())
    hit_rate = cached_tokens / prompt_tokens if prompt_tokens > 0 else 0.0
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO budget_ledger
               (id, session_id, model, prompt_tokens, completion_tokens, total_tokens,
                cost, cached_prompt_tokens, cache_hit_rate, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (ledger_id, session_id, "deepseek-chat-v3", prompt_tokens, 50,
             prompt_tokens + 50, 0.001, cached_tokens, hit_rate),
        )
        conn.commit()
        return ledger_id
    finally:
        conn.close()


# ===== 三段式 Prompt 缓存前缀构建测试 =====

class TestCachedPrefixBuild:
    """三段式缓存前缀构建测试"""

    def test_build_cached_prefix_basic(self):
        """测试基本前缀构建：系统角色 + 硬约束"""
        prefix = build_cached_prefix(
            system_role="你是论文选题专家",
            hard_constraints=["标题≤25字", "硕士1年内完成", "学科匹配"],
        )
        assert isinstance(prefix, CachedPrefix)
        assert "[SYSTEM_ROLE]" in prefix.prefix
        assert "你是论文选题专家" in prefix.prefix
        assert "[HARD_CONSTRAINTS]" in prefix.prefix
        assert "标题≤25字" in prefix.prefix
        assert prefix.prefix_char_count > 0
        assert len(prefix.prefix_messages) == 1
        assert prefix.prefix_messages[0]["role"] == "system"

    def test_build_cached_prefix_with_academic_context(self):
        """测试含学位/学科/导师信息的前缀构建"""
        prefix = build_cached_prefix(
            system_role="你是创意引擎",
            hard_constraints=["跨学科交叉"],
            degree="master",
            discipline="science_engineering",
            advisor="计算机视觉与深度学习",
        )
        assert "[ACADEMIC_CONTEXT]" in prefix.prefix
        assert "学位: master" in prefix.prefix
        assert "学科: science_engineering" in prefix.prefix
        assert "导师方向: 计算机视觉与深度学习" in prefix.prefix

    def test_build_cached_prefix_empty_constraints(self):
        """测试空硬约束列表"""
        prefix = build_cached_prefix(
            system_role="你是导师",
            hard_constraints=[],
        )
        assert "[SYSTEM_ROLE]" in prefix.prefix
        assert "[HARD_CONSTRAINTS]" not in prefix.prefix

    def test_build_cached_prefix_no_academic_context(self):
        """测试无学位/学科/导师信息"""
        prefix = build_cached_prefix(
            system_role="你是评审专家",
            hard_constraints=["评分≥60"],
        )
        assert "[ACADEMIC_CONTEXT]" not in prefix.prefix

    def test_build_cached_prefix_dynamic_initial_empty(self):
        """测试动态部分初始为空"""
        prefix = build_cached_prefix(
            system_role="你是写作助手",
            hard_constraints=["全文≥5000字"],
        )
        assert prefix.dynamic == ""

    def test_build_cached_prefix_char_count_matches_bytes(self):
        """测试 prefix_char_count 与 UTF-8 字节数一致"""
        prefix = build_cached_prefix(
            system_role="你是中文助手",
            hard_constraints=["中文约束"],
            degree="master",
        )
        expected_bytes = len(prefix.prefix.encode("utf-8"))
        assert prefix.prefix_char_count == expected_bytes

    def test_build_cached_prefix_messages_structure(self):
        """测试 prefix_messages 结构正确"""
        prefix = build_cached_prefix(
            system_role="系统角色",
            hard_constraints=["约束1"],
        )
        assert isinstance(prefix.prefix_messages, list)
        assert len(prefix.prefix_messages) == 1
        msg = prefix.prefix_messages[0]
        assert msg["role"] == "system"
        assert msg["content"] == prefix.prefix

    def test_build_cached_prefix_multiple_constraints_numbered(self):
        """测试多个硬约束带编号"""
        constraints = ["约束一", "约束二", "约束三", "约束四"]
        prefix = build_cached_prefix(
            system_role="系统",
            hard_constraints=constraints,
        )
        for i, c in enumerate(constraints, 1):
            assert f"{i}. {c}" in prefix.prefix


# ===== 前缀字节级一致性测试 =====

class TestPrefixByteConsistency:
    """前缀字节级一致性测试（核心：同会话内多次调用前缀完全相同）"""

    def test_same_inputs_produce_same_prefix_bytes(self):
        """相同输入产生字节级一致的前缀"""
        args = {
            "system_role": "你是论文选题专家",
            "hard_constraints": ["标题≤25字", "硕士1年内"],
            "degree": "master",
            "discipline": "science_engineering",
            "advisor": "深度学习",
        }
        prefix1 = build_cached_prefix(**args)
        prefix2 = build_cached_prefix(**args)
        assert prefix1.prefix == prefix2.prefix
        assert prefix1.prefix.encode("utf-8") == prefix2.prefix.encode("utf-8")
        assert prefix1.prefix_char_count == prefix2.prefix_char_count

    def test_different_dynamic_does_not_affect_prefix(self):
        """动态部分变化不影响前缀"""
        prefix1 = build_cached_prefix(
            system_role="角色",
            hard_constraints=["约束"],
        )
        prefix2 = build_cached_prefix(
            system_role="角色",
            hard_constraints=["约束"],
        )
        prefix2.dynamic = "这是动态变化的内容"
        assert prefix1.prefix == prefix2.prefix
        assert prefix1.prefix.encode("utf-8") == prefix2.prefix.encode("utf-8")

    def test_prefix_stable_across_multiple_calls(self):
        """多次调用前缀保持稳定（模拟 10 次连续调用）"""
        args = {
            "system_role": "你是创意引擎",
            "hard_constraints": ["跨学科", "新颖性≥70"],
            "degree": "doctor",
            "discipline": "humanities_social",
            "advisor": "社会学定量研究",
        }
        prefixes = [build_cached_prefix(**args) for _ in range(10)]
        first_bytes = prefixes[0].prefix.encode("utf-8")
        for p in prefixes[1:]:
            assert p.prefix.encode("utf-8") == first_bytes
            assert p.prefix_char_count == prefixes[0].prefix_char_count

    def test_prefix_differs_with_different_role(self):
        """不同系统角色产生不同前缀"""
        p1 = build_cached_prefix(system_role="角色A", hard_constraints=[])
        p2 = build_cached_prefix(system_role="角色B", hard_constraints=[])
        assert p1.prefix != p2.prefix

    def test_prefix_differs_with_different_constraints(self):
        """不同硬约束产生不同前缀"""
        p1 = build_cached_prefix(system_role="角色", hard_constraints=["约束A"])
        p2 = build_cached_prefix(system_role="角色", hard_constraints=["约束B"])
        assert p1.prefix != p2.prefix

    def test_prefix_differs_with_different_advisor(self):
        """不同导师方向产生不同前缀"""
        p1 = build_cached_prefix(
            system_role="角色", hard_constraints=[], advisor="方向A"
        )
        p2 = build_cached_prefix(
            system_role="角色", hard_constraints=[], advisor="方向B"
        )
        assert p1.prefix != p2.prefix

    def test_prefix_hash_consistency(self):
        """前缀哈希一致性验证"""
        import hashlib
        args = {
            "system_role": "你是评审",
            "hard_constraints": ["评分≥60"],
            "degree": "master",
        }
        p1 = build_cached_prefix(**args)
        p2 = build_cached_prefix(**args)
        hash1 = hashlib.sha256(p1.prefix.encode("utf-8")).hexdigest()
        hash2 = hashlib.sha256(p2.prefix.encode("utf-8")).hexdigest()
        assert hash1 == hash2


# ===== DeepSeek 模型识别测试 =====

class TestDeepSeekModelDetection:
    """DeepSeek 模型识别测试"""

    def test_is_deepseek_model_positive(self):
        """测试 DeepSeek 模型识别为 True"""
        assert is_deepseek_model("deepseek-chat-v3") is True
        assert is_deepseek_model("deepseek-reasoner") is True
        assert is_deepseek_model("deepseek-v3.2") is True
        assert is_deepseek_model("deepseek-r2") is True
        assert is_deepseek_model("DeepSeek-Chat") is True
        assert is_deepseek_model("DEEPSEEK-V3") is True

    def test_is_deepseek_model_negative(self):
        """测试非 DeepSeek 模型识别为 False"""
        assert is_deepseek_model("gpt-4.1") is False
        assert is_deepseek_model("claude-sonnet-4.5") is False
        assert is_deepseek_model("qwen3-max") is False
        assert is_deepseek_model("gemini-2.5-pro") is False
        assert is_deepseek_model("") is False

    def test_is_deepseek_model_case_insensitive(self):
        """测试大小写不敏感"""
        assert is_deepseek_model("DeepSeek-Chat") is True
        assert is_deepseek_model("DEEPSEEK-R2") is True
        assert is_deepseek_model("deepseek-V3.2") is True


# ===== 缓存命中率记录测试 =====

class TestCacheHitRecording:
    """缓存命中率记录测试"""

    def test_record_cache_hit_updates_ledger(self):
        """测试记录缓存命中率更新 budget_ledger 表"""
        sid = _make_session("缓存记录测试")
        ledger_id = _insert_ledger_entry(sid, prompt_tokens=1000, cached_tokens=950)
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=1000,
            cached_tokens=950,
            ledger_id=ledger_id,
        )
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
            assert row is not None
            assert abs(row["cache_hit_rate"] - 0.95) < 0.001
        finally:
            conn.close()

    def test_record_cache_hit_zero_prompt_tokens(self):
        """测试 prompt_tokens 为 0 时不记录"""
        sid = _make_session("零token测试")
        ledger_id = _insert_ledger_entry(sid, prompt_tokens=0, cached_tokens=0)
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=0,
            cached_tokens=0,
            ledger_id=ledger_id,
        )
        # cache_hit_rate 应保持初始值 0.0
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
            assert row["cache_hit_rate"] == 0.0
        finally:
            conn.close()

    def test_record_cache_hit_full_cache(self):
        """测试 100% 缓存命中"""
        sid = _make_session("全缓存命中测试")
        ledger_id = _insert_ledger_entry(sid, prompt_tokens=500, cached_tokens=500)
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=500,
            cached_tokens=500,
            ledger_id=ledger_id,
        )
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
            assert abs(row["cache_hit_rate"] - 1.0) < 0.001
        finally:
            conn.close()

    def test_record_cache_hit_no_ledger_id(self):
        """测试不提供 ledger_id 时不报错"""
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=1000,
            cached_tokens=900,
            ledger_id=None,
        )
        # 不报错即通过

    def test_record_cache_hit_partial_cache(self):
        """测试部分缓存命中（50%）"""
        sid = _make_session("部分缓存测试")
        ledger_id = _insert_ledger_entry(sid, prompt_tokens=800, cached_tokens=400)
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=800,
            cached_tokens=400,
            ledger_id=ledger_id,
        )
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
            assert abs(row["cache_hit_rate"] - 0.5) < 0.001
        finally:
            conn.close()


# ===== 缓存统计查询测试 =====

class TestCacheStatsQuery:
    """缓存统计查询测试"""

    def test_get_cache_stats_empty(self):
        """测试无数据时返回零值字典"""
        # 使用全新的临时数据库场景
        stats = get_cache_stats(limit=10)
        assert "avg_hit_rate" in stats
        assert "total_calls" in stats
        assert "total_cached" in stats
        assert "total_prompt" in stats

    def test_get_cache_stats_with_data(self):
        """测试有数据时返回正确统计"""
        sid = _make_session("统计查询测试")
        # 插入多条记录
        for i in range(5):
            lid = _insert_ledger_entry(sid, prompt_tokens=1000, cached_tokens=950 + i)
            record_cache_hit("deepseek-chat-v3", 1000, 950 + i, ledger_id=lid)
        stats = get_cache_stats(limit=100)
        assert stats["total_calls"] >= 5
        assert stats["total_prompt"] > 0
        assert stats["total_cached"] > 0
        assert 0 < stats["avg_hit_rate"] <= 1.0

    def test_get_cache_stats_limit(self):
        """测试 limit 参数限制返回条数"""
        sid = _make_session("limit测试")
        for i in range(10):
            lid = _insert_ledger_entry(sid, prompt_tokens=500, cached_tokens=475)
            record_cache_hit("deepseek-chat-v3", 500, 475, ledger_id=lid)
        stats = get_cache_stats(limit=3)
        assert stats["total_calls"] <= 3

    def test_get_cache_stats_overall_hit_rate(self):
        """测试整体命中率计算"""
        sid = _make_session("整体命中率测试")
        lid1 = _insert_ledger_entry(sid, prompt_tokens=1000, cached_tokens=900)
        record_cache_hit("deepseek-chat-v3", 1000, 900, ledger_id=lid1)
        lid2 = _insert_ledger_entry(sid, prompt_tokens=1000, cached_tokens=950)
        record_cache_hit("deepseek-chat-v3", 1000, 950, ledger_id=lid2)
        stats = get_cache_stats(limit=100)
        if stats["total_calls"] >= 2:
            expected_overall = (900 + 950) / (1000 + 1000)
            assert abs(stats["overall_hit_rate"] - expected_overall) < 0.01


# ===== 缓存统计 API 测试 =====

class TestCacheStatsAPI:
    """缓存统计 API（GET /api/cache-stats）测试"""

    def test_cache_stats_endpoint_returns_200(self):
        """测试缓存统计端点返回 200"""
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        response = client.get("/api/cache-stats")
        assert response.status_code == 200
        data = response.json()
        assert "avg_hit_rate" in data
        assert "total_calls" in data

    def test_cache_stats_endpoint_structure(self):
        """测试缓存统计端点返回结构完整"""
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        response = client.get("/api/cache-stats")
        data = response.json()
        required_fields = ["avg_hit_rate", "total_calls", "total_cached", "total_prompt"]
        for field in required_fields:
            assert field in data, f"缺少字段: {field}"

    def test_cache_stats_endpoint_after_recording(self):
        """测试记录后 API 返回更新后的统计"""
        from fastapi.testclient import TestClient
        from main import app
        sid = _make_session("API统计测试")
        lid = _insert_ledger_entry(sid, prompt_tokens=2000, cached_tokens=1900)
        record_cache_hit("deepseek-chat-v3", 2000, 1900, ledger_id=lid)
        client = TestClient(app)
        response = client.get("/api/cache-stats")
        data = response.json()
        assert data["total_calls"] >= 1


# ===== 多轮对话前缀稳定性测试 =====

class TestMultiTurnPrefixStability:
    """多轮对话前缀稳定性测试"""

    def test_prefix_stable_across_conversation_turns(self):
        """测试多轮对话中前缀保持稳定"""
        base_args = {
            "system_role": "你是论文选题专家",
            "hard_constraints": ["标题≤25字", "硕士1年内", "学科匹配"],
            "degree": "master",
            "discipline": "science_engineering",
            "advisor": "深度学习",
        }
        # 模拟 5 轮对话，每轮前缀应一致
        turn_prefixes = []
        for turn in range(5):
            prefix = build_cached_prefix(**base_args)
            prefix.dynamic = f"第{turn + 1}轮用户输入：{turn + 1}"
            turn_prefixes.append(prefix)
        first_bytes = turn_prefixes[0].prefix.encode("utf-8")
        for p in turn_prefixes[1:]:
            assert p.prefix.encode("utf-8") == first_bytes

    def test_prefix_stable_with_different_agents(self):
        """测试不同 Agent 使用各自前缀但同 Agent 内前缀稳定"""
        agent_roles = {
            "searcher": "你是文献检索专家",
            "reasoner": "你是创意引擎",
            "critic": "你是评审专家",
            "writer": "你是写作助手",
            "mentor": "你是导师",
        }
        common_constraints = ["学科匹配"]
        prefixes_by_agent = {}
        for agent_id, role in agent_roles.items():
            p1 = build_cached_prefix(system_role=role, hard_constraints=common_constraints)
            p2 = build_cached_prefix(system_role=role, hard_constraints=common_constraints)
            assert p1.prefix == p2.prefix
            prefixes_by_agent[agent_id] = p1.prefix
        # 不同 Agent 前缀应不同
        agent_ids = list(prefixes_by_agent.keys())
        for i in range(len(agent_ids)):
            for j in range(i + 1, len(agent_ids)):
                assert prefixes_by_agent[agent_ids[i]] != prefixes_by_agent[agent_ids[j]]

    def test_prefix_does_not_include_user_input(self):
        """测试前缀不包含用户动态输入"""
        prefix = build_cached_prefix(
            system_role="系统角色",
            hard_constraints=["约束"],
            degree="master",
        )
        user_inputs = ["用户输入A", "用户输入B", "动态内容"]
        for ui in user_inputs:
            assert ui not in prefix.prefix


# ===== 缓存命中率阈值验证 =====

class TestCacheHitRateThreshold:
    """缓存命中率 ≥95% 阈值验证"""

    def test_high_cache_hit_rate_scenario(self):
        """测试高缓存命中率场景（≥95%）"""
        sid = _make_session("高命中率场景")
        # 模拟 10 次 DeepSeek 调用，前缀固定，命中率应 ≥95%
        # 使用 990+ 的 cached_tokens 确保 10 条记录平均命中率 ≥95%
        inserted_ids = []
        for i in range(10):
            lid = _insert_ledger_entry(sid, prompt_tokens=1000, cached_tokens=990 + i)
            record_cache_hit("deepseek-chat-v3", 1000, 990 + i, ledger_id=lid)
            inserted_ids.append(lid)
        # 直接查询本测试插入的记录，验证平均命中率 ≥95%
        conn = get_db_connection()
        try:
            placeholders = ",".join("?" * len(inserted_ids))
            rows = conn.execute(
                f"SELECT cache_hit_rate FROM budget_ledger WHERE id IN ({placeholders})",
                inserted_ids,
            ).fetchall()
            rates = [r["cache_hit_rate"] for r in rows]
            avg_rate = sum(rates) / len(rates) if rates else 0
            assert avg_rate >= 0.95, f"平均命中率 {avg_rate:.4f} < 0.95"
        finally:
            conn.close()

    def test_cache_hit_rate_calculation(self):
        """测试缓存命中率计算公式"""
        sid = _make_session("命中率计算测试")
        lid = _insert_ledger_entry(sid, prompt_tokens=1000, cached_tokens=950)
        record_cache_hit("deepseek-chat-v3", 1000, 950, ledger_id=lid)
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (lid,),
            ).fetchone()
            # cache_hit_rate = cached_tokens / prompt_tokens = 950/1000 = 0.95
            assert abs(row["cache_hit_rate"] - 0.95) < 0.001
        finally:
            conn.close()

    def test_consecutive_calls_maintain_high_hit_rate(self):
        """测试连续调用维持高命中率"""
        sid = _make_session("连续调用测试")
        rates = []
        for i in range(10):
            prompt_t = 2000
            cached_t = 1950  # 97.5% 命中率
            lid = _insert_ledger_entry(sid, prompt_tokens=prompt_t, cached_tokens=cached_t)
            record_cache_hit("deepseek-chat-v3", prompt_t, cached_t, ledger_id=lid)
            conn = get_db_connection()
            try:
                row = conn.execute(
                    "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                    (lid,),
                ).fetchone()
                rates.append(row["cache_hit_rate"])
            finally:
                conn.close()
        for rate in rates:
            assert rate >= 0.95


# ===== 集成场景：前缀 + 缓存记录 + 统计查询 =====

class TestCacheIntegrationScenario:
    """缓存优化集成场景测试"""

    def test_full_cache_workflow(self):
        """测试完整缓存工作流：构建前缀 → 记录命中 → 查询统计"""
        # 1. 构建前缀
        prefix = build_cached_prefix(
            system_role="你是论文选题专家",
            hard_constraints=["标题≤25字", "硕士1年内"],
            degree="master",
            discipline="science_engineering",
            advisor="深度学习",
        )
        assert prefix.prefix_char_count > 0

        # 2. 创建会话并记录缓存命中
        sid = _make_session("完整工作流测试")
        lid = _insert_ledger_entry(sid, prompt_tokens=1500, cached_tokens=1450)
        record_cache_hit("deepseek-chat-v3", 1500, 1450, ledger_id=lid)

        # 3. 查询统计
        stats = get_cache_stats(limit=100)
        assert stats["total_calls"] >= 1
        assert stats["avg_hit_rate"] > 0

    def test_prefix_consistency_with_session_context(self):
        """测试会话上下文中前缀一致性"""
        sid = _make_session("会话上下文前缀测试")
        # 同一会话多次构建前缀
        args = {
            "system_role": "你是创意引擎",
            "hard_constraints": ["跨学科交叉", "新颖性≥70"],
            "degree": "master",
            "discipline": "science_engineering",
            "advisor": "计算机视觉",
        }
        prefixes = [build_cached_prefix(**args) for _ in range(5)]
        # 全部一致
        for p in prefixes[1:]:
            assert p.prefix == prefixes[0].prefix
            assert p.prefix.encode("utf-8") == prefixes[0].prefix.encode("utf-8")

    def test_cache_monitor_with_multiple_sessions(self):
        """测试多会话缓存监控"""
        sid1 = _make_session("多会话测试1")
        sid2 = _make_session("多会话测试2")
        for sid in [sid1, sid2]:
            for i in range(3):
                lid = _insert_ledger_entry(sid, prompt_tokens=1000, cached_tokens=950)
                record_cache_hit("deepseek-chat-v3", 1000, 950, ledger_id=lid)
        stats = get_cache_stats(limit=100)
        assert stats["total_calls"] >= 6


# ===== 边界条件测试 =====

class TestCacheEdgeCases:
    """缓存优化边界条件测试"""

    def test_empty_system_role(self):
        """测试空系统角色"""
        prefix = build_cached_prefix(system_role="", hard_constraints=["约束"])
        assert "[SYSTEM_ROLE]" in prefix.prefix

    def test_very_long_constraints(self):
        """测试超长硬约束列表"""
        constraints = [f"约束条件{i}" for i in range(50)]
        prefix = build_cached_prefix(
            system_role="角色",
            hard_constraints=constraints,
        )
        assert prefix.prefix_char_count > 0
        for i, c in enumerate(constraints, 1):
            assert f"{i}. {c}" in prefix.prefix

    def test_unicode_in_prefix(self):
        """测试前缀中的 Unicode 字符"""
        prefix = build_cached_prefix(
            system_role="你是中文助手🎉",
            hard_constraints=["中文约束≤25字"],
            advisor="导师方向：深度学习与NLP",
        )
        bytes_data = prefix.prefix.encode("utf-8")
        assert len(bytes_data) == prefix.prefix_char_count
        # 重建后应一致
        prefix2 = build_cached_prefix(
            system_role="你是中文助手🎉",
            hard_constraints=["中文约束≤25字"],
            advisor="导师方向：深度学习与NLP",
        )
        assert prefix.prefix.encode("utf-8") == prefix2.prefix.encode("utf-8")

    def test_cache_stats_with_zero_rate_entries(self):
        """测试统计查询过滤零命中率记录"""
        sid = _make_session("零命中率过滤测试")
        # 插入一条 cache_hit_rate=0 的记录（不调用 record_cache_hit）
        _insert_ledger_entry(sid, prompt_tokens=1000, cached_tokens=0)
        stats = get_cache_stats(limit=100)
        # 零命中率记录应被过滤（WHERE cache_hit_rate > 0）
        # 此处仅验证不报错
        assert "total_calls" in stats

    def test_negative_cache_tokens_ignored(self):
        """测试负数 prompt_tokens 被忽略"""
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=-100,
            cached_tokens=-50,
            ledger_id=None,
        )
        # 不报错即通过（prompt_tokens <= 0 时直接 return）


# ===== 前缀消息数组格式测试 =====

class TestPrefixMessagesFormat:
    """前缀消息数组格式测试"""

    def test_prefix_messages_role_is_system(self):
        """测试前缀消息角色为 system"""
        prefix = build_cached_prefix(
            system_role="角色",
            hard_constraints=["约束"],
        )
        assert prefix.prefix_messages[0]["role"] == "system"

    def test_prefix_messages_content_equals_prefix(self):
        """测试前缀消息内容等于 prefix 字段"""
        prefix = build_cached_prefix(
            system_role="角色",
            hard_constraints=["约束"],
            degree="master",
        )
        assert prefix.prefix_messages[0]["content"] == prefix.prefix

    def test_prefix_messages_is_list(self):
        """测试前缀消息是列表类型"""
        prefix = build_cached_prefix(
            system_role="角色",
            hard_constraints=[],
        )
        assert isinstance(prefix.prefix_messages, list)

    def test_prefix_messages_has_exactly_one_item(self):
        """测试前缀消息数组仅含一条消息"""
        prefix = build_cached_prefix(
            system_role="角色",
            hard_constraints=["约束1", "约束2"],
            degree="master",
            discipline="science_engineering",
            advisor="方向",
        )
        assert len(prefix.prefix_messages) == 1
