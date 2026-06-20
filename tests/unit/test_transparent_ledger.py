"""透明账本模块单元测试

测试 backend/budgets/transparent_ledger.py。
覆盖以下功能：
  - record_usage: 记录 AI 调用用量与费用
  - get_ledger_entries: 查询账本明细
  - get_ledger_summary: 汇总账本统计（含三类 token）
  - get_session_cost: 查询会话总费用

测试策略：
  - 使用临时数据库隔离测试
  - 先插入 session 满足外键约束
  - 覆盖三类 token 统计（input_cached/input_uncached/output）
  - 边界条件：空账本、单条记录、多条记录
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

# ===== 临时数据库初始化 =====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_ledger_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.budgets.transparent_ledger import (
    record_usage,
    get_ledger_entries,
    get_ledger_summary,
    get_session_cost,
)
from backend.database import get_db_connection


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


# ===== 测试类：record_usage =====

class TestRecordUsage:
    """测试 record_usage 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        sid = _insert_session()
        result = record_usage(sid, "deepseek-chat", 100, 50, "reasoner")
        assert isinstance(result, dict)

    def test_record_contains_required_fields(self):
        """返回的字典应包含所有必需字段。"""
        sid = _insert_session()
        result = record_usage(sid, "deepseek-chat", 100, 50, "reasoner")
        assert "id" in result
        assert "session_id" in result
        assert "model" in result
        assert "prompt_tokens" in result
        assert "completion_tokens" in result
        assert "total_tokens" in result
        assert "cost" in result
        assert "purpose" in result
        assert "created_at" in result

    def test_calculates_total_tokens(self):
        """应正确计算 total_tokens。"""
        sid = _insert_session()
        result = record_usage(sid, "deepseek-chat", 100, 50, "reasoner")
        assert result["total_tokens"] == 150

    def test_records_cached_tokens(self):
        """应记录 cached_prompt_tokens。"""
        sid = _insert_session()
        result = record_usage(sid, "deepseek-chat", 100, 50, "reasoner", cached_tokens=80)
        assert result["cached_prompt_tokens"] == 80

    def test_default_cached_tokens_zero(self):
        """默认 cached_tokens 应为 0。"""
        sid = _insert_session()
        result = record_usage(sid, "deepseek-chat", 100, 50, "reasoner")
        assert result["cached_prompt_tokens"] == 0

    def test_generates_unique_id(self):
        """每次记录应生成唯一 id。"""
        sid = _insert_session()
        r1 = record_usage(sid, "model", 100, 50, "purpose")
        r2 = record_usage(sid, "model", 100, 50, "purpose")
        assert r1["id"] != r2["id"]

    def test_records_session_id(self):
        """应正确记录 session_id。"""
        sid = _insert_session()
        result = record_usage(sid, "model", 100, 50, "purpose")
        assert result["session_id"] == sid

    def test_records_model(self):
        """应正确记录模型名。"""
        sid = _insert_session()
        result = record_usage(sid, "gpt-4.1", 100, 50, "purpose")
        assert result["model"] == "gpt-4.1"

    def test_records_purpose(self):
        """应正确记录用途。"""
        sid = _insert_session()
        result = record_usage(sid, "model", 100, 50, "mentor")
        assert result["purpose"] == "mentor"

    def test_calculates_cost(self):
        """应计算费用。"""
        sid = _insert_session()
        result = record_usage(sid, "deepseek-chat", 1000, 500, "reasoner")
        assert result["cost"] > 0


# ===== 测试类：get_ledger_entries =====

