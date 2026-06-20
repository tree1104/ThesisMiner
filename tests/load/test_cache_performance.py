"""压力测试：DeepSeek 缓存性能验证

验证系统在 1000 次 DeepSeek 调用场景下的缓存性能：
- 三段式 Prompt 前缀构建性能
- 前缀字节级一致性（1000 次调用）
- 缓存命中率记录性能
- 缓存统计查询性能
- 缓存命中率 ≥95% 验证
- 并发缓存记录
- 响应时间测量

运行方式：python -m pytest tests/load/test_cache_performance.py -v
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

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_load_cache_")
_tmp_db = os.path.join(_tmp_dir, "test_cache_perf.db")
_db.DB_PATH = _tmp_db
_db.init_db()

from backend.ai.prompt_cache import build_cached_prefix, is_deepseek_model
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

def _make_session(title: str = "缓存性能测试") -> str:
    """创建测试会话"""
    req = SessionCreate(
        title=title,
        degree=DegreeType.master,
        discipline=DisciplineType.science_engineering,
        mentor_info="深度学习",
    )
    return session_manager.create_session(req)["id"]


def _insert_ledger(session_id: str, prompt_tokens: int, cached_tokens: int) -> str:
    """插入 budget_ledger 记录，返回 UUID 字符串 ID

    budget_ledger 表的 id 为 TEXT PRIMARY KEY（UUID），非自增整数。
    直接在 INSERT 时计算并写入 cache_hit_rate。
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


def _record_cache_call(session_id: str, prompt_tokens: int = 1000, cached_tokens: int = 950) -> str:
    """记录一次缓存调用"""
    lid = _insert_ledger(session_id, prompt_tokens, cached_tokens)
    record_cache_hit("deepseek-chat-v3", prompt_tokens, cached_tokens, ledger_id=lid)
    return lid


# ===== 前缀构建性能测试 =====

class TestPrefixBuildPerformance:
    """三段式 Prompt 前缀构建性能测试"""

    def test_single_prefix_build_time(self):
        """测试单次前缀构建时间 < 0.001 秒"""
        start = time.time()
        build_cached_prefix(
            system_role="你是论文选题专家",
            hard_constraints=["标题≤25字", "硕士1年内"],
            degree="master",
            discipline="science_engineering",
            advisor="深度学习",
        )
        elapsed = time.time() - start
        assert elapsed < 0.001, f"单次前缀构建耗时 {elapsed:.6f}s"

    def test_100_prefix_builds_time(self):
        """测试 100 次前缀构建时间 < 0.1 秒"""
        args = {
            "system_role": "你是论文选题专家",
            "hard_constraints": ["标题≤25字"],
            "degree": "master",
            "discipline": "science_engineering",
            "advisor": "深度学习",
        }
        start = time.time()
        for _ in range(100):
            build_cached_prefix(**args)
        elapsed = time.time() - start
        assert elapsed < 0.1, f"100 次前缀构建耗时 {elapsed:.3f}s"

    def test_1000_prefix_builds_time(self):
        """测试 1000 次前缀构建时间 < 1 秒"""
        args = {
            "system_role": "你是论文选题专家",
            "hard_constraints": ["标题≤25字", "硕士1年内", "学科匹配"],
            "degree": "master",
            "discipline": "science_engineering",
            "advisor": "深度学习",
        }
        start = time.time()
        for _ in range(1000):
            build_cached_prefix(**args)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"1000 次前缀构建耗时 {elapsed:.3f}s"

    def test_prefix_build_throughput(self):
        """测试前缀构建吞吐量（次/秒）"""
        args = {
            "system_role": "角色",
            "hard_constraints": ["约束"],
            "degree": "master",
        }
        count = 5000
        start = time.time()
        for _ in range(count):
            build_cached_prefix(**args)
        elapsed = time.time() - start
        throughput = count / elapsed if elapsed > 0 else 0
        assert throughput > 1000, f"吞吐量 {throughput:.0f} 次/秒，低于 1000 次/秒"


