"""深度辅助三件套单元测试

测试 backend/constraints/deep_assist.py。
覆盖以下功能：
  - DeepAssistResult 数据类
  - literature_reading: 文献精读（异步）
  - experiment_preparation: 实验预研（异步）
  - defense_simulation: 答辩模拟（异步）

测试策略：
  - 使用 unittest.mock 模拟 call_llm 调用
  - 覆盖正常流程与异常处理
  - 验证返回的 DeepAssistResult 结构
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.constraints.deep_assist import (
    DeepAssistResult,
    literature_reading,
    experiment_preparation,
    defense_simulation,
)


# ===== 辅助函数 =====

def _run_async(coro):
    """辅助函数：运行异步协程。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_llm_result(content="模拟回复内容", prompt_tokens=100, completion_tokens=50):
    """构造模拟的 call_llm 返回值。"""
    return {
        "content": content,
        "model": "mock-model",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost": 0.0,
    }


# ===== 测试类：DeepAssistResult 数据类 =====

class TestDeepAssistResult:
    """测试 DeepAssistResult 数据类。"""

    def test_construction(self):
        """应能正常构造。"""
        result = DeepAssistResult(
            assist_type="literature_reading",
            content="精读内容",
            suggestions=["建议1"],
            follow_up=["后续1"],
        )
        assert result.assist_type == "literature_reading"
        assert result.content == "精读内容"
        assert len(result.suggestions) == 1
        assert len(result.follow_up) == 1

    def test_with_empty_collections(self):
        """空集合应能正常构造。"""
        result = DeepAssistResult(
            assist_type="test",
            content="",
            suggestions=[],
            follow_up=[],
        )
        assert result.suggestions == []
        assert result.follow_up == []


# ===== 测试类：literature_reading =====

class TestLiteratureReading:
    """测试 literature_reading 函数。"""

    def test_returns_deep_assist_result(self):
        """应返回 DeepAssistResult 实例。"""
        paper = {"title": "测试论文", "authors": "张三", "year": "2026", "abstract": "摘要"}
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("精读结果")
            result = _run_async(literature_reading(paper))
        assert isinstance(result, DeepAssistResult)
        assert result.assist_type == "literature_reading"

    def test_content_from_llm(self):
        """content 应来自 LLM 返回。"""
        paper = {"title": "论文", "abstract": "摘要"}
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("这是精读内容")
            result = _run_async(literature_reading(paper))
        assert result.content == "这是精读内容"

    def test_with_focus_param(self):
        """focus 参数应能正常传递。"""
        paper = {"title": "论文", "abstract": "摘要"}
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("关注方法的精读")
            result = _run_async(literature_reading(paper, focus="方法"))
        assert "关注方法" in result.content

    def test_suggestions_not_empty(self):
        """suggestions 应不为空。"""
        paper = {"title": "论文", "abstract": "摘要"}
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("内容")
            result = _run_async(literature_reading(paper))
        assert len(result.suggestions) > 0

    def test_follow_up_not_empty(self):
        """follow_up 应不为空。"""
        paper = {"title": "论文", "abstract": "摘要"}
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("内容")
            result = _run_async(literature_reading(paper))
        assert len(result.follow_up) > 0

    def test_empty_paper(self):
        """空论文信息应仍能执行（异常处理）。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("内容")
            result = _run_async(literature_reading({}))
        assert isinstance(result, DeepAssistResult)

    def test_llm_exception_returns_error_result(self):
        """LLM 异常时应返回含错误信息的 DeepAssistResult。"""
        paper = {"title": "论文", "abstract": "摘要"}
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("API 错误")
            result = _run_async(literature_reading(paper))
        assert "精读失败" in result.content
        assert result.suggestions == []
        assert result.follow_up == []


# ===== 测试类：experiment_preparation =====

class TestExperimentPreparation:
    """测试 experiment_preparation 函数。"""

    def test_returns_deep_assist_result(self):
        """应返回 DeepAssistResult 实例。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("实验方案")
            result = _run_async(experiment_preparation("深度学习论题"))
        assert isinstance(result, DeepAssistResult)
        assert result.assist_type == "experiment_preparation"

    def test_content_from_llm(self):
        """content 应来自 LLM 返回。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("这是实验方案")
            result = _run_async(experiment_preparation("论题"))
        assert result.content == "这是实验方案"

    def test_with_method_param(self):
        """method 参数应能正常传递。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("含方法的方案")
            result = _run_async(experiment_preparation("论题", method="实验法"))
        assert "含方法" in result.content

    def test_suggestions_not_empty(self):
        """suggestions 应不为空。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("内容")
            result = _run_async(experiment_preparation("论题"))
        assert len(result.suggestions) > 0

    def test_follow_up_not_empty(self):
        """follow_up 应不为空。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("内容")
            result = _run_async(experiment_preparation("论题"))
        assert len(result.follow_up) > 0

    def test_empty_topic(self):
        """空论题应仍能执行。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("内容")
            result = _run_async(experiment_preparation(""))
        assert isinstance(result, DeepAssistResult)

    def test_llm_exception_returns_error_result(self):
        """LLM 异常时应返回含错误信息的 DeepAssistResult。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("API 错误")
            result = _run_async(experiment_preparation("论题"))
        assert "预研失败" in result.content
        assert result.suggestions == []


