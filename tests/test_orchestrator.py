"""Task 5 测试：验证 v8.0 多 Agent 架构与 Orchestrator

验证：
- Orchestrator 初始化包含 5 个阶段
- 阶段推进正常工作
- 评分 < 60 触发回退（retry）
- 子 Agent 拥有独立上下文（reasoner.messages != mentor.messages）
- 通过 mock call_llm 避免真实 API 调用
"""
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_llm_result(content: str) -> dict:
    """构造模拟的 call_llm 返回值"""
    return {
        "content": content,
        "model": "mock-model",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "cached_tokens": 0,
        "cost": 0.0,
    }


class TestOrchestratorInit:
    """Orchestrator 初始化测试"""

    def test_orchestrator_initializes_with_5_stages(self):
        """Orchestrator 应初始化包含 5 个阶段"""
        from backend.agents.orchestrator import OrchestratorAgent

        orchestrator = OrchestratorAgent()
        assert len(OrchestratorAgent.STAGES) == 5
        expected_stages = [
            "info_confirm",
            "creativity",
            "validation",
            "generation",
            "deep_assist",
        ]
        assert OrchestratorAgent.STAGES == expected_stages

    def test_orchestrator_initial_stage_is_info_confirm(self):
        """初始阶段应为 info_confirm"""
        from backend.agents.orchestrator import OrchestratorAgent

        orchestrator = OrchestratorAgent()
        assert orchestrator.current_stage == "info_confirm"
        assert orchestrator.get_stage() == "info_confirm"

    def test_orchestrator_agent_id(self):
        """Orchestrator 的 agent_id 应为 orchestrator"""
        from backend.agents.orchestrator import OrchestratorAgent

        orchestrator = OrchestratorAgent()
        assert orchestrator.agent_id == "orchestrator"
        assert orchestrator.name == "Orchestrator"

    def test_orchestrator_has_stage_results_dict(self):
        """Orchestrator 应有 stage_results 字典"""
        from backend.agents.orchestrator import OrchestratorAgent

        orchestrator = OrchestratorAgent()
        assert isinstance(orchestrator.stage_results, dict)
        assert len(orchestrator.stage_results) == 0


class TestStageProgression:
    """阶段推进测试"""

    def test_confirm_info_advances_to_creativity(self):
        """confirm_info 应将阶段从 info_confirm 推进到 creativity"""
        from backend.agents.orchestrator import OrchestratorAgent

        orchestrator = OrchestratorAgent()
        assert orchestrator.current_stage == "info_confirm"
        result = orchestrator.confirm_info()
        assert result is True
        assert orchestrator.current_stage == "creativity"

    def test_confirm_info_returns_false_when_not_in_info_confirm(self):
        """非 info_confirm 阶段调用 confirm_info 应返回 False"""
        from backend.agents.orchestrator import OrchestratorAgent

        orchestrator = OrchestratorAgent()
        orchestrator.current_stage = "creativity"
        result = orchestrator.confirm_info()
        assert result is False
        assert orchestrator.current_stage == "creativity"

    def test_reset_returns_to_info_confirm(self):
        """reset 应将阶段重置为 info_confirm"""
        from backend.agents.orchestrator import OrchestratorAgent

        orchestrator = OrchestratorAgent()
        orchestrator.current_stage = "deep_assist"
        orchestrator.stage_results = {"some": "data"}
        orchestrator.reset()
        assert orchestrator.current_stage == "info_confirm"
        assert orchestrator.stage_results == {}


