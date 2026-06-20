"""mentor 模块单元测试

测试 backend/agents/mentor_agent.py 的 MentorAgent：
  - 初始化与属性
  - run 方法导师评审
  - _parse_response 响应解析
  - _build_user_prompt 提示构建
  - review_proposal 单次评审函数
  - batch_review 批量评审
  - fallback_review 兜底评审
  - _normalize_review 评审规范化
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
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_mentor_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.agents.base_agent import AgentResult
from backend.agents.mentor_agent import (
    MentorAgent,
    review_proposal,
    batch_review,
    fallback_review,
    _normalize_review,
)


def _run_async(coro):
    """辅助函数：运行异步协程"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_llm_result(content='{"advice": "建议进一步细化", "direction": "approve", "score": 80, "reason": "方向明确"}',
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


# ===== 初始化测试 =====


class TestMentorInit:
    """MentorAgent 初始化测试"""

    def test_init_agent_id(self):
        """测试：agent_id 为 mentor"""
        agent = MentorAgent()
        assert agent.agent_id == "mentor"

    def test_init_name(self):
        """测试：name 为 Mentor"""
        agent = MentorAgent()
        assert agent.name == "Mentor"

    def test_init_description(self):
        """测试：包含描述"""
        agent = MentorAgent()
        assert "导师" in agent.description or "Mentor" in agent.description

    def test_init_temperature(self):
        """测试：temperature 为 0.4"""
        agent = MentorAgent()
        assert agent.temperature == 0.4

    def test_init_has_system_prompt(self):
        """测试：有系统提示"""
        agent = MentorAgent()
        assert len(agent.system_prompt) > 0
        assert "导师" in agent.system_prompt or "Mentor" in agent.system_prompt

    def test_init_system_prompt_contains_direction(self):
        """测试：系统提示包含 direction 字段说明"""
        agent = MentorAgent()
        assert "direction" in agent.system_prompt
        assert "approve" in agent.system_prompt


# ===== run 方法测试 =====


class TestRun:
    """run 方法测试"""

    def test_run_returns_agent_result(self):
        """测试：run 返回 AgentResult"""
        agent = MentorAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "机器学习研究"}))
        assert isinstance(result, AgentResult)
        assert result.agent_id == "mentor"

    def test_run_success_with_topic(self):
        """测试：有效 topic 返回成功"""
        agent = MentorAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI研究"}))
        assert result.success is True

    def test_run_data_contains_advice(self):
        """测试：data 包含 advice"""
        agent = MentorAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI"}))
        assert "advice" in result.data

    def test_run_data_contains_direction(self):
        """测试：data 包含 direction"""
        agent = MentorAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI"}))
        assert "direction" in result.data

    def test_run_empty_topic_returns_failure(self):
        """测试：空 topic 返回失败"""
        agent = MentorAgent()
        result = _run_async(agent.run({"topic": ""}))
        assert result.success is False
        assert result.data["direction"] == "reject"

    def test_run_fallback_on_exception(self):
        """测试：LLM 异常时返回兜底"""
        agent = MentorAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 不可用")
            result = _run_async(agent.run({"topic": "AI"}))
        assert result.success is False
        assert "advice" in result.data

    def test_run_with_context(self):
        """测试：传入 context 不崩溃"""
        agent = MentorAgent()
        context = {
            "degree": "master",
            "discipline": "计算机",
            "mentor_info": "张教授",
            "evaluation": {"evaluations": [{"score": 75}]},
        }
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI", "context": context}))
        assert result.success is True

    def test_run_token_usage_recorded(self):
        """测试：token 使用量被记录"""
        agent = MentorAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(prompt_tokens=200, completion_tokens=100)
            result = _run_async(agent.run({"topic": "AI"}))
        assert result.token_usage["prompt_tokens"] == 200


# ===== _parse_response 测试 =====


class TestParseResponse:
    """_parse_response 方法测试"""

    def test_parse_valid_json(self):
        """测试：解析有效 JSON"""
        content = '{"advice": "好建议", "direction": "approve", "score": 85}'
        advice, direction = MentorAgent._parse_response(content)
        assert advice == "好建议"
        assert direction == "approve"

    def test_parse_empty_content(self):
        """测试：空内容返回兜底"""
        advice, direction = MentorAgent._parse_response("")
        assert direction == "revise"

    def test_parse_invalid_json(self):
        """测试：无效 JSON 返回兜底"""
        advice, direction = MentorAgent._parse_response("这不是JSON")
        assert direction == "revise"

    def test_parse_invalid_direction_normalized(self):
        """测试：无效 direction 被规范化为 revise"""
        content = '{"advice": "建议", "direction": "invalid"}'
        advice, direction = MentorAgent._parse_response(content)
        assert direction == "revise"

    def test_parse_json_in_code_block(self):
        """测试：解析代码块中的 JSON"""
        content = '```json\n{"advice": "代码块建议", "direction": "reject"}\n```'
        advice, direction = MentorAgent._parse_response(content)
        assert advice == "代码块建议"
        assert direction == "reject"

    def test_parse_json_embedded_in_text(self):
        """测试：解析嵌入文本的 JSON"""
        content = '评审结果：{"advice": "嵌入建议", "direction": "approve"} 完成'
        advice, direction = MentorAgent._parse_response(content)
        assert advice == "嵌入建议"
        assert direction == "approve"

    def test_parse_approve_direction(self):
        """测试：解析 approve 方向"""
        content = '{"advice": "通过", "direction": "approve"}'
        _, direction = MentorAgent._parse_response(content)
        assert direction == "approve"

    def test_parse_reject_direction(self):
        """测试：解析 reject 方向"""
        content = '{"advice": "拒绝", "direction": "reject"}'
        _, direction = MentorAgent._parse_response(content)
        assert direction == "reject"


