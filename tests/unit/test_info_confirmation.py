"""信息确权门禁单元测试

测试 backend/constraints/info_confirmation.py。
覆盖以下功能：
  - InfoConfirmationResult 数据类
  - search_recent_papers: 检索近2年文献（异步）
  - format_paper_summary: 格式化文献摘要
  - validate_confirmation: 验证用户确认响应

测试策略：
  - 使用 unittest.mock 模拟 SearcherAgent
  - 覆盖正常流程与异常处理
  - 验证文献摘要格式化与确认验证逻辑
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.constraints.info_confirmation import (
    InfoConfirmationResult,
    search_recent_papers,
    format_paper_summary,
    validate_confirmation,
)


# ===== 辅助函数 =====

def _run_async(coro):
    """辅助函数：运行异步协程。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_agent_result(content="检索摘要", papers=None, citations=None):
    """构造模拟的 Agent 返回结果。"""
    result = MagicMock()
    result.content = content
    result.data = {"papers": papers or []}
    result.citations = citations or []
    return result


# ===== 测试类：InfoConfirmationResult 数据类 =====

class TestInfoConfirmationResult:
    """测试 InfoConfirmationResult 数据类。"""

    def test_construction(self):
        """应能正常构造。"""
        result = InfoConfirmationResult(
            confirmed=True,
            papers=[{"title": "论文"}],
            summary="摘要",
            message="已确认",
        )
        assert result.confirmed is True
        assert len(result.papers) == 1
        assert result.summary == "摘要"
        assert result.message == "已确认"

    def test_with_empty_papers(self):
        """空论文列表应能正常构造。"""
        result = InfoConfirmationResult(
            confirmed=False,
            papers=[],
            summary="",
            message="未确认",
        )
        assert result.papers == []
        assert result.confirmed is False


# ===== 测试类：search_recent_papers =====