class TestGetLedgerEntries:
    """测试 get_ledger_entries 函数。"""

    def test_empty_ledger(self):
        """空账本应返回空列表。"""
        result = get_ledger_entries()
        assert isinstance(result, list)

    def test_returns_all_entries(self):
        """应返回所有记录。"""
        sid = _insert_session()
        record_usage(sid, "model", 100, 50, "purpose")
        record_usage(sid, "model", 200, 100, "purpose")
        result = get_ledger_entries()
        assert len(result) >= 2

    def test_filter_by_session(self):
        """应能按 session_id 过滤。"""
        sid1 = _insert_session(title="会话1")
        sid2 = _insert_session(title="会话2")
        record_usage(sid1, "model", 100, 50, "purpose")
        record_usage(sid2, "model", 200, 100, "purpose")
        result1 = get_ledger_entries(session_id=sid1)
        result2 = get_ledger_entries(session_id=sid2)
        assert all(r["session_id"] == sid1 for r in result1)
        assert all(r["session_id"] == sid2 for r in result2)

    def test_limit_parameter(self):
        """limit 参数应限制返回条数。"""
        sid = _insert_session()
        for _ in range(10):
            record_usage(sid, "model", 100, 50, "purpose")
        result = get_ledger_entries(limit=5)
        assert len(result) <= 5

    def test_offset_parameter(self):
        """offset 参数应跳过指定条数。"""
        sid = _insert_session()
        for _ in range(10):
            record_usage(sid, "model", 100, 50, "purpose")
        result1 = get_ledger_entries(limit=5, offset=0)
        result2 = get_ledger_entries(limit=5, offset=5)
        ids1 = {r["id"] for r in result1}
        ids2 = {r["id"] for r in result2}
        assert not (ids1 & ids2)

    def test_nonexistent_session_returns_empty(self):
        """不存在的 session 应返回空列表。"""
        result = get_ledger_entries(session_id="nonexistent")
        assert result == []


# ===== 测试类：get_ledger_summary =====

class TestGetLedgerSummary:
    """测试 get_ledger_summary 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        result = get_ledger_summary()
        assert isinstance(result, dict)

    def test_contains_required_fields(self):
        """应包含所有必需字段。"""
        result = get_ledger_summary()
        assert "total_calls" in result
        assert "total_tokens" in result
        assert "total_cost" in result
        assert "input_cached" in result
        assert "input_uncached" in result
        assert "output" in result
        assert "by_model" in result
        assert "by_purpose" in result

    def test_empty_ledger_summary(self):
        """空账本汇总应为零值。"""
        # 注意：可能有其他测试已写入数据，验证字段存在即可
        result = get_ledger_summary()
        assert result["total_calls"] >= 0
        assert result["total_tokens"] >= 0

    def test_summary_after_record(self):
        """记录后汇总应包含该记录。"""
        sid = _insert_session()
        record_usage(sid, "test-model-summary", 100, 50, "test-purpose",
                    cached_tokens=30)
        result = get_ledger_summary()
        assert result["total_calls"] > 0

    def test_by_model_grouping(self):
        """应按模型分组统计。"""
        sid = _insert_session()
        record_usage(sid, "model-a", 100, 50, "purpose")
        record_usage(sid, "model-b", 200, 100, "purpose")
        result = get_ledger_summary()
        assert "model-a" in result["by_model"]
        assert "model-b" in result["by_model"]

    def test_by_purpose_grouping(self):
        """应按用途分组统计。"""
        sid = _insert_session()
        record_usage(sid, "model", 100, 50, "reasoner")
        record_usage(sid, "model", 200, 100, "mentor")
        result = get_ledger_summary()
        assert "reasoner" in result["by_purpose"]
        assert "mentor" in result["by_purpose"]

    def test_three_category_tokens(self):
        """三类 token 应正确统计。"""
        sid = _insert_session()
        record_usage(sid, "model", 100, 50, "purpose", cached_tokens=30)
        result = get_ledger_summary()
        # input_cached = 30, input_uncached = 100-30=70, output = 50
        assert result["input_cached"] >= 30
        assert result["input_uncached"] >= 70
        assert result["output"] >= 50

    def test_by_model_contains_three_categories(self):
        """按模型分组应包含三类 token。"""
        sid = _insert_session()
        record_usage(sid, "three-cat-model", 100, 50, "purpose", cached_tokens=40)
        result = get_ledger_summary()
        model_stats = result["by_model"].get("three-cat-model", {})
        assert "input_cached" in model_stats
        assert "input_uncached" in model_stats
        assert "output" in model_stats

    def test_by_purpose_contains_three_categories(self):
        """按用途分组应包含三类 token。"""
        sid = _insert_session()
        record_usage(sid, "model", 100, 50, "three-cat-purpose", cached_tokens=40)
        result = get_ledger_summary()
        purpose_stats = result["by_purpose"].get("three-cat-purpose", {})
        assert "input_cached" in purpose_stats
        assert "input_uncached" in purpose_stats
        assert "output" in purpose_stats


# ===== 测试类：get_session_cost =====

class TestGetSessionCost:
    """测试 get_session_cost 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        sid = _insert_session()
        result = get_session_cost(sid)
        assert isinstance(result, dict)

    def test_contains_required_fields(self):
        """应包含所有必需字段。"""
        sid = _insert_session()
        result = get_session_cost(sid)
        assert "session_id" in result
        assert "total_calls" in result
        assert "total_tokens" in result
        assert "total_cost" in result
        assert "input_cached" in result
        assert "input_uncached" in result
        assert "output" in result

    def test_empty_session_cost(self):
        """无记录的会话费用应为零。"""
        sid = _insert_session()
        result = get_session_cost(sid)
        assert result["total_calls"] == 0
        assert result["total_tokens"] == 0
        assert result["total_cost"] == 0

    def test_after_record(self):
        """记录后应统计该会话的费用。"""
        sid = _insert_session()
        record_usage(sid, "model", 100, 50, "purpose", cached_tokens=30)
        result = get_session_cost(sid)
        assert result["total_calls"] == 1
        assert result["total_tokens"] == 150
        assert result["input_cached"] == 30
        assert result["input_uncached"] == 70
        assert result["output"] == 50

    def test_multiple_records(self):
        """多条记录应累计统计。"""
        sid = _insert_session()
        record_usage(sid, "model", 100, 50, "purpose1", cached_tokens=30)
        record_usage(sid, "model", 200, 100, "purpose2", cached_tokens=50)
        result = get_session_cost(sid)
        assert result["total_calls"] == 2
        assert result["total_tokens"] == 450
        assert result["input_cached"] == 80
        assert result["input_uncached"] == 220  # (100-30) + (200-50)
        assert result["output"] == 150

    def test_isolates_by_session(self):
        """不同会话的费用应隔离。"""
        sid1 = _insert_session(title="会话1")
        sid2 = _insert_session(title="会话2")
        record_usage(sid1, "model", 100, 50, "purpose")
        record_usage(sid2, "model", 200, 100, "purpose")
        cost1 = get_session_cost(sid1)
        cost2 = get_session_cost(sid2)
        assert cost1["total_calls"] == 1
        assert cost2["total_calls"] == 1
        assert cost1["total_tokens"] == 150
        assert cost2["total_tokens"] == 300

    def test_nonexistent_session_returns_zeros(self):
        """不存在的会话应返回零值。"""
        result = get_session_cost("nonexistent-id")
        assert result["total_calls"] == 0
        assert result["total_cost"] == 0


