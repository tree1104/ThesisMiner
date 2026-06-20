"""critic 模块单元测试

测试 backend/agents/critic.py 的 CriticAgent：
  - SCORE_THRESHOLD 阈值常量
  - 初始化与属性
  - run 方法候选评估
  - _parse_evaluations JSON 解析
  - _extract_json_evaluations 多模式提取
  - _fallback_evaluations 兜底评估
  - _safe_int 安全转换
  - _build_user_prompt 提示构建
  - 本地新颖性融合
"""
import asyncio
import json
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
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_critic_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.agents.base_agent import AgentResult
from backend.agents.critic import CriticAgent, SCORE_THRESHOLD


def _run_async(coro):
    """辅助函数：运行异步协程"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_llm_result(content='{"evaluations": [{"title": "测试论题", "score": 75, "novelty": 80, "feasibility": 70, "issues": [], "suggestions": []}]}',
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


# ===== 常量测试 =====


class TestScoreThreshold:
    """SCORE_THRESHOLD 常量测试"""

    def test_threshold_is_60(self):
        """测试：评分阈值为 60"""
        assert SCORE_THRESHOLD == 60

    def test_threshold_is_integer(self):
        """测试：阈值为整数"""
        assert isinstance(SCORE_THRESHOLD, int)


# ===== 初始化测试 =====


class TestCriticInit:
    """CriticAgent 初始化测试"""

    def test_init_agent_id(self):
        """测试：agent_id 为 critic"""
        agent = CriticAgent()
        assert agent.agent_id == "critic"

    def test_init_name(self):
        """测试：name 为 Critic"""
        agent = CriticAgent()
        assert agent.name == "Critic"

    def test_init_description(self):
        """测试：包含描述"""
        agent = CriticAgent()
        assert "评估" in agent.description or "Critic" in agent.description

    def test_init_temperature(self):
        """测试：temperature 较低（评估需稳定）"""
        agent = CriticAgent()
        assert agent.temperature == 0.2

    def test_init_has_system_prompt(self):
        """测试：有系统提示"""
        agent = CriticAgent()
        assert len(agent.system_prompt) > 0
        assert "评估" in agent.system_prompt or "score" in agent.system_prompt.lower()

    def test_init_capabilities(self):
        """测试：capabilities 包含 thinking"""
        agent = CriticAgent()
        assert "thinking" in agent.capabilities


# ===== run 方法测试 =====


class TestRun:
    """run 方法测试"""

    def test_run_returns_agent_result(self):
        """测试：run 返回 AgentResult"""
        agent = CriticAgent()
        candidates = [{"title": "论题1", "dimension": "cross_discipline", "rationale": "R"}]
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"candidates": candidates}))
        assert isinstance(result, AgentResult)
        assert result.agent_id == "critic"

    def test_run_success_with_valid_response(self):
        """测试：有效响应返回成功结果"""
        agent = CriticAgent()
        candidates = [{"title": "论题1", "dimension": "cross_discipline", "rationale": "R"}]
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"candidates": candidates}))
        assert result.success is True

    def test_run_data_contains_evaluations(self):
        """测试：data 包含 evaluations"""
        agent = CriticAgent()
        candidates = [{"title": "论题1", "dimension": "cross_discipline", "rationale": "R"}]
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"candidates": candidates}))
        assert "evaluations" in result.data
        assert len(result.data["evaluations"]) > 0

    def test_run_data_contains_avg_score(self):
        """测试：data 包含 avg_score"""
        agent = CriticAgent()
        candidates = [{"title": "论题1", "dimension": "cross_discipline", "rationale": "R"}]
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"candidates": candidates}))
        assert "avg_score" in result.data

    def test_run_data_contains_threshold(self):
        """测试：data 包含 threshold"""
        agent = CriticAgent()
        candidates = [{"title": "论题1", "dimension": "cross_discipline", "rationale": "R"}]
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"candidates": candidates}))
        assert result.data["threshold"] == SCORE_THRESHOLD

    def test_run_empty_candidates_returns_failure(self):
        """测试：空候选列表返回失败"""
        agent = CriticAgent()
        result = _run_async(agent.run({"candidates": []}))
        assert result.success is False
        assert "evaluations" in result.data

    def test_run_fallback_on_llm_exception(self):
        """测试：LLM 异常时返回兜底评估"""
        agent = CriticAgent()
        candidates = [{"title": "论题1", "dimension": "cross_discipline", "rationale": "R"}]
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 不可用")
            result = _run_async(agent.run({"candidates": candidates}))
        assert result.success is False
        assert len(result.data["evaluations"]) > 0

    def test_run_with_search_feeds(self):
        """测试：传入 search_feeds 进行本地新颖性检查"""
        agent = CriticAgent()
        candidates = [{"title": "论题1", "dimension": "cross_discipline", "rationale": "R"}]
        feeds = [{"title": "已有论文1"}]
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"candidates": candidates, "search_feeds": feeds}))
        assert result.success is True

    def test_run_token_usage_recorded(self):
        """测试：token 使用量被记录"""
        agent = CriticAgent()
        candidates = [{"title": "论题1", "dimension": "cross_discipline", "rationale": "R"}]
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(prompt_tokens=200, completion_tokens=100)
            result = _run_async(agent.run({"candidates": candidates}))
        assert result.token_usage["prompt_tokens"] == 200


# ===== _parse_evaluations 测试 =====


class TestParseEvaluations:
    """_parse_evaluations 方法测试"""

    def test_parse_valid_json(self):
        """测试：解析有效 JSON"""
        content = '{"evaluations": [{"title": "T", "score": 80, "novelty": 75, "feasibility": 70, "issues": [], "suggestions": []}]}'
        candidates = [{"title": "T"}]
        result = CriticAgent._parse_evaluations(content, candidates, {})
        assert len(result) == 1
        assert result[0]["title"] == "T"

    def test_parse_empty_content(self):
        """测试：空内容返回兜底"""
        candidates = [{"title": "T"}]
        result = CriticAgent._parse_evaluations("", candidates, {})
        assert len(result) > 0

    def test_parse_invalid_json(self):
        """测试：无效 JSON 返回兜底"""
        candidates = [{"title": "T"}]
        result = CriticAgent._parse_evaluations("无效内容", candidates, {})
        assert len(result) > 0

    def test_parse_filters_empty_title(self):
        """测试：空标题被过滤"""
        content = '{"evaluations": [{"title": "", "score": 80}, {"title": "有效", "score": 70}]}'
        candidates = [{"title": "有效"}]
        result = CriticAgent._parse_evaluations(content, candidates, {})
        assert len(result) == 1
        assert result[0]["title"] == "有效"

    def test_parse_json_in_code_block(self):
        """测试：解析代码块中的 JSON"""
        content = '```json\n{"evaluations": [{"title": "T", "score": 80, "novelty": 70, "feasibility": 75, "issues": [], "suggestions": []}]}\n```'
        candidates = [{"title": "T"}]
        result = CriticAgent._parse_evaluations(content, candidates, {})
        assert len(result) == 1


# ===== _safe_int 测试 =====


class TestSafeInt:
    """_safe_int 方法测试"""

    def test_safe_int_valid_integer(self):
        """测试：有效整数"""
        assert CriticAgent._safe_int(80, 0) == 80

    def test_safe_int_string_number(self):
        """测试：字符串数字"""
        assert CriticAgent._safe_int("75", 0) == 75

    def test_safe_int_invalid_string(self):
        """测试：无效字符串返回默认值"""
        assert CriticAgent._safe_int("abc", 50) == 50

    def test_safe_int_none(self):
        """测试：None 返回默认值"""
        assert CriticAgent._safe_int(None, 50) == 50

    def test_safe_int_float(self):
        """测试：浮点数转整数"""
        assert CriticAgent._safe_int(75.9, 0) == 75


# ===== _fallback_evaluations 测试 =====


class TestFallbackEvaluations:
    """_fallback_evaluations 方法测试"""

    def test_fallback_returns_evaluations(self):
        """测试：兜底返回评估列表"""
        candidates = [{"title": "论题1"}]
        result = CriticAgent._fallback_evaluations(candidates, [])
        assert len(result) == 1
        assert result[0]["title"] == "论题1"

    def test_fallback_evaluations_have_score(self):
        """测试：兜底评估包含 score"""
        candidates = [{"title": "T"}]
        result = CriticAgent._fallback_evaluations(candidates, [])
        assert "score" in result[0]
        assert isinstance(result[0]["score"], int)

    def test_fallback_evaluations_have_novelty(self):
        """测试：兜底评估包含 novelty"""
        candidates = [{"title": "T"}]
        result = CriticAgent._fallback_evaluations(candidates, [])
        assert "novelty" in result[0]

    def test_fallback_evaluations_have_feasibility(self):
        """测试：兜底评估包含 feasibility"""
        candidates = [{"title": "T"}]
        result = CriticAgent._fallback_evaluations(candidates, [])
        assert "feasibility" in result[0]

    def test_fallback_evaluations_have_issues_and_suggestions(self):
        """测试：兜底评估包含 issues 和 suggestions"""
        candidates = [{"title": "T"}]
        result = CriticAgent._fallback_evaluations(candidates, [])
        assert "issues" in result[0]
        assert "suggestions" in result[0]

    def test_fallback_with_multiple_candidates(self):
        """测试：多个候选的兜底评估"""
        candidates = [{"title": "T1"}, {"title": "T2"}, {"title": "T3"}]
        result = CriticAgent._fallback_evaluations(candidates, [])
        assert len(result) == 3


# ===== _build_user_prompt 测试 =====


class TestBuildUserPrompt:
    """_build_user_prompt 方法测试"""

    def test_prompt_contains_candidate_title(self):
        """测试：提示包含候选标题"""
        candidates = [{"title": "论题A", "dimension": "cross_discipline", "rationale": "R"}]
        prompt = CriticAgent._build_user_prompt(candidates, {})
        assert "论题A" in prompt

    def test_prompt_contains_dimension(self):
        """测试：提示包含维度"""
        candidates = [{"title": "T", "dimension": "method_transfer", "rationale": "R"}]
        prompt = CriticAgent._build_user_prompt(candidates, {})
        assert "method_transfer" in prompt

    def test_prompt_contains_novelty_info(self):
        """测试：提示包含本地新颖性信息"""
        candidates = [{"title": "T", "dimension": "cross_discipline", "rationale": "R"}]
        local_novelty = {"T": {"novelty_score": 0.3, "assessment": "高创新"}}
        prompt = CriticAgent._build_user_prompt(candidates, local_novelty)
        assert "高创新" in prompt or "0.3" in prompt

    def test_prompt_with_empty_candidates(self):
        """测试：空候选列表不崩溃"""
        prompt = CriticAgent._build_user_prompt([], {})
        assert "暂无" in prompt or len(prompt) > 0

    def test_prompt_contains_json_format(self):
        """测试：提示包含 JSON 格式说明"""
        candidates = [{"title": "T", "dimension": "cross_discipline", "rationale": "R"}]
        prompt = CriticAgent._build_user_prompt(candidates, {})
        assert "evaluations" in prompt or "JSON" in prompt
