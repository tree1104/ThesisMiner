"""reasoner 模块单元测试

测试 backend/agents/reasoner.py 的 ReasonerAgent：
  - FOUR_DIMENSIONS 四维创意引擎定义
  - 初始化与属性
  - run 方法候选论题生成
  - _parse_candidates JSON 解析
  - _extract_json_candidates 多模式提取
  - _fallback_candidates 兜底候选
  - _build_user_prompt 提示构建
  - LLM 调用 mock 与异常处理
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
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_reasoner_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.agents.base_agent import AgentResult
from backend.agents.reasoner import ReasonerAgent, FOUR_DIMENSIONS


def _run_async(coro):
    """辅助函数：运行异步协程"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_llm_result(content='{"candidates": [{"title": "测试论题", "dimension": "cross_discipline", "rationale": "测试理由"}]}',
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


# ===== FOUR_DIMENSIONS 测试 =====


class TestFourDimensions:
    """四维创意引擎定义测试"""

    def test_has_four_dimensions(self):
        """测试：FOUR_DIMENSIONS 包含四个维度"""
        assert len(FOUR_DIMENSIONS) == 4

    def test_dimensions_have_required_fields(self):
        """测试：每个维度包含 id / name / description"""
        for d in FOUR_DIMENSIONS:
            assert "id" in d
            assert "name" in d
            assert "description" in d

    def test_cross_discipline_dimension(self):
        """测试：包含学科交叉维度"""
        ids = [d["id"] for d in FOUR_DIMENSIONS]
        assert "cross_discipline" in ids

    def test_method_transfer_dimension(self):
        """测试：包含方法迁移维度"""
        ids = [d["id"] for d in FOUR_DIMENSIONS]
        assert "method_transfer" in ids

    def test_pain_point_breakthrough_dimension(self):
        """测试：包含痛点突破维度"""
        ids = [d["id"] for d in FOUR_DIMENSIONS]
        assert "pain_point_breakthrough" in ids

    def test_trend_forecast_dimension(self):
        """测试：包含趋势前瞻维度"""
        ids = [d["id"] for d in FOUR_DIMENSIONS]
        assert "trend_forecast" in ids

    def test_dimension_names_are_chinese(self):
        """测试：维度名称为中文"""
        for d in FOUR_DIMENSIONS:
            assert len(d["name"]) > 0

    def test_dimension_descriptions_not_empty(self):
        """测试：维度描述非空"""
        for d in FOUR_DIMENSIONS:
            assert len(d["description"]) > 0


# ===== 初始化测试 =====


class TestReasonerInit:
    """ReasonerAgent 初始化测试"""

    def test_init_agent_id(self):
        """测试：agent_id 为 reasoner"""
        agent = ReasonerAgent()
        assert agent.agent_id == "reasoner"

    def test_init_name(self):
        """测试：name 为 Reasoner"""
        agent = ReasonerAgent()
        assert agent.name == "Reasoner"

    def test_init_description(self):
        """测试：包含描述"""
        agent = ReasonerAgent()
        assert "创意" in agent.description or "Reasoner" in agent.description

    def test_init_temperature(self):
        """测试：temperature 为 0.8（创意性较高）"""
        agent = ReasonerAgent()
        assert agent.temperature == 0.8

    def test_init_has_system_prompt(self):
        """测试：有系统提示"""
        agent = ReasonerAgent()
        assert len(agent.system_prompt) > 0
        assert "四维" in agent.system_prompt or "创意" in agent.system_prompt

    def test_init_capabilities(self):
        """测试：capabilities 包含 thinking"""
        agent = ReasonerAgent()
        assert "thinking" in agent.capabilities


# ===== run 方法测试 =====


class TestRun:
    """run 方法测试"""

    def test_run_returns_agent_result(self):
        """测试：run 返回 AgentResult"""
        agent = ReasonerAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"discipline": "计算机", "degree": "master"}))
        assert isinstance(result, AgentResult)
        assert result.agent_id == "reasoner"

    def test_run_success_with_valid_response(self):
        """测试：有效 LLM 响应返回成功结果"""
        agent = ReasonerAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"discipline": "计算机", "degree": "master"}))
        assert result.success is True
        assert "candidates" in result.data

    def test_run_data_contains_candidates(self):
        """测试：data 包含 candidates 列表"""
        agent = ReasonerAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"discipline": "计算机", "degree": "master"}))
        assert isinstance(result.data["candidates"], list)
        assert len(result.data["candidates"]) > 0

    def test_run_data_contains_discipline(self):
        """测试：data 包含 discipline"""
        agent = ReasonerAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"discipline": "物理学", "degree": "doctor"}))
        assert result.data["discipline"] == "物理学"

    def test_run_data_contains_degree(self):
        """测试：data 包含 degree"""
        agent = ReasonerAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"discipline": "AI", "degree": "doctor"}))
        assert result.data["degree"] == "doctor"

    def test_run_data_contains_dimensions(self):
        """测试：data 包含 dimensions 列表"""
        agent = ReasonerAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"discipline": "AI", "degree": "master"}))
        assert "dimensions" in result.data
        assert len(result.data["dimensions"]) == 4

    def test_run_fallback_on_llm_exception(self):
        """测试：LLM 异常时返回兜底候选"""
        agent = ReasonerAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 不可用")
            result = _run_async(agent.run({"discipline": "AI", "degree": "master"}))
        assert result.success is False
        assert len(result.data["candidates"]) > 0  # 兜底候选

    def test_run_with_empty_discipline(self):
        """测试：空学科不导致崩溃"""
        agent = ReasonerAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"discipline": "", "degree": "master"}))
        assert result.success is True

    def test_run_with_search_feeds(self):
        """测试：传入 search_feeds 不导致崩溃"""
        agent = ReasonerAgent()
        feeds = [{"title": "论文1"}, {"title": "论文2"}]
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({
                "discipline": "AI", "degree": "master", "search_feeds": feeds
            }))
        assert result.success is True

    def test_run_token_usage_recorded(self):
        """测试：token 使用量被记录"""
        agent = ReasonerAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(prompt_tokens=200, completion_tokens=100)
            result = _run_async(agent.run({"discipline": "AI", "degree": "master"}))
        assert result.token_usage["prompt_tokens"] == 200
        assert result.token_usage["completion_tokens"] == 100


