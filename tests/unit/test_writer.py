"""writer 模块单元测试

测试 backend/agents/proposal_writer.py 的 WriterAgent：
  - GRANULARITIES 粒度常量
  - 初始化与属性
  - run 方法多粒度生成
  - _build_user_prompt 提示构建
  - _template_fallback 模板兜底
  - generate_report 报告生成函数
  - _generate_with_template 模板生成
  - _deserialize_fields 字段反序列化
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
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_writer_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.agents.base_agent import AgentResult
from backend.agents.proposal_writer import (
    WriterAgent,
    GRANULARITIES,
    generate_report,
    _generate_with_template,
    _deserialize_fields,
)


def _run_async(coro):
    """辅助函数：运行异步协程"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_llm_result(content="# 生成的开题报告\n\n## 一、选题依据\n...",
                     prompt_tokens=100, completion_tokens=200):
    """构造模拟的 call_llm 返回值"""
    return {
        "content": content,
        "model": "mock-model",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost": 0.0,
    }


# ===== GRANULARITIES 测试 =====


class TestGranularities:
    """GRANULARITIES 常量测试"""

    def test_has_four_granularities(self):
        """测试：包含四种粒度"""
        assert len(GRANULARITIES) == 4

    def test_contains_title(self):
        """测试：包含 title 粒度"""
        assert "title" in GRANULARITIES

    def test_contains_abstract(self):
        """测试：包含 abstract 粒度"""
        assert "abstract" in GRANULARITIES

    def test_contains_outline(self):
        """测试：包含 outline 粒度"""
        assert "outline" in GRANULARITIES

    def test_contains_full(self):
        """测试：包含 full 粒度"""
        assert "full" in GRANULARITIES


# ===== 初始化测试 =====


class TestWriterInit:
    """WriterAgent 初始化测试"""

    def test_init_agent_id(self):
        """测试：agent_id 为 writer"""
        agent = WriterAgent()
        assert agent.agent_id == "writer"

    def test_init_name(self):
        """测试：name 为 Writer"""
        agent = WriterAgent()
        assert agent.name == "Writer"

    def test_init_description(self):
        """测试：包含描述"""
        agent = WriterAgent()
        assert "生成" in agent.description or "Writer" in agent.description

    def test_init_temperature(self):
        """测试：temperature 为 0.6"""
        agent = WriterAgent()
        assert agent.temperature == 0.6

    def test_init_has_system_prompt(self):
        """测试：有系统提示"""
        agent = WriterAgent()
        assert len(agent.system_prompt) > 0
        assert "粒度" in agent.system_prompt or "Writer" in agent.system_prompt

    def test_init_capabilities(self):
        """测试：capabilities 包含 streaming"""
        agent = WriterAgent()
        assert "streaming" in agent.capabilities

    def test_init_max_tokens(self):
        """测试：max_tokens 为 8192"""
        agent = WriterAgent()
        assert agent.max_tokens == 8192


# ===== run 方法测试 =====


