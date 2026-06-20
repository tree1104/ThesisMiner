"""cache_monitor 模块单元测试

测试 backend/ai/cache_monitor.py 的 record_cache_hit 与 get_cache_stats 函数。
验证 DeepSeek 缓存命中率监控逻辑：
  - record_cache_hit 正确计算并写入 cache_hit_rate
  - 边界条件（prompt_tokens <= 0 不写入）
  - get_cache_stats 聚合统计逻辑
  - 无数据时返回零值字典
  - ledger_id 关联更新
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

# ===== 临时数据库初始化（必须在导入 backend.database 之前覆盖 DB_PATH）=====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_cache_monitor_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.ai.cache_monitor import record_cache_hit, get_cache_stats
from backend.database import get_db_connection


def _insert_session(session_id: str = None) -> str:
    """辅助函数：向 sessions 表插入一条记录以满足外键约束。

    budget_ledger.session_id 外键引用 sessions.id，
    因此插入 ledger 前必须先插入对应 session。
    """
    sid = session_id or f"test-session-{uuid.uuid4().hex[:8]}"
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO sessions (id, title, created_at)
               VALUES (?, ?, datetime('now'))""",
            (sid, "测试会话"),
        )
        conn.commit()
    finally:
        conn.close()
    return sid


def _insert_ledger_row(prompt_tokens: int = 1000,
                       completion_tokens: int = 200,
                       cached_prompt_tokens: int = 0,
                       cache_hit_rate: float = 0.0,
                       model: str = "deepseek-chat-v3",
                       session_id: str = None) -> str:
    """辅助函数：向 budget_ledger 表插入一条记录并返回其 id。

    用于在测试中构造前置数据，便于 record_cache_hit 与 get_cache_stats 验证。
    id 为 TEXT 类型（UUID），需先插入 session 满足外键。
    """
    sid = _insert_session(session_id)
    ledger_id = f"ledger-{uuid.uuid4().hex[:12]}"
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO budget_ledger
               (id, session_id, model, prompt_tokens, completion_tokens,
                total_tokens, cached_prompt_tokens, cache_hit_rate, cost,
                purpose, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (ledger_id, sid, model, prompt_tokens, completion_tokens,
             prompt_tokens + completion_tokens, cached_prompt_tokens,
             cache_hit_rate, 0.0, "test"),
        )
        conn.commit()
    finally:
        conn.close()
    return ledger_id


def _clear_ledger():
    """辅助函数：清空 budget_ledger 与 sessions 表，确保测试间数据隔离。"""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM budget_ledger")
        conn.execute("DELETE FROM sessions")
        conn.commit()
    finally:
        conn.close()