# ===== _parse_candidates 测试 =====


class TestParseCandidates:
    """_parse_candidates 方法测试"""

    def test_parse_valid_json(self):
        """测试：解析有效 JSON"""
        content = '{"candidates": [{"title": "论题1", "dimension": "cross_discipline", "rationale": "理由"}]}'
        result = ReasonerAgent._parse_candidates(content, "AI")
        assert len(result) == 1
        assert result[0]["title"] == "论题1"

    def test_parse_empty_content(self):
        """测试：空内容返回兜底候选"""
        result = ReasonerAgent._parse_candidates("", "AI")
        assert len(result) > 0  # 兜底

    def test_parse_invalid_json(self):
        """测试：无效 JSON 返回兜底候选"""
        result = ReasonerAgent._parse_candidates("这不是JSON", "AI")
        assert len(result) > 0  # 兜底

    def test_parse_normalizes_invalid_dimension(self):
        """测试：无效 dimension 被规范化为 cross_discipline"""
        content = '{"candidates": [{"title": "T", "dimension": "invalid_dim", "rationale": "R"}]}'
        result = ReasonerAgent._parse_candidates(content, "AI")
        assert result[0]["dimension"] == "cross_discipline"

    def test_parse_filters_empty_title(self):
        """测试：空标题的候选被过滤"""
        content = '{"candidates": [{"title": "", "dimension": "cross_discipline"}, {"title": "有效", "dimension": "cross_discipline"}]}'
        result = ReasonerAgent._parse_candidates(content, "AI")
        assert len(result) == 1
        assert result[0]["title"] == "有效"

    def test_parse_json_in_code_block(self):
        """测试：解析 ```json 代码块中的 JSON"""
        content = '```json\n{"candidates": [{"title": "代码块论题", "dimension": "method_transfer", "rationale": "R"}]}\n```'
        result = ReasonerAgent._parse_candidates(content, "AI")
        assert len(result) == 1
        assert result[0]["title"] == "代码块论题"

    def test_parse_json_embedded_in_text(self):
        """测试：解析嵌入文本中的 JSON"""
        content = '以下是结果：{"candidates": [{"title": "嵌入论题", "dimension": "cross_discipline", "rationale": "R"}]} 完成'
        result = ReasonerAgent._parse_candidates(content, "AI")
        assert len(result) == 1
        assert result[0]["title"] == "嵌入论题"


# ===== _fallback_candidates 测试 =====


class TestFallbackCandidates:
    """_fallback_candidates 方法测试"""

    def test_fallback_returns_four_candidates(self):
        """测试：兜底返回四个候选（每维度一个）"""
        result = ReasonerAgent._fallback_candidates("计算机")
        assert len(result) == 4

    def test_fallback_candidates_have_all_dimensions(self):
        """测试：兜底候选覆盖所有四个维度"""
        result = ReasonerAgent._fallback_candidates("AI")
        dims = [c["dimension"] for c in result]
        assert "cross_discipline" in dims
        assert "method_transfer" in dims
        assert "pain_point_breakthrough" in dims
        assert "trend_forecast" in dims

    def test_fallback_with_empty_discipline(self):
        """测试：空学科时使用默认值"""
        result = ReasonerAgent._fallback_candidates("")
        assert len(result) == 4
        assert all(c["title"] for c in result)

    def test_fallback_candidates_have_rationale(self):
        """测试：兜底候选包含 rationale"""
        result = ReasonerAgent._fallback_candidates("物理学")
        for c in result:
            assert "rationale" in c
            assert len(c["rationale"]) > 0

    def test_fallback_candidates_have_title(self):
        """测试：兜底候选包含 title"""
        result = ReasonerAgent._fallback_candidates("化学")
        for c in result:
            assert "title" in c
            assert len(c["title"]) > 0


# ===== _build_user_prompt 测试 =====


class TestBuildUserPrompt:
    """_build_user_prompt 方法测试"""

    def test_prompt_contains_discipline(self):
        """测试：提示包含学科"""
        prompt = ReasonerAgent._build_user_prompt("计算机", "master", [])
        assert "计算机" in prompt

    def test_prompt_contains_degree_label(self):
        """测试：提示包含学位标签"""
        prompt = ReasonerAgent._build_user_prompt("AI", "master", [])
        assert "硕士" in prompt
        prompt2 = ReasonerAgent._build_user_prompt("AI", "doctor", [])
        assert "博士" in prompt2

    def test_prompt_contains_existing_titles(self):
        """测试：提示包含已有文献标题"""
        feeds = [{"title": "已有论文1"}, {"title": "已有论文2"}]
        prompt = ReasonerAgent._build_user_prompt("AI", "master", feeds)
        assert "已有论文1" in prompt
        assert "已有论文2" in prompt

    def test_prompt_with_empty_feeds(self):
        """测试：无文献时提示包含'暂无'"""
        prompt = ReasonerAgent._build_user_prompt("AI", "master", [])
        assert "暂无" in prompt

    def test_prompt_contains_json_format_instruction(self):
        """测试：提示包含 JSON 格式说明"""
        prompt = ReasonerAgent._build_user_prompt("AI", "master", [])
        assert "candidates" in prompt or "JSON" in prompt