class TestRun:
    """run 方法测试"""

    def test_run_returns_agent_result(self):
        """测试：run 返回 AgentResult"""
        agent = WriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI研究", "granularity": "outline"}))
        assert isinstance(result, AgentResult)
        assert result.agent_id == "writer"

    def test_run_success_with_topic(self):
        """测试：有效 topic 返回成功"""
        agent = WriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI", "granularity": "outline"}))
        assert result.success is True

    def test_run_data_contains_content(self):
        """测试：data 包含 content"""
        agent = WriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI", "granularity": "outline"}))
        assert "content" in result.data

    def test_run_data_contains_granularity(self):
        """测试：data 包含 granularity"""
        agent = WriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI", "granularity": "abstract"}))
        assert result.data["granularity"] == "abstract"

    def test_run_data_contains_word_count(self):
        """测试：data 包含 word_count"""
        agent = WriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI", "granularity": "full"}))
        assert "word_count" in result.data
        assert result.data["word_count"] > 0

    def test_run_empty_topic_returns_failure(self):
        """测试：空 topic 返回失败"""
        agent = WriterAgent()
        result = _run_async(agent.run({"topic": "", "granularity": "outline"}))
        assert result.success is False

    def test_run_invalid_granularity_normalized(self):
        """测试：无效粒度被规范化为 outline"""
        agent = WriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI", "granularity": "invalid"}))
        assert result.data["granularity"] == "outline"

    def test_run_fallback_on_exception(self):
        """测试：LLM 异常时使用模板兜底"""
        agent = WriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 不可用")
            result = _run_async(agent.run({"topic": "AI", "granularity": "outline"}))
        assert result.success is False
        assert len(result.data["content"]) > 0  # 模板兜底

    def test_run_empty_llm_response_uses_fallback(self):
        """测试：LLM 返回空内容时使用模板兜底"""
        agent = WriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="")
            result = _run_async(agent.run({"topic": "AI", "granularity": "outline"}))
        assert result.success is True
        assert len(result.data["content"]) > 0

    def test_run_token_usage_recorded(self):
        """测试：token 使用量被记录"""
        agent = WriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(prompt_tokens=300, completion_tokens=500)
            result = _run_async(agent.run({"topic": "AI", "granularity": "full"}))
        assert result.token_usage["prompt_tokens"] == 300
        assert result.token_usage["completion_tokens"] == 500

    def test_run_with_context(self):
        """测试：传入 context 不崩溃"""
        agent = WriterAgent()
        context = {
            "search_feeds": [{"title": "论文1", "year": 2025}],
            "evaluation": {"evaluations": [{"score": 80, "issues": ["问题"]}]},
        }
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            result = _run_async(agent.run({"topic": "AI", "granularity": "full", "context": context}))
        assert result.success is True


# ===== _build_user_prompt 测试 =====


class TestBuildUserPrompt:
    """_build_user_prompt 方法测试"""

    def test_prompt_contains_topic(self):
        """测试：提示包含论题"""
        prompt = WriterAgent._build_user_prompt("AI研究", "outline", {})
        assert "AI研究" in prompt

    def test_prompt_contains_granularity_desc(self):
        """测试：提示包含粒度描述"""
        prompt = WriterAgent._build_user_prompt("T", "abstract", {})
        assert "摘要" in prompt or "abstract" in prompt.lower()

    def test_prompt_with_search_feeds(self):
        """测试：提示包含文献"""
        feeds = [{"title": "论文A", "year": 2025}]
        prompt = WriterAgent._build_user_prompt("T", "outline", {"search_feeds": feeds})
        assert "论文A" in prompt

    def test_prompt_with_evaluation(self):
        """测试：提示包含评估信息"""
        context = {"evaluation": {"evaluations": [{"score": 75, "issues": ["问题1"]}]}}
        prompt = WriterAgent._build_user_prompt("T", "outline", context)
        assert "75" in prompt or "评估" in prompt

    def test_prompt_empty_context(self):
        """测试：空上下文不崩溃"""
        prompt = WriterAgent._build_user_prompt("T", "outline", {})
        assert len(prompt) > 0

    def test_prompt_title_granularity(self):
        """测试：title 粒度提示"""
        prompt = WriterAgent._build_user_prompt("T", "title", {})
        assert "标题" in prompt or "title" in prompt.lower()

    def test_prompt_full_granularity(self):
        """测试：full 粒度提示"""
        prompt = WriterAgent._build_user_prompt("T", "full", {})
        assert "完整" in prompt or "full" in prompt.lower()


# ===== _template_fallback 测试 =====


class TestTemplateFallback:
    """_template_fallback 方法测试"""

    def test_fallback_title_returns_topic(self):
        """测试：title 粒度返回论题本身"""
        result = WriterAgent._template_fallback("AI研究", "title", {})
        assert result == "AI研究"

    def test_fallback_abstract_returns_text(self):
        """测试：abstract 粒度返回摘要文本"""
        result = WriterAgent._template_fallback("AI", "abstract", {})
        assert len(result) > 0
        assert "AI" in result

    def test_fallback_outline_returns_markdown(self):
        """测试：outline 粒度返回 Markdown 大纲"""
        result = WriterAgent._template_fallback("AI", "outline", {})
        assert "#" in result  # Markdown 标题
        assert "AI" in result

    def test_fallback_full_returns_markdown(self):
        """测试：full 粒度返回 Markdown 报告"""
        result = WriterAgent._template_fallback("AI", "full", {})
        assert "#" in result
        assert "AI" in result

    def test_fallback_outline_has_sections(self):
        """测试：outline 包含多个章节"""
        result = WriterAgent._template_fallback("T", "outline", {})
        assert "选题依据" in result or "研究现状" in result

    def test_fallback_full_has_basic_info(self):
        """测试：full 包含基本信息"""
        result = WriterAgent._template_fallback("AI研究", "full", {})
        assert "AI研究" in result