class TestRecordCacheHit:
    """测试 record_cache_hit 函数"""

    def setup_method(self):
        """每个测试方法前清空 ledger 表"""
        _clear_ledger()

    def test_record_with_valid_tokens_and_ledger_id(self):
        """测试：传入有效 token 数与 ledger_id，应更新对应行的 cache_hit_rate"""
        ledger_id = _insert_ledger_row(prompt_tokens=1000, cached_prompt_tokens=0)
        # 记录缓存命中：800/1000 = 0.8
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=1000,
            cached_tokens=800,
            ledger_id=ledger_id,
        )
        # 验证数据库中 cache_hit_rate 已更新
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == pytest.approx(0.8, abs=1e-6)

    def test_record_with_zero_prompt_tokens_skips_update(self):
        """测试：prompt_tokens=0 时应跳过更新（边界条件）"""
        ledger_id = _insert_ledger_row(prompt_tokens=500, cache_hit_rate=0.5)
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=0,
            cached_tokens=0,
            ledger_id=ledger_id,
        )
        # 验证 cache_hit_rate 未被修改
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == 0.5

    def test_record_with_negative_prompt_tokens_skips_update(self):
        """测试：prompt_tokens 为负数时应跳过更新"""
        ledger_id = _insert_ledger_row(prompt_tokens=500, cache_hit_rate=0.3)
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=-100,
            cached_tokens=50,
            ledger_id=ledger_id,
        )
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == 0.3

    def test_record_without_ledger_id_does_not_crash(self):
        """测试：不传 ledger_id 时不应报错（仅计算不写入）"""
        # 不应抛出异常
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=1000,
            cached_tokens=950,
            ledger_id=None,
        )
        # 验证 ledger 表仍为空
        conn = get_db_connection()
        try:
            count = conn.execute("SELECT COUNT(*) FROM budget_ledger").fetchone()[0]
        finally:
            conn.close()
        assert count == 0

    def test_record_full_cache_hit(self):
        """测试：cached_tokens == prompt_tokens 时命中率为 1.0"""
        ledger_id = _insert_ledger_row(prompt_tokens=2000)
        record_cache_hit(
            model_id="deepseek-r2",
            prompt_tokens=2000,
            cached_tokens=2000,
            ledger_id=ledger_id,
        )
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == pytest.approx(1.0, abs=1e-6)

    def test_record_zero_cached_tokens(self):
        """测试：cached_tokens=0 时命中率为 0.0"""
        ledger_id = _insert_ledger_row(prompt_tokens=1500)
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=1500,
            cached_tokens=0,
            ledger_id=ledger_id,
        )
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == pytest.approx(0.0, abs=1e-6)

    def test_record_high_cache_hit_rate_above_threshold(self):
        """测试：缓存命中率达到 95% 阈值以上"""
        ledger_id = _insert_ledger_row(prompt_tokens=10000)
        record_cache_hit(
            model_id="deepseek-chat-v3",
            prompt_tokens=10000,
            cached_tokens=9600,
            ledger_id=ledger_id,
        )
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == pytest.approx(0.96, abs=1e-6)
        assert row[0] >= 0.95  # 满足 ≥95% 目标

    def test_record_multiple_calls_update_respective_rows(self):
        """测试：多次调用分别更新不同的 ledger 行"""
        id1 = _insert_ledger_row(prompt_tokens=1000)
        id2 = _insert_ledger_row(prompt_tokens=2000)
        record_cache_hit("deepseek-chat-v3", 1000, 900, ledger_id=id1)
        record_cache_hit("deepseek-r2", 2000, 1500, ledger_id=id2)
        conn = get_db_connection()
        try:
            r1 = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?", (id1,)
            ).fetchone()
            r2 = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?", (id2,)
            ).fetchone()
        finally:
            conn.close()
        assert r1[0] == pytest.approx(0.9, abs=1e-6)
        assert r2[0] == pytest.approx(0.75, abs=1e-6)

    def test_record_non_deepseek_model_still_works(self):
        """测试：非 DeepSeek 模型调用 record_cache_hit 也能正常写入

        record_cache_hit 不区分模型，仅做计算与写入。
        """
        ledger_id = _insert_ledger_row(prompt_tokens=800, model="gpt-4.1")
        record_cache_hit(
            model_id="gpt-4.1",
            prompt_tokens=800,
            cached_tokens=0,
            ledger_id=ledger_id,
        )
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == pytest.approx(0.0, abs=1e-6)

    def test_record_overwrites_existing_rate(self):
        """测试：对同一 ledger_id 多次调用，后一次覆盖前一次的值"""
        ledger_id = _insert_ledger_row(prompt_tokens=1000, cache_hit_rate=0.5)
        record_cache_hit("deepseek-chat-v3", 1000, 800, ledger_id=ledger_id)
        record_cache_hit("deepseek-chat-v3", 1000, 950, ledger_id=ledger_id)
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT cache_hit_rate FROM budget_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == pytest.approx(0.95, abs=1e-6)