class TestSearchRecentPapers:
    """测试 search_recent_papers 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=_make_mock_agent_result())
        with patch("backend.agents.agent_registry.get_agent", return_value=mock_agent):
            result = _run_async(search_recent_papers("深度学习"))
        assert isinstance(result, dict)
        assert "papers" in result
        assert "summary" in result
        assert "citations" in result

    def test_papers_from_agent(self):
        """papers 应来自 Agent 返回。"""
        papers = [{"title": "论文1"}, {"title": "论文2"}]
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(
            return_value=_make_mock_agent_result(papers=papers)
        )
        with patch("backend.agents.agent_registry.get_agent", return_value=mock_agent):
            result = _run_async(search_recent_papers("深度学习"))
        assert len(result["papers"]) == 2

    def test_summary_from_agent(self):
        """summary 应来自 Agent 返回。"""
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(
            return_value=_make_mock_agent_result(content="这是检索摘要")
        )
        with patch("backend.agents.agent_registry.get_agent", return_value=mock_agent):
            result = _run_async(search_recent_papers("深度学习"))
        assert result["summary"] == "这是检索摘要"

    def test_citations_from_agent(self):
        """citations 应来自 Agent 返回。"""
        citations = [{"url": "http://x.com"}]
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(
            return_value=_make_mock_agent_result(citations=citations)
        )
        with patch("backend.agents.agent_registry.get_agent", return_value=mock_agent):
            result = _run_async(search_recent_papers("深度学习"))
        assert len(result["citations"]) == 1

    def test_exception_returns_empty_result(self):
        """异常时应返回空结果。"""
        with patch("backend.agents.agent_registry.get_agent", side_effect=Exception("错误")):
            result = _run_async(search_recent_papers("深度学习"))
        assert result["papers"] == []
        assert "检索失败" in result["summary"]
        assert result["citations"] == []

    def test_with_years_param(self):
        """years 参数应能正常传递。"""
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=_make_mock_agent_result())
        with patch("backend.agents.agent_registry.get_agent", return_value=mock_agent):
            _run_async(search_recent_papers("深度学习", years=3))
        # 验证 Agent 被调用
        mock_agent.run.assert_called_once()

    def test_empty_query(self):
        """空查询应仍能执行。"""
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=_make_mock_agent_result())
        with patch("backend.agents.agent_registry.get_agent", return_value=mock_agent):
            result = _run_async(search_recent_papers(""))
        assert isinstance(result, dict)


# ===== 测试类：format_paper_summary =====

class TestFormatPaperSummary:
    """测试 format_paper_summary 函数。"""

    def test_empty_papers(self):
        """空论文列表应返回提示文本。"""
        result = format_paper_summary([])
        assert "未检索到" in result

    def test_single_paper(self):
        """单篇论文应包含标题与作者。"""
        papers = [{"title": "深度学习研究", "authors": "张三", "year": "2026", "abstract": "摘要内容"}]
        result = format_paper_summary(papers)
        assert "深度学习研究" in result
        assert "张三" in result
        assert "2026" in result

    def test_multiple_papers(self):
        """多篇论文应全部展示（最多10篇）。"""
        papers = [
            {"title": f"论文{i}", "authors": f"作者{i}", "year": "2026", "abstract": "摘要"}
            for i in range(5)
        ]
        result = format_paper_summary(papers)
        for i in range(5):
            assert f"论文{i}" in result

    def test_more_than_ten_papers(self):
        """超过10篇论文应显示省略提示。"""
        papers = [
            {"title": f"论文{i}", "authors": "作者", "year": "2026", "abstract": "摘要"}
            for i in range(15)
        ]
        result = format_paper_summary(papers)
        assert "还有" in result
        assert "5" in result  # 15-10=5

    def test_paper_without_title(self):
        """无标题的论文应显示"无标题"。"""
        papers = [{"authors": "张三", "year": "2026", "abstract": "摘要"}]
        result = format_paper_summary(papers)
        assert "无标题" in result

    def test_paper_without_authors(self):
        """无作者的论文应显示"未知作者"。"""
        papers = [{"title": "论文", "year": "2026", "abstract": "摘要"}]
        result = format_paper_summary(papers)
        assert "未知作者" in result

    def test_includes_confirmation_prompt(self):
        """应包含确认提示语。"""
        papers = [{"title": "论文", "authors": "作者", "year": "2026", "abstract": "摘要"}]
        result = format_paper_summary(papers)
        assert "确认" in result

    def test_abstract_truncated(self):
        """摘要应被截断（最多100字）。"""
        long_abstract = "x" * 200
        papers = [{"title": "论文", "authors": "作者", "year": "2026", "abstract": long_abstract}]
        result = format_paper_summary(papers)
        # 摘要应被截断
        assert "..." in result

    def test_shows_paper_count(self):
        """应显示论文总数。"""
        papers = [
            {"title": f"论文{i}", "authors": "作者", "year": "2026", "abstract": "摘要"}
            for i in range(3)
        ]
        result = format_paper_summary(papers)
        assert "3" in result


# ===== 测试类：validate_confirmation =====

class TestValidateConfirmation:
    """测试 validate_confirmation 函数。"""

    def test_empty_response(self):
        """空响应应返回 False。"""
        assert validate_confirmation("") is False

    def test_none_response(self):
        """None 应返回 False。"""
        assert validate_confirmation(None) is False

    def test_confirm_keyword(self):
        """含"确认"应返回 True。"""
        assert validate_confirmation("确认") is True

    def test_correct_keyword(self):
        """含"正确"应返回 True。"""
        assert validate_confirmation("信息正确") is True

    def test_yes_keyword(self):
        """含"yes"应返回 True。"""
        assert validate_confirmation("yes") is True

    def test_ok_keyword(self):
        """含"ok"应返回 True。"""
        assert validate_confirmation("ok") is True

    def test_continue_keyword(self):
        """含"继续"应返回 True。"""
        assert validate_confirmation("继续") is True

    def test_no_problem_keyword(self):
        """含"没问题"应返回 True。"""
        assert validate_confirmation("没问题") is True

    def test_accurate_keyword(self):
        """含"准确"应返回 True。"""
        assert validate_confirmation("准确") is True

    def test_negative_response(self):
        """否定响应应返回 False。"""
        assert validate_confirmation("不对") is False

    def test_irrelevant_response(self):
        """无关响应应返回 False。"""
        assert validate_confirmation("今天天气不错") is False

    def test_case_insensitive(self):
        """应不区分大小写。"""
        assert validate_confirmation("YES") is True
        assert validate_confirmation("OK") is True

    def test_mixed_text(self):
        """混合文本含确认词应返回 True。"""
        assert validate_confirmation("信息确认无误，继续下一步") is True


# ===== 集成测试 =====

class TestInfoConfirmationIntegration:
    """信息确权集成测试。"""

    def test_full_confirmation_flow(self):
        """测试完整确权流程：检索→格式化→验证。"""
        # 1. 模拟检索
        papers = [
            {"title": "深度学习教育应用", "authors": "张三", "year": "2026", "abstract": "探讨AI在教育中的应用"},
        ]
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(
            return_value=_make_mock_agent_result(content="检索完成", papers=papers)
        )
        with patch("backend.agents.agent_registry.get_agent", return_value=mock_agent):
            search_result = _run_async(search_recent_papers("深度学习"))
        # 2. 格式化摘要
        summary = format_paper_summary(search_result["papers"])
        assert "深度学习教育应用" in summary
        # 3. 验证用户确认
        assert validate_confirmation("确认") is True
        assert validate_confirmation("不对") is False