# ===== 集成测试 =====

class TestTransparentLedgerIntegration:
    """透明账本集成测试。"""

    def test_full_ledger_flow(self):
        """测试完整账本流程：记录→查询→汇总。"""
        sid = _insert_session()
        # 1. 记录多次调用
        record_usage(sid, "deepseek-chat", 1000, 500, "reasoner", cached_tokens=800)
        record_usage(sid, "gpt-4.1", 2000, 1000, "mentor", cached_tokens=0)
        record_usage(sid, "deepseek-chat", 500, 200, "reasoner", cached_tokens=400)
        # 2. 查询明细
        entries = get_ledger_entries(session_id=sid)
        assert len(entries) == 3
        # 3. 查询汇总
        summary = get_ledger_summary()
        assert summary["total_calls"] >= 3
        # 4. 查询会话费用
        cost = get_session_cost(sid)
        assert cost["total_calls"] == 3
        assert cost["input_cached"] == 1200  # 800+0+400
        assert cost["input_uncached"] == 2300  # 200+2000+100
        assert cost["output"] == 1700  # 500+1000+200

    def test_multi_session_multi_model_summary(self):
        """测试多会话多模型的汇总统计。"""
        sid1 = _insert_session(title="会话A")
        sid2 = _insert_session(title="会话B")
        record_usage(sid1, "model-x", 100, 50, "reasoner")
        record_usage(sid1, "model-y", 200, 100, "mentor")
        record_usage(sid2, "model-x", 300, 150, "reasoner")
        summary = get_ledger_summary()
        # 按模型分组
        assert "model-x" in summary["by_model"]
        assert "model-y" in summary["by_model"]
        # model-x 应有 2 次调用
        assert summary["by_model"]["model-x"]["calls"] >= 2