# ===== 测试类：defense_simulation =====

class TestDefenseSimulation:
    """测试 defense_simulation 函数。"""

    def test_returns_deep_assist_result(self):
        """应返回 DeepAssistResult 实例。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("答辩问答")
            result = _run_async(defense_simulation("深度学习论题"))
        assert isinstance(result, DeepAssistResult)
        assert result.assist_type == "defense_simulation"

    def test_content_from_llm(self):
        """content 应来自 LLM 返回。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("这是答辩问答")
            result = _run_async(defense_simulation("论题"))
        assert result.content == "这是答辩问答"

    def test_with_report_content(self):
        """report_content 参数应能正常传递。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("含报告的答辩")
            result = _run_async(defense_simulation("论题", report_content="报告内容" * 100))
        assert "含报告" in result.content

    def test_suggestions_not_empty(self):
        """suggestions 应不为空。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("内容")
            result = _run_async(defense_simulation("论题"))
        assert len(result.suggestions) > 0

    def test_follow_up_not_empty(self):
        """follow_up 应不为空。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("内容")
            result = _run_async(defense_simulation("论题"))
        assert len(result.follow_up) > 0

    def test_empty_topic(self):
        """空论题应仍能执行。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("内容")
            result = _run_async(defense_simulation(""))
        assert isinstance(result, DeepAssistResult)

    def test_llm_exception_returns_error_result(self):
        """LLM 异常时应返回含错误信息的 DeepAssistResult。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("API 错误")
            result = _run_async(defense_simulation("论题"))
        assert "模拟失败" in result.content
        assert result.suggestions == []


# ===== 集成测试 =====

class TestDeepAssistIntegration:
    """深度辅助集成测试。"""

    def test_all_three_assist_types(self):
        """测试三种辅助类型。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("通用回复")
            # 文献精读
            r1 = _run_async(literature_reading({"title": "论文"}))
            assert r1.assist_type == "literature_reading"
            # 实验预研
            r2 = _run_async(experiment_preparation("论题"))
            assert r2.assist_type == "experiment_preparation"
            # 答辩模拟
            r3 = _run_async(defense_simulation("论题"))
            assert r3.assist_type == "defense_simulation"

    def test_error_handling_consistency(self):
        """三种辅助类型的异常处理应一致。"""
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("统一错误")
            r1 = _run_async(literature_reading({"title": "论文"}))
            r2 = _run_async(experiment_preparation("论题"))
            r3 = _run_async(defense_simulation("论题"))
            # 都应返回 DeepAssistResult 且 suggestions 为空
            assert isinstance(r1, DeepAssistResult)
            assert isinstance(r2, DeepAssistResult)
            assert isinstance(r3, DeepAssistResult)
            assert r1.suggestions == []
            assert r2.suggestions == []
            assert r3.suggestions == []