class TestOrchestratorFlow:
    """Orchestrator 流程测试（mock call_llm）"""

    @pytest.mark.asyncio
    async def test_full_flow_completes_all_stages(self):
        """完整流程应推进到 deep_assist 阶段"""
        from backend.agents.orchestrator import OrchestratorAgent

        # Mock call_llm 返回合理的 JSON
        search_content = json.dumps({
            "summary": "检索到5篇相关文献",
            "key_findings": ["发现1", "发现2"],
        })
        reasoner_content = json.dumps({
            "candidates": [
                {"title": "测试论题1", "dimension": "cross_discipline", "rationale": "理由1"},
                {"title": "测试论题2", "dimension": "method_transfer", "rationale": "理由2"},
            ]
        })
        critic_content = json.dumps({
            "evaluations": [
                {
                    "title": "测试论题1",
                    "score": 80,
                    "novelty": 75,
                    "feasibility": 85,
                    "issues": [],
                    "suggestions": ["建议1"],
                }
            ]
        })
        writer_content = "# 开题报告大纲\n## 一、选题依据\n..."

        # 按调用顺序返回不同内容
        call_sequence = [
            search_content,
            reasoner_content,
            critic_content,
            writer_content,
        ]
        call_index = {"i": 0}

        async def mock_call_llm(**kwargs):
            idx = call_index["i"]
            call_index["i"] += 1
            content = call_sequence[idx] if idx < len(call_sequence) else "{}"
            return _make_llm_result(content)

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            orchestrator = OrchestratorAgent()
            orchestrator.reset()

            chunks = []
            async for chunk in orchestrator.orchestrate("深度学习", conversation_id="test"):
                chunks.append(chunk)

        # 应推进到 deep_assist
        assert orchestrator.current_stage == "deep_assist"

        # 应有各阶段的 started 与 completed 事件
        stages_seen = {c["stage"] for c in chunks}
        assert "info_confirm" in stages_seen
        assert "creativity" in stages_seen
        assert "validation" in stages_seen
        assert "generation" in stages_seen
        assert "deep_assist" in stages_seen

    @pytest.mark.asyncio
    async def test_low_score_triggers_retry(self):
        """评分 < 60 应触发 retry 并回退到 creativity"""
        from backend.agents.orchestrator import OrchestratorAgent

        search_content = json.dumps({"summary": "检索完成", "key_findings": []})
        reasoner_content = json.dumps({
            "candidates": [
                {"title": "低分论题", "dimension": "cross_discipline", "rationale": "理由"}
            ]
        })
        # 评分低于 60
        critic_content = json.dumps({
            "evaluations": [
                {
                    "title": "低分论题",
                    "score": 40,
                    "novelty": 30,
                    "feasibility": 50,
                    "issues": ["新颖性不足"],
                    "suggestions": ["重新选题"],
                }
            ]
        })

        call_sequence = [search_content, reasoner_content, critic_content]
        call_index = {"i": 0}

        async def mock_call_llm(**kwargs):
            idx = call_index["i"]
            call_index["i"] += 1
            content = call_sequence[idx] if idx < len(call_sequence) else "{}"
            return _make_llm_result(content)

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            orchestrator = OrchestratorAgent()
            orchestrator.reset()

            chunks = []
            async for chunk in orchestrator.orchestrate("测试方向", conversation_id="test"):
                chunks.append(chunk)

        # 应回退到 creativity
        assert orchestrator.current_stage == "creativity"

        # 应有 retry 状态的事件
        retry_chunks = [c for c in chunks if c.get("status") == "retry"]
        assert len(retry_chunks) > 0
        assert "回退" in retry_chunks[0]["content"] or "retry" in retry_chunks[0]["status"]

    @pytest.mark.asyncio
    async def test_run_returns_agent_result(self):
        """run() 应返回 AgentResult"""
        from backend.agents.base_agent import AgentResult
        from backend.agents.orchestrator import OrchestratorAgent

        search_content = json.dumps({"summary": "检索完成", "key_findings": []})
        reasoner_content = json.dumps({
            "candidates": [
                {"title": "测试论题", "dimension": "cross_discipline", "rationale": "理由"}
            ]
        })
        critic_content = json.dumps({
            "evaluations": [
                {
                    "title": "测试论题",
                    "score": 75,
                    "novelty": 70,
                    "feasibility": 80,
                    "issues": [],
                    "suggestions": [],
                }
            ]
        })
        writer_content = "# 大纲"

        call_sequence = [search_content, reasoner_content, critic_content, writer_content]
        call_index = {"i": 0}

        async def mock_call_llm(**kwargs):
            idx = call_index["i"]
            call_index["i"] += 1
            content = call_sequence[idx] if idx < len(call_sequence) else "{}"
            return _make_llm_result(content)

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            orchestrator = OrchestratorAgent()
            orchestrator.reset()

            result = await orchestrator.run({"user_input": "机器学习"})

        assert isinstance(result, AgentResult)
        assert result.agent_id == "orchestrator"
        assert result.success is True
        assert "stages" in result.data
        assert "final_stage" in result.data