# ===== _build_user_prompt 测试 =====


class TestBuildUserPrompt:
    """_build_user_prompt 方法测试"""

    def test_prompt_contains_topic(self):
        """测试：提示包含论题"""
        prompt = MentorAgent._build_user_prompt("AI研究", {})
        assert "AI研究" in prompt

    def test_prompt_contains_degree_label(self):
        """测试：提示包含学位标签"""
        prompt = MentorAgent._build_user_prompt("T", {"degree": "master"})
        assert "硕士" in prompt
        prompt2 = MentorAgent._build_user_prompt("T", {"degree": "doctor"})
        assert "博士" in prompt2

    def test_prompt_contains_discipline(self):
        """测试：提示包含学科"""
        prompt = MentorAgent._build_user_prompt("T", {"discipline": "计算机"})
        assert "计算机" in prompt

    def test_prompt_contains_mentor_info(self):
        """测试：提示包含导师信息"""
        prompt = MentorAgent._build_user_prompt("T", {"mentor_info": "张教授"})
        assert "张教授" in prompt

    def test_prompt_with_evaluation(self):
        """测试：包含评估信息"""
        context = {"evaluation": {"evaluations": [{"score": 75, "issues": ["问题"]}]}}
        prompt = MentorAgent._build_user_prompt("T", context)
        assert "75" in prompt or "评估" in prompt

    def test_prompt_empty_context(self):
        """测试：空上下文不崩溃"""
        prompt = MentorAgent._build_user_prompt("T", {})
        assert len(prompt) > 0


# ===== _normalize_review 测试 =====


class TestNormalizeReview:
    """_normalize_review 函数测试"""

    def test_normalize_complete_review(self):
        """测试：规范化完整评审"""
        review = {"score": 85, "comments": "好", "suggestions": "建议", "approve": True}
        result = _normalize_review(review)
        assert result["score"] == 85.0
        assert result["comments"] == "好"
        assert result["approve"] is True

    def test_normalize_empty_review(self):
        """测试：空评审使用默认值"""
        result = _normalize_review({})
        assert result["score"] == 0.0
        assert "暂无" in result["comments"]
        assert result["approve"] is False

    def test_normalize_string_score(self):
        """测试：字符串评分（非数值）转为 0.0"""
        result = _normalize_review({"score": "不是数字"})
        assert result["score"] == 0.0

    def test_normalize_float_score(self):
        """测试：浮点数评分保留"""
        result = _normalize_review({"score": 85.5})
        assert result["score"] == 85.5

    def test_normalize_invalid_score(self):
        """测试：无效评分转为 0"""
        result = _normalize_review({"score": "abc"})
        assert result["score"] == 0.0

    def test_normalize_approve_boolean(self):
        """测试：approve 转为布尔"""
        result = _normalize_review({"approve": 1})
        assert result["approve"] is True
        result2 = _normalize_review({"approve": 0})
        assert result2["approve"] is False


# ===== fallback_review 测试 =====


class TestFallbackReview:
    """fallback_review 函数测试"""

    def test_fallback_high_confidence(self):
        """测试：高置信度返回 approve"""
        proposal = {"confidence_score": 0.9}
        result = fallback_review(proposal)
        assert result["approve"] is True
        assert result["score"] >= 0.8

    def test_fallback_medium_confidence(self):
        """测试：中等置信度返回 revise"""
        proposal = {"confidence_score": 0.65}
        result = fallback_review(proposal)
        assert result["approve"] is False

    def test_fallback_low_confidence(self):
        """测试：低置信度返回 reject"""
        proposal = {"confidence_score": 0.3}
        result = fallback_review(proposal)
        assert result["approve"] is False

    def test_fallback_default_confidence(self):
        """测试：默认置信度为 0.5"""
        result = fallback_review({})
        assert result["score"] == 0.5

    def test_fallback_has_comments(self):
        """测试：兜底评审包含 comments"""
        result = fallback_review({"confidence_score": 0.8})
        assert len(result["comments"]) > 0

    def test_fallback_has_suggestions(self):
        """测试：兜底评审包含 suggestions"""
        result = fallback_review({"confidence_score": 0.5})
        assert len(result["suggestions"]) > 0


# ===== batch_review 测试 =====


class TestBatchReview:
    """batch_review 函数测试"""

    def test_batch_review_multiple_proposals(self):
        """测试：批量评审多个提案"""
        proposals = [
            {"confidence_score": 0.9},
            {"confidence_score": 0.5},
            {"confidence_score": 0.3},
        ]
        results = _run_async(batch_review(proposals))
        assert len(results) == 3

    def test_batch_review_empty_list(self):
        """测试：空列表返回空"""
        results = _run_async(batch_review([]))
        assert results == []

    def test_batch_review_fallback_on_exception(self):
        """测试：单个失败时使用兜底"""
        proposals = [{"confidence_score": 0.8}]
        with patch("backend.agents.mentor_agent.review_proposal", side_effect=Exception("失败")):
            results = _run_async(batch_review(proposals))
        assert len(results) == 1
        # 应使用 fallback_review
        assert "comments" in results[0]
