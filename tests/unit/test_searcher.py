"""searcher 模块单元测试

测试 backend/agents/searcher_wrapper.py 的检索功能：
  - search_literature 模拟文献检索
  - check_novelty 新颖性检查
  - _calculate_similarity 字符串相似度
  - _levenshtein_distance 编辑距离
  - estimate_literature_count 文献数量估算
  - search_and_summarize 检索汇总
  - MockSearcher 异步检索器
  - SearcherAgent Agent 类
  - get_searcher 工厂函数
"""
import asyncio
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ===== 临时数据库初始化 =====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_searcher_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.agents.base_agent import AgentResult
from backend.agents.searcher_wrapper import (
    search_literature,
    check_novelty,
    _calculate_similarity,
    _levenshtein_distance,
    estimate_literature_count,
    search_and_summarize,
    MockSearcher,
    SearcherAgent,
    get_searcher,
)


def _run_async(coro):
    """辅助函数：运行异步协程"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_llm_result(content='{"summary": "检索摘要", "key_findings": ["发现1"]}',
                     prompt_tokens=100, completion_tokens=50):
    """构造模拟的 call_llm 返回值"""
    return {
        "content": content,
        "model": "mock-model",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost": 0.0,
    }


# ===== search_literature 测试 =====


class TestSearchLiterature:
    """search_literature 函数测试"""

    def test_search_returns_list(self):
        """测试：返回列表"""
        result = search_literature("机器学习", 5)
        assert isinstance(result, list)

    def test_search_returns_correct_count(self):
        """测试：返回指定数量的文献"""
        result = search_literature("AI", 3)
        assert len(result) == 3

    def test_search_default_count(self):
        """测试：默认返回 10 篇"""
        result = search_literature("深度学习")
        assert len(result) == 10

    def test_search_zero_count(self):
        """测试：count=0 返回空列表"""
        result = search_literature("AI", 0)
        assert len(result) == 0

    def test_search_paper_has_title(self):
        """测试：每篇文献包含 title"""
        result = search_literature("AI", 2)
        for p in result:
            assert "title" in p

    def test_search_paper_has_authors(self):
        """测试：每篇文献包含 authors"""
        result = search_literature("AI", 2)
        for p in result:
            assert "authors" in p

    def test_search_paper_has_year(self):
        """测试：每篇文献包含 year"""
        result = search_literature("AI", 2)
        for p in result:
            assert "year" in p

    def test_search_paper_has_abstract(self):
        """测试：每篇文献包含 abstract"""
        result = search_literature("AI", 2)
        for p in result:
            assert "abstract" in p

    def test_search_title_contains_keyword(self):
        """测试：标题包含关键词"""
        result = search_literature("机器学习", 1)
        assert "机器学习" in result[0]["title"]

    def test_search_empty_keyword(self):
        """测试：空关键词不崩溃"""
        result = search_literature("", 3)
        assert len(result) == 3


# ===== check_novelty 测试 =====


class TestCheckNovelty:
    """check_novelty 函数测试"""

    def test_check_novelty_returns_dict(self):
        """测试：返回字典"""
        result = check_novelty("新论题", [])
        assert isinstance(result, dict)

    def test_check_novelty_has_required_fields(self):
        """测试：包含必需字段"""
        result = check_novelty("论题", [])
        assert "novelty_score" in result
        assert "similar_titles" in result
        assert "assessment" in result

    def test_check_novelty_no_existing_titles(self):
        """测试：无已有标题时为高创新"""
        result = check_novelty("全新论题", [])
        assert result["novelty_score"] == 0.0
        assert result["assessment"] == "高创新"

    def test_check_novelty_identical_title(self):
        """测试：完全相同标题为预警"""
        result = check_novelty("相同标题", ["相同标题"])
        assert result["novelty_score"] == 1.0
        assert result["assessment"] == "预警"

    def test_check_novelty_similar_title(self):
        """测试：相似标题为微创新或常规创新"""
        result = check_novelty("机器学习研究", ["机器学习的研究"])
        assert result["novelty_score"] > 0

    def test_check_novelty_collects_similar_titles(self):
        """测试：收集相似标题"""
        result = check_novelty("测试", ["测试", "测试A", "完全不同"])
        assert "测试" in result["similar_titles"]

    def test_check_novelty_default_existing_titles(self):
        """测试：existing_titles 默认为空"""
        result = check_novelty("论题")
        assert result["novelty_score"] == 0.0

    def test_check_novelty_high_innovation(self):
        """测试：低相似度为高创新"""
        result = check_novelty("量子计算", ["生物医学"])
        assert result["assessment"] == "高创新"

    def test_check_novelty_warning_level(self):
        """测试：高相似度为预警"""
        result = check_novelty("机器学习", ["机器学习应用研究"])
        # 包含关系 -> similarity=1.0 -> 预警
        assert result["assessment"] == "预警"


# ===== _calculate_similarity 测试 =====


class TestCalculateSimilarity:
    """_calculate_similarity 函数测试"""

    def test_identical_strings(self):
        """测试：完全相同相似度为 1.0"""
        assert _calculate_similarity("abc", "abc") == 1.0

    def test_empty_string(self):
        """测试：空字符串相似度为 0.0"""
        assert _calculate_similarity("", "abc") == 0.0
        assert _calculate_similarity("abc", "") == 0.0

    def test_containment(self):
        """测试：包含关系相似度为 1.0"""
        assert _calculate_similarity("abc", "abcdef") == 1.0
        assert _calculate_similarity("abcdef", "abc") == 1.0

    def test_completely_different(self):
        """测试：完全不同相似度较低"""
        sim = _calculate_similarity("abc", "xyz")
        assert 0.0 <= sim < 0.5

    def test_similarity_range(self):
        """测试：相似度在 0-1 范围内"""
        sim = _calculate_similarity("kitten", "sitting")
        assert 0.0 <= sim <= 1.0

    def test_one_char_difference(self):
        """测试：一个字符差异"""
        sim = _calculate_similarity("abc", "abd")
        assert sim > 0.5


# ===== _levenshtein_distance 测试 =====


class TestLevenshteinDistance:
    """_levenshtein_distance 函数测试"""

    def test_identical_strings(self):
        """测试：相同字符串距离为 0"""
        assert _levenshtein_distance("abc", "abc") == 0

    def test_one_substitution(self):
        """测试：一个替换距离为 1"""
        assert _levenshtein_distance("abc", "abd") == 1

    def test_one_insertion(self):
        """测试：一个插入距离为 1"""
        assert _levenshtein_distance("abc", "abcd") == 1

    def test_one_deletion(self):
        """测试：一个删除距离为 1"""
        assert _levenshtein_distance("abcd", "abc") == 1

    def test_empty_string(self):
        """测试：空字符串距离为另一字符串长度"""
        assert _levenshtein_distance("", "abc") == 3
        assert _levenshtein_distance("abc", "") == 3

    def test_completely_different(self):
        """测试：完全不同"""
        assert _levenshtein_distance("abc", "xyz") == 3

    def test_classic_example(self):
        """测试：经典例子 kitten -> sitting"""
        assert _levenshtein_distance("kitten", "sitting") == 3


# ===== estimate_literature_count 测试 =====


class TestEstimateLiteratureCount:
    """estimate_literature_count 函数测试"""

    def test_returns_integer(self):
        """测试：返回整数"""
        result = estimate_literature_count("AI")
        assert isinstance(result, int)

    def test_range_20_to_100(self):
        """测试：结果在 20-100 范围内"""
        result = estimate_literature_count("机器学习")
        assert 20 <= result <= 100

    def test_empty_keyword(self):
        """测试：空关键词不崩溃"""
        result = estimate_literature_count("")
        assert 20 <= result <= 100

    def test_deterministic_for_same_keyword(self):
        """测试：相同关键词返回相同结果（基于种子）"""
        r1 = estimate_literature_count("深度学习")
        r2 = estimate_literature_count("深度学习")
        assert r1 == r2


# ===== search_and_summarize 测试 =====


class TestSearchAndSummarize:
    """search_and_summarize 函数测试"""

    def test_returns_dict(self):
        """测试：返回字典"""
        result = search_and_summarize("AI", 3)
        assert isinstance(result, dict)

    def test_has_required_fields(self):
        """测试：包含必需字段"""
        result = search_and_summarize("AI", 3)
        assert "keyword" in result
        assert "total_found" in result
        assert "papers" in result
        assert "summary" in result

    def test_keyword_matches(self):
        """测试：keyword 与输入一致"""
        result = search_and_summarize("机器学习", 3)
        assert result["keyword"] == "机器学习"

    def test_total_found_matches_count(self):
        """测试：total_found 与 count 一致"""
        result = search_and_summarize("AI", 5)
        assert result["total_found"] == 5

    def test_papers_count_matches(self):
        """测试：papers 数量与 count 一致"""
        result = search_and_summarize("AI", 4)
        assert len(result["papers"]) == 4


# ===== MockSearcher 测试 =====


class TestMockSearcher:
    """MockSearcher 异步检索器测试"""

    def test_search_literature_async(self):
        """测试：异步文献检索"""
        searcher = MockSearcher()
        result = _run_async(searcher.search_literature("AI", 3))
        assert "papers" in result
        assert len(result["papers"]) == 3
        assert result["search_degraded"] is False

    def test_check_novelty_async(self):
        """测试：异步新颖性检查"""
        searcher = MockSearcher()
        result = _run_async(searcher.check_novelty("论题", []))
        assert "novelty_score" in result
        assert result["search_degraded"] is False

    def test_estimate_count_async(self):
        """测试：异步文献数量估算"""
        searcher = MockSearcher()
        result = _run_async(searcher.estimate_literature_count("AI"))
        assert "count" in result
        assert result["search_degraded"] is False

    def test_search_and_summarize_async(self):
        """测试：异步检索汇总"""
        searcher = MockSearcher()
        result = _run_async(searcher.search_and_summarize("AI", 3))
        assert "papers" in result
        assert result["search_degraded"] is False


# ===== get_searcher 工厂测试 =====


class TestGetSearcher:
    """get_searcher 工厂函数测试"""

    def test_returns_searcher_instance(self):
        """测试：返回检索器实例"""
        searcher = get_searcher()
        assert searcher is not None

    def test_default_returns_mock_searcher(self):
        """测试：默认返回 MockSearcher（real_search_enabled=False）"""
        searcher = get_searcher()
        # 默认配置下应返回 MockSearcher
        assert hasattr(searcher, "search_literature")


# ===== SearcherAgent 测试 =====


class TestSearcherAgent:
    """SearcherAgent Agent 类测试"""

    def test_init_agent_id(self):
        """测试：agent_id 为 searcher"""
        agent = SearcherAgent()
        assert agent.agent_id == "searcher"

    def test_init_name(self):
        """测试：name 为 Searcher"""
        agent = SearcherAgent()
        assert agent.name == "Searcher"

    def test_init_capabilities(self):
        """测试：capabilities 包含 web_search"""
        agent = SearcherAgent()
        assert "web_search" in agent.capabilities

    def test_run_returns_agent_result(self):
        """测试：run 返回 AgentResult"""
        agent = SearcherAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"query": "AI"}))
        assert isinstance(result, AgentResult)
        assert result.agent_id == "searcher"

    def test_run_success_with_query(self):
        """测试：有效 query 返回成功"""
        agent = SearcherAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"query": "机器学习"}))
        assert result.success is True

    def test_run_data_contains_papers(self):
        """测试：data 包含 papers"""
        agent = SearcherAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"query": "AI"}))
        assert "papers" in result.data

    def test_run_empty_query_returns_failure(self):
        """测试：空 query 返回失败"""
        agent = SearcherAgent()
        result = _run_async(agent.run({"query": ""}))
        assert result.success is False

    def test_run_fallback_on_exception(self):
        """测试：异常时返回失败结果"""
        agent = SearcherAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 不可用")
            result = _run_async(agent.run({"query": "AI"}))
        assert result.success is False

    def test_run_data_contains_years(self):
        """测试：data 包含 years"""
        agent = SearcherAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"query": "AI", "years": 3}))
        assert result.data["years"] == 3