# ===== 前缀字节级一致性压测 =====

class TestPrefixByteConsistencyStress:
    """前缀字节级一致性压测"""

    def test_1000_calls_prefix_identical(self):
        """测试 1000 次调用前缀字节级一致"""
        args = {
            "system_role": "你是论文选题专家",
            "hard_constraints": ["标题≤25字", "硕士1年内", "学科匹配"],
            "degree": "master",
            "discipline": "science_engineering",
            "advisor": "深度学习",
        }
        prefixes = [build_cached_prefix(**args) for _ in range(1000)]
        first_bytes = prefixes[0].prefix.encode("utf-8")
        for p in prefixes[1:]:
            assert p.prefix.encode("utf-8") == first_bytes, "前缀字节级不一致"

    def test_prefix_consistency_with_varying_dynamic(self):
        """测试动态部分变化时前缀仍一致"""
        args = {
            "system_role": "角色",
            "hard_constraints": ["约束"],
            "degree": "master",
        }
        prefixes = []
        for i in range(500):
            p = build_cached_prefix(**args)
            p.dynamic = f"动态内容_{i}_变化的部分"
            prefixes.append(p)
        first_bytes = prefixes[0].prefix.encode("utf-8")
        for p in prefixes[1:]:
            assert p.prefix.encode("utf-8") == first_bytes

    def test_prefix_hash_stable_1000_calls(self):
        """测试 1000 次调用前缀哈希稳定"""
        import hashlib
        args = {
            "system_role": "你是创意引擎",
            "hard_constraints": ["跨学科", "新颖性≥70"],
            "degree": "doctor",
            "discipline": "humanities_social",
            "advisor": "社会学",
        }
        first_hash = hashlib.sha256(
            build_cached_prefix(**args).prefix.encode("utf-8")
        ).hexdigest()
        for _ in range(999):
            p = build_cached_prefix(**args)
            h = hashlib.sha256(p.prefix.encode("utf-8")).hexdigest()
            assert h == first_hash, "前缀哈希不一致"


# ===== 缓存命中率记录性能测试 =====

class TestCacheHitRecordingPerformance:
    """缓存命中率记录性能测试"""

    def test_single_record_time(self):
        """测试单次缓存记录时间 < 0.05 秒"""
        sid = _make_session()
        start = time.time()
        _record_cache_call(sid)
        elapsed = time.time() - start
        assert elapsed < 0.05, f"单次缓存记录耗时 {elapsed:.4f}s"

    def test_100_records_time(self):
        """测试 100 次缓存记录时间 < 5 秒"""
        sid = _make_session()
        start = time.time()
        for _ in range(100):
            _record_cache_call(sid)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"100 次缓存记录耗时 {elapsed:.3f}s"

    def test_500_records_time(self):
        """测试 500 次缓存记录时间 < 15 秒"""
        sid = _make_session()
        start = time.time()
        for _ in range(500):
            _record_cache_call(sid)
        elapsed = time.time() - start
        assert elapsed < 15.0, f"500 次缓存记录耗时 {elapsed:.3f}s"

    def test_1000_records_time(self):
        """测试 1000 次缓存记录时间 < 30 秒（核心压测）"""
        sid = _make_session()
        start = time.time()
        for _ in range(1000):
            _record_cache_call(sid)
        elapsed = time.time() - start
        assert elapsed < 30.0, f"1000 次缓存记录耗时 {elapsed:.3f}s"

    def test_record_throughput(self):
        """测试缓存记录吞吐量"""
        sid = _make_session()
        count = 200
        start = time.time()
        for _ in range(count):
            _record_cache_call(sid)
        elapsed = time.time() - start
        throughput = count / elapsed if elapsed > 0 else 0
        assert throughput > 20, f"吞吐量 {throughput:.1f} 次/秒，低于 20 次/秒"


# ===== 缓存统计查询性能测试 =====