class TestIndependentContexts:
    """子 Agent 上下文独立性测试"""

    def test_reasoner_and_mentor_have_independent_contexts(self):
        """reasoner 与 mentor 的 messages 应相互独立"""
        from backend.agents.agent_registry import get_agent, reset_all_contexts

        # 先重置所有上下文，避免被前置测试污染
        reset_all_contexts()

        reasoner = get_agent("reasoner")
        mentor = get_agent("mentor")

        # 初始状态：都只有 system 消息
        assert len(reasoner.messages) == 1
        assert len(mentor.messages) == 1
        assert reasoner.messages[0]["role"] == "system"
        assert mentor.messages[0]["role"] == "system"

        # 系统提示应不同
        assert reasoner.messages[0]["content"] != mentor.messages[0]["content"]

        # 向 reasoner 添加消息，不应影响 mentor
        reasoner.add_message("user", "测试消息给 reasoner")
        assert len(reasoner.messages) == 2
        assert len(mentor.messages) == 1  # mentor 不受影响

        # 向 mentor 添加消息，不应影响 reasoner
        mentor.add_message("user", "测试消息给 mentor")
        assert len(mentor.messages) == 2
        assert len(reasoner.messages) == 2  # reasoner 不受影响

        # 内容应不同
        assert reasoner.messages[1]["content"] == "测试消息给 reasoner"
        assert mentor.messages[1]["content"] == "测试消息给 mentor"

        # 测试结束后重置，避免污染后续测试
        reset_all_contexts()

    def test_all_agents_have_distinct_messages_lists(self):
        """所有 Agent 应有独立的 messages 列表对象"""
        from backend.agents.agent_registry import get_agent

        agents = ["searcher", "reasoner", "critic", "mentor", "writer"]
        messages_ids = set()
        for agent_id in agents:
            agent = get_agent(agent_id)
            # 每个 Agent 的 messages 应是不同的列表对象
            messages_ids.add(id(agent.messages))

        # 应有 5 个不同的列表对象
        assert len(messages_ids) == 5

    def test_reset_all_contexts_clears_all_agents(self):
        """reset_all_contexts 应清空所有 Agent 的上下文"""
        from backend.agents.agent_registry import get_agent, reset_all_contexts

        # 向多个 Agent 添加消息
        for agent_id in ["reasoner", "mentor", "writer"]:
            agent = get_agent(agent_id)
            agent.add_message("user", "测试消息")

        # 重置所有上下文
        reset_all_contexts()

        # 所有 Agent 应只剩 system 消息
        for agent_id in ["reasoner", "mentor", "writer"]:
            agent = get_agent(agent_id)
            assert len(agent.messages) == 1
            assert agent.messages[0]["role"] == "system"


class TestAgentRegistry:
    """Agent 注册表测试"""

    def test_all_agents_registered(self):
        """所有 6 个 Agent 应已注册"""
        from backend.agents.agent_registry import AGENT_REGISTRY

        expected_ids = {"searcher", "reasoner", "critic", "mentor", "writer", "orchestrator"}
        assert expected_ids.issubset(set(AGENT_REGISTRY.keys()))

    def test_get_agent_returns_instances(self):
        """get_agent 应返回 Agent 实例"""
        from backend.agents.agent_registry import get_agent
        from backend.agents.base_agent import BaseAgent

        for agent_id in ["searcher", "reasoner", "critic", "mentor", "writer", "orchestrator"]:
            agent = get_agent(agent_id)
            assert isinstance(agent, BaseAgent)
            assert agent.agent_id == agent_id

    def test_get_agent_singleton(self):
        """get_agent 应返回单例"""
        from backend.agents.agent_registry import get_agent

        agent1 = get_agent("reasoner")
        agent2 = get_agent("reasoner")
        assert agent1 is agent2

    def test_get_agent_raises_for_unknown(self):
        """获取未注册的 Agent 应抛出 ValueError"""
        from backend.agents.agent_registry import get_agent

        with pytest.raises(ValueError, match="未注册"):
            get_agent("nonexistent_agent")

    def test_list_agents_returns_metadata(self):
        """list_agents 应返回元数据列表"""
        from backend.agents.agent_registry import list_agents

        metadata_list = list_agents()
        assert isinstance(metadata_list, list)
        assert len(metadata_list) >= 6

        # 每项应包含必要字段
        for meta in metadata_list:
            assert "id" in meta
            assert "name" in meta

    def test_agent_metadata_complete(self):
        """每个 Agent 的元数据应完整"""
        from backend.agents.agent_registry import list_agents

        metadata_list = list_agents()
        for meta in metadata_list:
            assert "id" in meta
            assert "name" in meta
            assert "description" in meta
            assert "default_model" in meta
            assert "capabilities" in meta