class TestGetCacheStats:
    """测试 get_cache_stats 函数"""

    def setup_method(self):
        """每个测试方法前清空 ledger 表"""
        _clear_ledger()

    def test_stats_empty_database_returns_zero_values(self):
        """测试：空数据库时应返回零值统计字典"""
        stats = get_cache_stats()
        assert stats["avg_hit_rate"] == 0.0
        assert stats["total_calls"] == 0
        assert stats["total_cached"] == 0
        assert stats["total_prompt"] == 0

    def test_stats_single_record(self):
        """测试：单条记录时正确计算统计"""
        ledger_id = _insert_ledger_row(
            prompt_tokens=1000, cached_prompt_tokens=900
        )
        record_cache_hit("deepseek-chat-v3", 1000, 900, ledger_id=ledger_id)
        stats = get_cache_stats()
        assert stats["total_calls"] == 1
        assert stats["total_cached"] == 900
        assert stats["total_prompt"] == 1000
        assert stats["avg_hit_rate"] == pytest.approx(0.9, abs=1e-6)
        assert stats["overall_hit_rate"] == pytest.approx(0.9, abs=1e-6)

    def test_stats_multiple_records(self):
        """测试：多条记录时正确聚合统计"""
        # 记录1: 1000 prompt, 900 cached
        id1 = _insert_ledger_row(prompt_tokens=1000, cached_prompt_tokens=900)
        record_cache_hit("deepseek-chat-v3", 1000, 900, ledger_id=id1)
        # 记录2: 2000 prompt, 1500 cached
        id2 = _insert_ledger_row(prompt_tokens=2000, cached_prompt_tokens=1500)
        record_cache_hit("deepseek-r2", 2000, 1500, ledger_id=id2)
        stats = get_cache_stats()
        assert stats["total_calls"] == 2
        assert stats["total_cached"] == 2400
        assert stats["total_prompt"] == 3000
        # avg_hit_rate = (0.9 + 0.75) / 2 = 0.825
        assert stats["avg_hit_rate"] == pytest.approx(0.825, abs=1e-6)
        # overall_hit_rate = 2400 / 3000 = 0.8
        assert stats["overall_hit_rate"] == pytest.approx(0.8, abs=1e-6)

    def test_stats_respects_limit_parameter(self):
        """测试：limit 参数限制返回的记录数"""
        # 插入 5 条记录
        for i in range(5):
            lid = _insert_ledger_row(
                prompt_tokens=1000, cached_prompt_tokens=800
            )
            record_cache_hit("deepseek-chat-v3", 1000, 800, ledger_id=lid)
        # 限制只取最近 3 条
        stats = get_cache_stats(limit=3)
        assert stats["total_calls"] == 3
        assert stats["total_cached"] == 2400
        assert stats["total_prompt"] == 3000

    def test_stats_filters_zero_rate_rows(self):
        """测试：cache_hit_rate=0 的行不参与统计"""
        # 一条有命中率的记录
        id1 = _insert_ledger_row(prompt_tokens=1000, cached_prompt_tokens=900)
        record_cache_hit("deepseek-chat-v3", 1000, 900, ledger_id=id1)
        # 一条命中率为 0 的记录（未调用 record_cache_hit，cache_hit_rate 保持默认 0）
        _insert_ledger_row(prompt_tokens=2000, cached_prompt_tokens=0)
        stats = get_cache_stats()
        # 只统计 cache_hit_rate > 0 的行
        assert stats["total_calls"] == 1

    def test_stats_default_limit_is_100(self):
        """测试：默认 limit 为 100"""
        # 插入 150 条记录
        for i in range(150):
            lid = _insert_ledger_row(
                prompt_tokens=100, cached_prompt_tokens=80
            )
            record_cache_hit("deepseek-chat-v3", 100, 80, ledger_id=lid)
        stats = get_cache_stats()
        # 默认 limit=100，只统计最近 100 条
        assert stats["total_calls"] == 100

    def test_stats_overall_hit_rate_calculation(self):
        """测试：overall_hit_rate = total_cached / total_prompt"""
        id1 = _insert_ledger_row(prompt_tokens=500, cached_prompt_tokens=400)
        record_cache_hit("deepseek-chat-v3", 500, 400, ledger_id=id1)
        id2 = _insert_ledger_row(prompt_tokens=1500, cached_prompt_tokens=1200)
        record_cache_hit("deepseek-r2", 1500, 1200, ledger_id=id2)
        stats = get_cache_stats()
        # overall = (400 + 1200) / (500 + 1500) = 1600 / 2000 = 0.8
        assert stats["overall_hit_rate"] == pytest.approx(0.8, abs=1e-6)

    def test_stats_avg_vs_overall_difference(self):
        """测试：avg_hit_rate（算术平均）与 overall_hit_rate（加权平均）的差异

        当各记录 prompt_tokens 不同时，两者会有差异。
        """
        # 记录1: 100 prompt, 100 cached -> rate=1.0
        id1 = _insert_ledger_row(prompt_tokens=100, cached_prompt_tokens=100)
        record_cache_hit("deepseek-chat-v3", 100, 100, ledger_id=id1)
        # 记录2: 1000 prompt, 500 cached -> rate=0.5
        id2 = _insert_ledger_row(prompt_tokens=1000, cached_prompt_tokens=500)
        record_cache_hit("deepseek-r2", 1000, 500, ledger_id=id2)
        stats = get_cache_stats()
        # avg = (1.0 + 0.5) / 2 = 0.75
        assert stats["avg_hit_rate"] == pytest.approx(0.75, abs=1e-6)
        # overall = 600 / 1100 ≈ 0.545
        assert stats["overall_hit_rate"] == pytest.approx(600 / 1100, abs=1e-6)

    def test_stats_with_zero_prompt_tokens_record_excluded(self):
        """测试：prompt_tokens=0 的记录（若 cache_hit_rate>0）边界情况

        由于 record_cache_hit 在 prompt_tokens<=0 时不写入，
        所以这种记录的 cache_hit_rate 保持 0，会被 get_cache_stats 过滤。
        """
        _insert_ledger_row(prompt_tokens=0, cached_prompt_tokens=0)
        stats = get_cache_stats()
        assert stats["total_calls"] == 0

    def test_stats_returns_dict_with_required_keys(self):
        """测试：返回的字典包含所有必需的键"""
        id1 = _insert_ledger_row(prompt_tokens=100, cached_prompt_tokens=80)
        record_cache_hit("deepseek-chat-v3", 100, 80, ledger_id=id1)
        stats = get_cache_stats()
        required_keys = {"avg_hit_rate", "total_calls", "total_cached", "total_prompt"}
        assert required_keys.issubset(stats.keys())
        # overall_hit_rate 在有数据时存在
        assert "overall_hit_rate" in stats