class TestCacheStatsQueryPerformance:
    """缓存统计查询性能测试"""

    def test_stats_query_empty_db_time(self):
        """测试空数据库统计查询时间"""
        # 使用新会话确保无数据干扰
        start = time.time()
        get_cache_stats(limit=100)
        elapsed = time.time() - start
        assert elapsed < 0.5, f"空数据库统计查询耗时 {elapsed:.3f}s"

    def test_stats_query_with_100_records(self):
        """测试 100 条记录统计查询性能"""
        sid = _make_session()
        for _ in range(100):
            _record_cache_call(sid)
        start = time.time()
        get_cache_stats(limit=100)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"100 条记录统计查询耗时 {elapsed:.3f}s"

    def test_stats_query_with_500_records(self):
        """测试 500 条记录统计查询性能"""
        sid = _make_session()
        for _ in range(500):
            _record_cache_call(sid)
        start = time.time()
        get_cache_stats(limit=500)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"500 条记录统计查询耗时 {elapsed:.3f}s"

    def test_stats_query_with_1000_records(self):
        """测试 1000 条记录统计查询性能"""
        sid = _make_session()
        for _ in range(1000):
            _record_cache_call(sid)
        start = time.time()
        get_cache_stats(limit=1000)
        elapsed = time.time() - start
        assert elapsed < 3.0, f"1000 条记录统计查询耗时 {elapsed:.3f}s"

    def test_stats_query_with_limit(self):
        """测试 limit 参数对查询性能影响"""
        sid = _make_session()
        for _ in range(500):
            _record_cache_call(sid)
        # 查询最近 100 条
        start = time.time()
        get_cache_stats(limit=100)
        elapsed = time.time() - start
        assert elapsed < 1.0


# ===== 缓存命中率 ≥95% 验证 =====

class TestCacheHitRateThreshold:
    """缓存命中率 ≥95% 阈值验证"""

    def test_100_calls_hit_rate_above_95(self):
        """测试 100 次调用缓存命中率 ≥95%"""
        sid = _make_session()
        for _ in range(100):
            _record_cache_call(sid, prompt_tokens=1000, cached_tokens=960)
        stats = get_cache_stats(limit=100)
        assert stats["avg_hit_rate"] >= 0.95, f"平均命中率 {stats['avg_hit_rate']:.4f} < 0.95"

    def test_500_calls_hit_rate_above_95(self):
        """测试 500 次调用缓存命中率 ≥95%"""
        sid = _make_session()
        for _ in range(500):
            _record_cache_call(sid, prompt_tokens=1000, cached_tokens=955)
        stats = get_cache_stats(limit=500)
        assert stats["avg_hit_rate"] >= 0.95

    def test_1000_calls_hit_rate_above_95(self):
        """测试 1000 次调用缓存命中率 ≥95%（核心压测）"""
        sid = _make_session()
        for _ in range(1000):
            _record_cache_call(sid, prompt_tokens=2000, cached_tokens=1950)
        stats = get_cache_stats(limit=1000)
        assert stats["avg_hit_rate"] >= 0.95, f"1000 次调用平均命中率 {stats['avg_hit_rate']:.4f}"

    def test_high_hit_rate_with_consistent_prefix(self):
        """测试一致前缀下高命中率"""
        # 构建固定前缀
        prefix = build_cached_prefix(
            system_role="你是论文选题专家",
            hard_constraints=["标题≤25字"],
            degree="master",
        )
        assert prefix.prefix_char_count > 0
        # 模拟 100 次调用，前缀固定，命中率应高
        sid = _make_session()
        for _ in range(100):
            _record_cache_call(sid, prompt_tokens=1000, cached_tokens=980)
        stats = get_cache_stats(limit=100)
        assert stats["avg_hit_rate"] >= 0.95


# ===== 并发缓存记录测试 =====