# ===== _generate_with_template 测试 =====


class TestGenerateWithTemplate:
    """_generate_with_template 函数测试"""

    def test_template_generates_markdown(self):
        """测试：模板生成 Markdown"""
        proposal = {"title": "AI研究", "problem_awareness": "问题"}
        result = _generate_with_template(proposal, "master", "计算机", "张教授")
        assert "#" in result
        assert "AI研究" in result

    def test_template_contains_degree_label(self):
        """测试：模板包含学位标签"""
        proposal = {"title": "T"}
        result = _generate_with_template(proposal, "master", "", "")
        assert "硕士" in result
        result2 = _generate_with_template(proposal, "doctor", "", "")
        assert "博士" in result2

    def test_template_contains_discipline(self):
        """测试：模板包含学科"""
        proposal = {"title": "T"}
        result = _generate_with_template(proposal, "master", "物理学", "")
        assert "物理学" in result

    def test_template_contains_mentor(self):
        """测试：模板包含导师"""
        proposal = {"title": "T"}
        result = _generate_with_template(proposal, "master", "", "李教授")
        assert "李教授" in result

    def test_template_master_schedule(self):
        """测试：硕士进度安排"""
        proposal = {"title": "T"}
        result = _generate_with_template(proposal, "master", "", "")
        assert "第1-2个月" in result or "12个月" in result

    def test_template_doctor_schedule(self):
        """测试：博士进度安排"""
        proposal = {"title": "T"}
        result = _generate_with_template(proposal, "doctor", "", "")
        assert "第1-3个月" in result or "24个月" in result

    def test_template_with_research_content_list(self):
        """测试：研究内容列表"""
        proposal = {"title": "T", "research_content": ["内容1", "内容2"]}
        result = _generate_with_template(proposal, "master", "", "")
        assert "内容1" in result
        assert "内容2" in result

    def test_template_with_significance_dict(self):
        """测试：研究意义字典"""
        proposal = {
            "title": "T",
            "research_significance": {"theoretical": "理论意义", "practical": "实践意义"},
        }
        result = _generate_with_template(proposal, "master", "", "")
        assert "理论意义" in result
        assert "实践意义" in result


# ===== _deserialize_fields 测试 =====


class TestDeserializeFields:
    """_deserialize_fields 函数测试"""

    def test_deserialize_valid_json(self):
        """测试：反序列化有效 JSON 字段"""
        proposal = {
            "research_significance": '{"theoretical": "理论", "practical": "实践"}',
            "research_content": '["内容1", "内容2"]',
        }
        _deserialize_fields(proposal)
        assert proposal["research_significance"]["theoretical"] == "理论"
        assert proposal["research_content"] == ["内容1", "内容2"]

    def test_deserialize_invalid_json_preserves_original(self):
        """测试：无效 JSON 保留原始字符串"""
        proposal = {"research_significance": "不是JSON", "research_content": "也不是JSON"}
        _deserialize_fields(proposal)
        assert proposal["research_significance"] == "不是JSON"

    def test_deserialize_already_dict(self):
        """测试：已是字典不做处理"""
        proposal = {"research_significance": {"key": "value"}}
        _deserialize_fields(proposal)
        assert proposal["research_significance"] == {"key": "value"}

    def test_deserialize_already_list(self):
        """测试：已是列表不做处理"""
        proposal = {"research_content": ["a", "b"]}
        _deserialize_fields(proposal)
        assert proposal["research_content"] == ["a", "b"]

    def test_deserialize_missing_fields(self):
        """测试：缺失字段不崩溃"""
        proposal = {"title": "T"}
        _deserialize_fields(proposal)  # 不应抛出异常
        assert proposal["title"] == "T"