class TestSubAgents:
    """子 Agent 基础测试"""

    def test_searcher_agent_uses_search_model(self):
        """SearcherAgent 应使用 search 步骤的模型"""
        from backend.agents.searcher_wrapper import SearcherAgent
        from backend.config import get_step_model

        agent = SearcherAgent()
        assert agent.model_id == get_step_model("search")

    def test_reasoner_agent_uses_reasoner_model(self):
        """ReasonerAgent 应使用 reasoner 步骤的模型"""
        from backend.agents.reasoner import ReasonerAgent
        from backend.config import get_step_model

        agent = ReasonerAgent()
        assert agent.model_id == get_step_model("reasoner")

    def test_critic_agent_uses_reasoner_model(self):
        """CriticAgent 应复用 reasoner 模型"""
        from backend.agents.critic import CriticAgent
        from backend.config import get_step_model

        agent = CriticAgent()
        assert agent.model_id == get_step_model("reasoner")

    def test_mentor_agent_uses_mentor_model(self):
        """MentorAgent 应使用 mentor 步骤的模型"""
        from backend.agents.mentor_agent import MentorAgent
        from backend.config import get_step_model

        agent = MentorAgent()
        assert agent.model_id == get_step_model("mentor")

    def test_writer_agent_uses_report_model(self):
        """WriterAgent 应使用 report 步骤的模型"""
        from backend.agents.proposal_writer import WriterAgent
        from backend.config import get_step_model

        agent = WriterAgent()
        assert agent.model_id == get_step_model("report")

    def test_orchestrator_agent_uses_orchestrator_model(self):
        """OrchestratorAgent 应使用 orchestrator 步骤的模型"""
        from backend.agents.orchestrator import OrchestratorAgent
        from backend.config import get_step_model

        agent = OrchestratorAgent()
        assert agent.model_id == get_step_model("orchestrator")

    @pytest.mark.asyncio
    async def test_reasoner_run_returns_agent_result(self):
        """ReasonerAgent.run() 应返回 AgentResult"""
        from backend.agents.base_agent import AgentResult
        from backend.agents.reasoner import ReasonerAgent

        # Mock call_llm 返回候选 JSON
        mock_content = json.dumps({
            "candidates": [
                {"title": "测试论题", "dimension": "cross_discipline", "rationale": "测试理由"}
            ]
        })

        async def mock_call_llm(**kwargs):
            return _make_llm_result(mock_content)

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            agent = ReasonerAgent()
            agent.reset_context()
            result = await agent.run({
                "discipline": "计算机科学",
                "degree": "master",
                "search_feeds": [],
            })

        assert isinstance(result, AgentResult)
        assert result.agent_id == "reasoner"
        assert "candidates" in result.data
        assert len(result.data["candidates"]) > 0

    @pytest.mark.asyncio
    async def test_critic_run_returns_agent_result(self):
        """CriticAgent.run() 应返回 AgentResult"""
        from backend.agents.base_agent import AgentResult
        from backend.agents.critic import CriticAgent

        mock_content = json.dumps({
            "evaluations": [
                {
                    "title": "测试论题",
                    "score": 75,
                    "novelty": 70,
                    "feasibility": 80,
                    "issues": [],
                    "suggestions": [],
                }
            ]
        })

        async def mock_call_llm(**kwargs):
            return _make_llm_result(mock_content)

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            agent = CriticAgent()
            agent.reset_context()
            result = await agent.run({
                "candidates": [{"title": "测试论题", "dimension": "cross_discipline", "rationale": "理由"}],
                "search_feeds": [],
            })

        assert isinstance(result, AgentResult)
        assert result.agent_id == "critic"
        assert "evaluations" in result.data

    @pytest.mark.asyncio
    async def test_mentor_run_returns_agent_result(self):
        """MentorAgent.run() 应返回 AgentResult"""
        from backend.agents.base_agent import AgentResult
        from backend.agents.mentor_agent import MentorAgent

        mock_content = json.dumps({
            "advice": "论题方向可行，建议深化",
            "direction": "approve",
            "score": 80,
            "reason": "方向契合导师研究",
        })

        async def mock_call_llm(**kwargs):
            return _make_llm_result(mock_content)

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            agent = MentorAgent()
            agent.reset_context()
            result = await agent.run({
                "topic": "测试论题",
                "context": {"degree": "master", "discipline": "计算机科学"},
            })

        assert isinstance(result, AgentResult)
        assert result.agent_id == "mentor"
        assert result.data["direction"] == "approve"
        assert "advice" in result.data

    @pytest.mark.asyncio
    async def test_writer_run_returns_agent_result(self):
        """WriterAgent.run() 应返回 AgentResult"""
        from backend.agents.base_agent import AgentResult
        from backend.agents.proposal_writer import WriterAgent

        mock_content = "# 开题报告大纲\n## 一、选题依据\n测试内容"

        async def mock_call_llm(**kwargs):
            return _make_llm_result(mock_content)

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            agent = WriterAgent()
            agent.reset_context()
            result = await agent.run({
                "topic": "测试论题",
                "granularity": "outline",
                "context": {},
            })

        assert isinstance(result, AgentResult)
        assert result.agent_id == "writer"
        assert result.data["granularity"] == "outline"
        assert result.data["word_count"] > 0
        assert "content" in result.data

    @pytest.mark.asyncio
    async def test_searcher_run_returns_agent_result(self):
        """SearcherAgent.run() 应返回 AgentResult"""
        from backend.agents.base_agent import AgentResult
        from backend.agents.searcher_wrapper import SearcherAgent

        mock_content = json.dumps({
            "summary": "检索到5篇文献",
            "key_findings": ["发现1"],
        })

        async def mock_call_llm(**kwargs):
            return _make_llm_result(mock_content)

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            agent = SearcherAgent()
            agent.reset_context()
            result = await agent.run({
                "query": "深度学习",
                "years": 2,
            })

        assert isinstance(result, AgentResult)
        assert result.agent_id == "searcher"
        assert "papers" in result.data
        assert "citations" in result.data