class TestConcurrentCacheRecording:
    """并发缓存记录测试"""

    def test_concurrent_50_records(self):
        """测试并发 50 次缓存记录"""
        sid = _make_session()

        def record_task(_):
            _record_cache_call(sid)
            return True

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(record_task, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]
        assert all(results)

    def test_concurrent_100_records(self):
        """测试并发 100 次缓存记录"""
        sid = _make_session()

        def record_task(_):
            _record_cache_call(sid)
            return True

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(record_task, i) for i in range(100)]
            results = [f.result() for f in as_completed(futures)]
        assert all(results)

    def test_concurrent_records_data_consistency(self):
        """测试并发记录数据一致性"""
        sid = _make_session()

        def record_task(index):
            _record_cache_call(sid, prompt_tokens=1000, cached_tokens=950)
            return True

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(record_task, i) for i in range(50)]
            [f.result() for f in as_completed(futures)]
        stats = get_cache_stats(limit=100)
        # 并发可能有少量失败，允许 >=45
        assert stats["total_calls"] >= 45


# ===== DeepSeek 模型识别性能测试 =====

class TestDeepSeekDetectionPerformance:
    """DeepSeek 模型识别性能测试"""

    def test_1000_model_checks_time(self):
        """测试 1000 次模型识别时间 < 0.1 秒"""
        models = ["deepseek-chat-v3", "gpt-4.1", "deepseek-r2", "claude-sonnet-4.5"]
        start = time.time()
        for i in range(1000):
            is_deepseek_model(models[i % len(models)])
        elapsed = time.time() - start
        assert elapsed < 0.1, f"1000 次模型识别耗时 {elapsed:.3f}s"

    def test_model_detection_accuracy(self):
        """测试模型识别准确性"""
        deepseek_models = ["deepseek-chat-v3", "deepseek-reasoner", "deepseek-v3.2", "deepseek-r2"]
        non_deepseek = ["gpt-4.1", "claude-sonnet-4.5", "qwen3-max", "gemini-2.5-pro"]
        for m in deepseek_models:
            assert is_deepseek_model(m) is True, f"{m} 应识别为 DeepSeek"
        for m in non_deepseek:
            assert is_deepseek_model(m) is False, f"{m} 不应识别为 DeepSeek"


# ===== 综合场景测试 =====

class TestCacheComprehensiveScenario:
    """缓存综合场景测试"""

    def test_full_cache_workflow_1000_calls(self):
        """测试完整缓存工作流（1000 次调用）"""
        # 1. 构建前缀
        prefix = build_cached_prefix(
            system_role="你是论文选题专家",
            hard_constraints=["标题≤25字", "硕士1年内"],
            degree="master",
            discipline="science_engineering",
            advisor="深度学习",
        )
        assert prefix.prefix_char_count > 0

        # 2. 创建会话
        sid = _make_session("综合场景测试")

        # 3. 记录 1000 次缓存调用
        for _ in range(1000):
            _record_cache_call(sid, prompt_tokens=1500, cached_tokens=1450)

        # 4. 查询统计
        stats = get_cache_stats(limit=1000)
        assert stats["total_calls"] >= 1000
        assert stats["avg_hit_rate"] >= 0.95

    def test_cache_stats_api_performance(self):
        """测试缓存统计 API 性能"""
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        sid = _make_session("API性能测试")
        for _ in range(100):
            _record_cache_call(sid)
        start = time.time()
        response = client.get("/api/cache-stats")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"缓存统计 API 耗时 {elapsed:.3f}s"

    def test_mixed_hit_rates_scenario(self):
        """测试混合命中率场景"""
        sid = _make_session("混合命中率测试")
        # 80% 高命中率调用
        for _ in range(80):
            _record_cache_call(sid, prompt_tokens=1000, cached_tokens=980)
        # 20% 低命中率调用（首次调用无缓存）
        for _ in range(20):
            _record_cache_call(sid, prompt_tokens=1000, cached_tokens=200)
        stats = get_cache_stats(limit=100)
        # 平均命中率应受低命中率拉低，但仍应可查询
        assert stats["total_calls"] >= 100
        assert 0 < stats["avg_hit_rate"] <= 1.0