class TestCacheMonitorIntegration:
    """缓存监控集成测试：模拟连续多次 DeepSeek 调用"""

    def setup_method(self):
        """每个测试方法前清空 ledger 表"""
        _clear_ledger()

    def test_simulate_10_consecutive_deepseek_calls_high_hit_rate(self):
        """测试：模拟连续 10 次 DeepSeek 调用，缓存命中率应 ≥95%

        三段式 Prompt 固化前缀后，后续调用前缀部分全部命中缓存。
        """
        prefix_tokens = 2000  # 固定前缀 token 数
        dynamic_tokens = 100  # 动态尾部 token 数
        for i in range(10):
            lid = _insert_ledger_row(
                prompt_tokens=prefix_tokens + dynamic_tokens,
                cached_prompt_tokens=prefix_tokens,
            )
            record_cache_hit(
                "deepseek-chat-v3",
                prompt_tokens=prefix_tokens + dynamic_tokens,
                cached_tokens=prefix_tokens,
                ledger_id=lid,
            )
        stats = get_cache_stats()
        assert stats["total_calls"] == 10
        # 每次命中率 = 2000 / 2100 ≈ 0.952
        assert stats["avg_hit_rate"] >= 0.95
        assert stats["overall_hit_rate"] >= 0.95

    def test_simulate_mixed_models_only_deepseek_counted(self):
        """测试：混合模型调用，仅 cache_hit_rate>0 的记录参与统计

        record_cache_hit 不区分模型，但非 DeepSeek 模型通常 cached_tokens=0，
        若未调用 record_cache_hit 则 cache_hit_rate=0，被 get_cache_stats 过滤。
        """
        # DeepSeek 调用：有缓存命中
        id1 = _insert_ledger_row(prompt_tokens=1000, cached_prompt_tokens=900)
        record_cache_hit("deepseek-chat-v3", 1000, 900, ledger_id=id1)
        # GPT 调用：无缓存（未调用 record_cache_hit，cache_hit_rate=0）
        _insert_ledger_row(
            prompt_tokens=800, cached_prompt_tokens=0, model="gpt-4.1"
        )
        stats = get_cache_stats()
        assert stats["total_calls"] == 1
        assert stats["total_cached"] == 900

    def test_prefix_consistency_across_calls(self):
        """测试：同一会话内前缀 token 数一致，缓存命中率稳定"""
        prefix = 1500
        dynamic_values = [50, 80, 100, 120, 60]
        for dyn in dynamic_values:
            lid = _insert_ledger_row(
                prompt_tokens=prefix + dyn,
                cached_prompt_tokens=prefix,
            )
            record_cache_hit(
                "deepseek-r2",
                prompt_tokens=prefix + dyn,
                cached_tokens=prefix,
                ledger_id=lid,
            )
        stats = get_cache_stats()
        assert stats["total_calls"] == 5
        # 每次命中率 = prefix / (prefix + dyn)，前缀一致
        for dyn in dynamic_values:
            expected = prefix / (prefix + dyn)
            assert expected >= 0.9  # 均高于 90%