class TestBackwardCompatibility:
    """v7 既有功能兼容性测试"""

    def test_search_literature_function_still_works(self):
        """既有 search_literature 函数应保持可用"""
        from backend.agents.searcher_wrapper import search_literature

        papers = search_literature("测试", count=3)
        assert isinstance(papers, list)
        assert len(papers) == 3
        assert "title" in papers[0]

    def test_check_novelty_function_still_works(self):
        """既有 check_novelty 函数应保持可用"""
        from backend.agents.searcher_wrapper import check_novelty

        result = check_novelty("测试标题", ["测试标题已存在"])
        assert "novelty_score" in result
        assert "assessment" in result

    def test_get_searcher_factory_still_works(self):
        """既有 get_searcher 工厂函数应保持可用"""
        from backend.agents.searcher_wrapper import get_searcher, MockSearcher

        searcher = get_searcher()
        # 默认应返回 MockSearcher（除非配置了真实检索）
        assert searcher is not None

    def test_mentor_review_proposal_function_exists(self):
        """既有 review_proposal 函数应保持可用"""
        from backend.agents.mentor_agent import review_proposal, fallback_review

        # fallback_review 不依赖 API，可直接测试
        result = fallback_review({"confidence_score": 0.8})
        assert "score" in result
        assert "comments" in result
        assert "suggestions" in result
        assert "approve" in result

    def test_proposal_writer_template_still_works(self):
        """既有 _generate_with_template 函数应保持可用"""
        from backend.agents.proposal_writer import _generate_with_template

        proposal = {
            "title": "测试论题",
            "problem_awareness": "问题意识",
            "inspiration_source": "灵感来源",
            "research_significance": {"theoretical": "理论", "practical": "实践"},
            "literature_review_outline": "综述",
            "differentiation": "创新点",
            "research_content": ["内容1", "内容2"],
            "feasibility_analysis": "可行",
            "confidence_score": 0.7,
        }
        report = _generate_with_template(proposal, "master", "计算机", "张老师")
        assert isinstance(report, str)
        assert "测试论题" in report
        assert "开题报告" in report

    def test_reasoner_proposal_module_importable(self):
        """v7 reasoner_proposal 模块应保持可导入"""
        from backend.agents import reasoner_proposal

        assert hasattr(reasoner_proposal, "generate_proposal")
        assert hasattr(reasoner_proposal, "fallback_proposal")
