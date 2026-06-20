"""集成测试：多 Agent 协作验证

覆盖：
- Orchestrator 调用所有5个子 Agent
- Agent 之间的上下文隔离
- Agent 注册表
- Agent 结果聚合
- Mock AI 调用

运行方式：python -m pytest tests/integration/test_multi_agent_collaboration.py -v
"""
import asyncio
import os
import sys
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 切换到临时数据库
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_multi_agent_")
_tmp_db = os.path.join(_tmp_dir, "test_multi_agent.db")
_db.DB_PATH = _tmp_db
_db.init_db()

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.agents.agent_registry import (
    AGENT_REGISTRY,
    _AGENT_INSTANCES,
    get_agent,
    list_agents,
    register_agent,
    reset_all_contexts,
)
from backend.agents.orchestrator import OrchestratorAgent
from backend.agents.reasoner import ReasonerAgent, FOUR_DIMENSIONS
from backend.agents.critic import CriticAgent, SCORE_THRESHOLD
from backend.agents.searcher_wrapper import SearcherAgent, check_novelty, search_literature
from backend.agents.mentor_agent import MentorAgent
from backend.agents.proposal_writer import WriterAgent, GRANULARITIES


# ===== 辅助函数 =====

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


# ===== Agent 注册表测试 =====

class TestAgentRegistry:
    """Agent 注册表测试"""

    def test_all_agents_registered(self):
        """所有6个 Agent 应已注册"""
        expected_agents = {"searcher", "reasoner", "critic", "mentor", "writer", "orchestrator"}
        registered = set(AGENT_REGISTRY.keys())
        assert expected_agents.issubset(registered)

    def test_get_agent_returns_instance(self):
        """get_agent 应返回 Agent 实例"""
        agent = get_agent("orchestrator")
        assert agent is not None
        assert isinstance(agent, OrchestratorAgent)
        assert agent.agent_id == "orchestrator"

    def test_get_agent_returns_singleton(self):
        """get_agent 应返回单例"""
        agent1 = get_agent("reasoner")
        agent2 = get_agent("reasoner")
        assert agent1 is agent2

    def test_get_agent_raises_for_unknown(self):
        """获取未注册的 Agent 应抛出 ValueError"""
        with pytest.raises(ValueError, match="未注册"):
            get_agent("nonexistent_agent")

    def test_list_agents_returns_metadata(self):
        """list_agents 应返回元数据列表"""
        agents = list_agents()
        assert isinstance(agents, list)
        assert len(agents) >= 6
        for agent_meta in agents:
            assert "id" in agent_meta
            assert "name" in agent_meta
            assert "description" in agent_meta

    def test_list_agents_contains_all_ids(self):
        """list_agents 应包含所有 Agent ID"""
        agents = list_agents()
        ids = [a["id"] for a in agents]
        for expected_id in ["searcher", "reasoner", "critic", "mentor", "writer", "orchestrator"]:
            assert expected_id in ids

    def test_register_custom_agent(self):
        """应能注册自定义 Agent"""

        class CustomAgent(BaseAgent):
            async def run(self, task_input: dict) -> AgentResult:
                return AgentResult(agent_id=self.agent_id, success=True, content="custom")

        register_agent("custom_test_agent", CustomAgent)
        assert "custom_test_agent" in AGENT_REGISTRY
        agent = get_agent("custom_test_agent")
        assert isinstance(agent, CustomAgent)

        # 清理
        AGENT_REGISTRY.pop("custom_test_agent", None)
        _AGENT_INSTANCES.pop("custom_test_agent", None)

    def test_reset_all_contexts(self):
        """reset_all_contexts 应重置所有 Agent 上下文"""
        # 先添加一些消息
        agent = get_agent("reasoner")
        original_len = len(agent.messages)
        agent.add_message("user", "测试消息")
        assert len(agent.messages) == original_len + 1

        # 重置
        reset_all_contexts()
        assert len(agent.messages) == 1  # 仅剩系统提示


# ===== 各 Agent 元数据测试 =====

class TestAgentMetadata:
    """各 Agent 元数据测试"""

    def test_searcher_metadata(self):
        """SearcherAgent 元数据"""
        agent = get_agent("searcher")
        meta = agent.get_metadata()
        assert meta["id"] == "searcher"
        assert meta["name"] == "Searcher"
        assert "检索" in meta["description"] or "search" in meta["description"].lower()

    def test_reasoner_metadata(self):
        """ReasonerAgent 元数据"""
        agent = get_agent("reasoner")
        meta = agent.get_metadata()
        assert meta["id"] == "reasoner"
        assert meta["name"] == "Reasoner"
        assert "创意" in meta["description"] or "creative" in meta["description"].lower()

    def test_critic_metadata(self):
        """CriticAgent 元数据"""
        agent = get_agent("critic")
        meta = agent.get_metadata()
        assert meta["id"] == "critic"
        assert meta["name"] == "Critic"
        assert "评估" in meta["description"] or "evaluat" in meta["description"].lower()

    def test_mentor_metadata(self):
        """MentorAgent 元数据"""
        agent = get_agent("mentor")
        meta = agent.get_metadata()
        assert meta["id"] == "mentor"
        assert meta["name"] == "Mentor"

    def test_writer_metadata(self):
        """WriterAgent 元数据"""
        agent = get_agent("writer")
        meta = agent.get_metadata()
        assert meta["id"] == "writer"
        assert meta["name"] == "Writer"
        assert "生成" in meta["description"] or "generat" in meta["description"].lower()

    def test_orchestrator_metadata(self):
        """OrchestratorAgent 元数据"""
        agent = get_agent("orchestrator")
        meta = agent.get_metadata()
        assert meta["id"] == "orchestrator"
        assert meta["name"] == "Orchestrator"
        assert "调度" in meta["description"] or "orchestrat" in meta["description"].lower()

    def test_all_agents_have_capabilities(self):
        """所有 Agent 应有 capabilities 列表"""
        for agent_id in ["searcher", "reasoner", "critic", "mentor", "writer", "orchestrator"]:
            agent = get_agent(agent_id)
            meta = agent.get_metadata()
            assert isinstance(meta["capabilities"], list)


# ===== Agent 上下文隔离测试 =====

class TestAgentContextIsolation:
    """Agent 上下文隔离测试"""

    def test_each_agent_has_independent_context(self):
        """每个 Agent 应有独立的上下文"""
        reasoner = get_agent("reasoner")
        critic = get_agent("critic")

        # 初始状态：都只有系统提示
        assert len(reasoner.messages) == 1
        assert len(critic.messages) == 1

        # 在 reasoner 中添加消息
        reasoner.add_message("user", "给 reasoner 的消息")
        assert len(reasoner.messages) == 2
        assert len(critic.messages) == 1  # critic 不受影响

    def test_context_isolation_after_multiple_messages(self):
        """多条消息后上下文仍应隔离"""
        reasoner = get_agent("reasoner")
        writer = get_agent("writer")
        mentor = get_agent("mentor")

        reset_all_contexts()

        reasoner.add_message("user", "消息1")
        reasoner.add_message("assistant", "回复1")
        writer.add_message("user", "消息2")
        mentor.add_message("user", "消息3")

        assert len(reasoner.messages) == 3  # system + 2
        assert len(writer.messages) == 2  # system + 1
        assert len(mentor.messages) == 2  # system + 1

    def test_reset_context_keeps_system_prompt(self):
        """reset_context 应保留系统提示"""
        agent = get_agent("reasoner")
        original_system = agent.messages[0]["content"]

        agent.add_message("user", "测试")
        agent.add_message("assistant", "回复")
        assert len(agent.messages) == 3

        agent.reset_context()
        assert len(agent.messages) == 1
        assert agent.messages[0]["content"] == original_system

    def test_get_context_returns_copy(self):
        """get_context 应返回副本"""
        agent = get_agent("reasoner")
        agent.reset_context()

        context = agent.get_context()
        original_len = len(context)

        # 修改副本不应影响原始上下文
        context.append({"role": "user", "content": "外部修改"})
        assert len(agent.messages) == original_len

    def test_different_agents_have_different_system_prompts(self):
        """不同 Agent 应有不同的系统提示"""
        reasoner = get_agent("reasoner")
        critic = get_agent("critic")
        writer = get_agent("writer")

        assert reasoner.system_prompt != critic.system_prompt
        assert reasoner.system_prompt != writer.system_prompt
        assert critic.system_prompt != writer.system_prompt


# ===== Agent 结果聚合测试 =====

class TestAgentResultAggregation:
    """Agent 结果聚合测试"""

    def test_agent_result_dataclass(self):
        """AgentResult 数据类应有正确字段"""
        result = AgentResult(
            agent_id="test",
            success=True,
            content="测试内容",
            reasoning="推理过程",
            data={"key": "value"},
            citations=[{"url": "https://example.com"}],
            token_usage={"total_tokens": 100},
        )
        assert result.agent_id == "test"
        assert result.success is True
        assert result.content == "测试内容"
        assert result.data == {"key": "value"}
        assert len(result.citations) == 1
        assert result.token_usage["total_tokens"] == 100

    def test_agent_result_default_values(self):
        """AgentResult 应有正确的默认值"""
        result = AgentResult(agent_id="test", success=True)
        assert result.content == ""
        assert result.reasoning == ""
        assert result.data == {}
        assert result.citations == []
        assert result.token_usage == {}
        assert result.error == ""

    @pytest.mark.asyncio
    async def test_orchestrator_aggregates_results(self):
        """Orchestrator 应聚合各阶段结果"""
        orchestrator = OrchestratorAgent()

        def _mock_searcher_result():
            return AgentResult(
                agent_id="searcher", success=True,
                content="检索完成", data={"papers": [{"title": "p1"}]},
            )

        def _mock_reasoner_result():
            return AgentResult(
                agent_id="reasoner", success=True,
                content="生成候选", data={"candidates": [{"title": "t1"}]},
            )

        def _mock_critic_result():
            return AgentResult(
                agent_id="critic", success=True,
                content="评估完成", data={"evaluations": [{"score": 80}]},
            )

        def _mock_writer_result():
            return AgentResult(
                agent_id="writer", success=True,
                content="生成完成", data={"content": "报告内容"},
            )

        with patch("backend.agents.agent_registry.get_agent") as mock_get_agent:
            class MockSearcher:
                async def run(self, task_input):
                    return _mock_searcher_result()

            class MockReasoner:
                async def run(self, task_input):
                    return _mock_reasoner_result()

            class MockCritic:
                async def run(self, task_input):
                    return _mock_critic_result()

            class MockWriter:
                async def run(self, task_input):
                    return _mock_writer_result()

            def get_agent_side_effect(agent_id):
                return {
                    "searcher": MockSearcher(),
                    "reasoner": MockReasoner(),
                    "critic": MockCritic(),
                    "writer": MockWriter(),
                }.get(agent_id)

            mock_get_agent.side_effect = get_agent_side_effect

            result = await orchestrator.run({"user_input": "测试"})

            assert result.success is True
            assert "stages" in result.data
            stages = result.data["stages"]
            assert len(stages) > 0

            # 验证 stage_results 缓存
            assert "info_confirm" in orchestrator.stage_results
            assert "creativity" in orchestrator.stage_results
            assert "validation" in orchestrator.stage_results
            assert "generation" in orchestrator.stage_results


# ===== 四维创意引擎测试 =====

class TestFourDimensions:
    """四维创意引擎测试"""

    def test_four_dimensions_defined(self):
        """应定义4个维度"""
        assert len(FOUR_DIMENSIONS) == 4

    def test_dimension_ids(self):
        """维度 ID 应正确"""
        ids = [d["id"] for d in FOUR_DIMENSIONS]
        assert "cross_discipline" in ids
        assert "method_transfer" in ids
        assert "pain_point_breakthrough" in ids
        assert "trend_forecast" in ids

    def test_dimension_has_name_and_description(self):
        """每个维度应有名称和描述"""
        for dim in FOUR_DIMENSIONS:
            assert "id" in dim
            assert "name" in dim
            assert "description" in dim
            assert len(dim["name"]) > 0
            assert len(dim["description"]) > 0


# ===== 评分阈值测试 =====

class TestScoreThreshold:
    """评分阈值测试"""

    def test_score_threshold_is_60(self):
        """评分阈值应为60"""
        assert SCORE_THRESHOLD == 60

    @pytest.mark.asyncio
    async def test_score_below_threshold_triggers_retry(self):
        """评分低于阈值应触发回退"""
        orchestrator = OrchestratorAgent()

        with patch("backend.agents.agent_registry.get_agent") as mock_get_agent:
            class MockSearcher:
                async def run(self, task_input):
                    return AgentResult(
                        agent_id="searcher", success=True,
                        data={"papers": []},
                    )

            class MockReasoner:
                async def run(self, task_input):
                    return AgentResult(
                        agent_id="reasoner", success=True,
                        data={"candidates": [{"title": "t1"}, {"title": "t2"}, {"title": "t3"}]},
                    )

            class MockCritic:
                async def run(self, task_input):
                    return AgentResult(
                        agent_id="critic", success=True,
                        data={"evaluations": [{"score": 40}, {"score": 50}]},
                    )

            def get_agent_side_effect(agent_id):
                return {
                    "searcher": MockSearcher(),
                    "reasoner": MockReasoner(),
                    "critic": MockCritic(),
                }.get(agent_id)

            mock_get_agent.side_effect = get_agent_side_effect

            chunks = []
            async for chunk in orchestrator.orchestrate("测试", conversation_id=""):
                chunks.append(chunk)

            retry_chunks = [c for c in chunks if c.get("status") == "retry"]
            assert len(retry_chunks) > 0
            assert orchestrator.current_stage == "creativity"


# ===== 生成粒度测试 =====

class TestGranularities:
    """生成粒度测试"""

    def test_granularities_defined(self):
        """应定义4种生成粒度"""
        assert len(GRANULARITIES) == 4

    def test_granularity_values(self):
        """粒度值应正确"""
        assert "title" in GRANULARITIES
        assert "abstract" in GRANULARITIES
        assert "outline" in GRANULARITIES
        assert "full" in GRANULARITIES


# ===== 新颖性检查测试 =====

class TestNoveltyCheck:
    """新颖性检查测试"""

    def test_check_novelty_high_innovation(self):
        """低相似度应为高创新"""
        result = check_novelty("全新的研究标题", ["完全不同的标题"])
        assert result["novelty_score"] < 0.4
        assert result["assessment"] == "高创新"

    def test_check_novelty_warning(self):
        """高相似度应为预警"""
        result = check_novelty("基于图神经网络的代码漏洞检测", ["基于图神经网络的代码漏洞检测"])
        assert result["novelty_score"] > 0.85
        assert result["assessment"] == "预警"

    def test_check_novelty_similar_titles_tracked(self):
        """相似标题应被追踪"""
        result = check_novelty(
            "基于图神经网络的代码漏洞检测方法",
            ["基于图神经网络的代码漏洞检测", "其他不相关标题"],
        )
        assert isinstance(result["similar_titles"], list)

    def test_search_literature_returns_list(self):
        """search_literature 应返回列表"""
        papers = search_literature("测试", count=3)
        assert isinstance(papers, list)
        assert len(papers) == 3
        for paper in papers:
            assert "title" in paper
            assert "authors" in paper
            assert "year" in paper


# ===== Orchestrator 调用所有子 Agent 测试 =====

class TestOrchestratorCallsAllAgents:
    """Orchestrator 调用所有子 Agent 测试"""

    @pytest.mark.asyncio
    async def test_orchestrator_calls_searcher(self):
        """Orchestrator 应调用 searcher"""
        orchestrator = OrchestratorAgent()
        call_log = []

        with patch("backend.agents.agent_registry.get_agent") as mock_get_agent:
            class MockSearcher:
                async def run(self, task_input):
                    call_log.append("searcher")
                    return AgentResult(agent_id="searcher", success=True, data={"papers": []})

            class MockReasoner:
                async def run(self, task_input):
                    call_log.append("reasoner")
                    return AgentResult(agent_id="reasoner", success=True,
                                       data={"candidates": [{"title": "t1"}, {"title": "t2"}, {"title": "t3"}]})

            class MockCritic:
                async def run(self, task_input):
                    call_log.append("critic")
                    return AgentResult(agent_id="critic", success=True,
                                       data={"evaluations": [{"score": 80, "title": "t1"}]})

            class MockWriter:
                async def run(self, task_input):
                    call_log.append("writer")
                    return AgentResult(agent_id="writer", success=True, data={"content": "报告"})

            def get_agent_side_effect(agent_id):
                return {
                    "searcher": MockSearcher(),
                    "reasoner": MockReasoner(),
                    "critic": MockCritic(),
                    "writer": MockWriter(),
                }.get(agent_id)

            mock_get_agent.side_effect = get_agent_side_effect

            async for _ in orchestrator.orchestrate("测试", conversation_id=""):
                pass

            assert "searcher" in call_log
            assert "reasoner" in call_log
            assert "critic" in call_log
            assert "writer" in call_log

    @pytest.mark.asyncio
    async def test_orchestrator_agent_call_order(self):
        """Orchestrator 应按顺序调用 Agent"""
        orchestrator = OrchestratorAgent()
        call_order = []

        with patch("backend.agents.agent_registry.get_agent") as mock_get_agent:
            class MockSearcher:
                async def run(self, task_input):
                    call_order.append("searcher")
                    return AgentResult(agent_id="searcher", success=True, data={"papers": []})

            class MockReasoner:
                async def run(self, task_input):
                    call_order.append("reasoner")
                    return AgentResult(agent_id="reasoner", success=True,
                                       data={"candidates": [{"title": "t1"}, {"title": "t2"}, {"title": "t3"}]})

            class MockCritic:
                async def run(self, task_input):
                    call_order.append("critic")
                    return AgentResult(agent_id="critic", success=True,
                                       data={"evaluations": [{"score": 80, "title": "t1"}]})

            class MockWriter:
                async def run(self, task_input):
                    call_order.append("writer")
                    return AgentResult(agent_id="writer", success=True, data={"content": "报告"})

            def get_agent_side_effect(agent_id):
                return {
                    "searcher": MockSearcher(),
                    "reasoner": MockReasoner(),
                    "critic": MockCritic(),
                    "writer": MockWriter(),
                }.get(agent_id)

            mock_get_agent.side_effect = get_agent_side_effect

            async for _ in orchestrator.orchestrate("测试", conversation_id=""):
                pass

            # 验证调用顺序
            assert call_order.index("searcher") < call_order.index("reasoner")
            assert call_order.index("reasoner") < call_order.index("critic")
            assert call_order.index("critic") < call_order.index("writer")


# ===== Agent 能力测试 =====

class TestAgentCapabilities:
    """Agent 能力测试"""

    def test_orchestrator_capabilities(self):
        """Orchestrator 应有 streaming, thinking, web_search 能力"""
        agent = get_agent("orchestrator")
        assert "streaming" in agent.capabilities
        assert "thinking" in agent.capabilities
        assert "web_search" in agent.capabilities

    def test_reasoner_has_thinking(self):
        """Reasoner 应有 thinking 能力"""
        agent = get_agent("reasoner")
        assert "thinking" in agent.capabilities

    def test_critic_has_thinking(self):
        """Critic 应有 thinking 能力"""
        agent = get_agent("critic")
        assert "thinking" in agent.capabilities

    def test_all_agents_have_model_id(self):
        """所有 Agent 应有 model_id"""
        for agent_id in ["searcher", "reasoner", "critic", "mentor", "writer", "orchestrator"]:
            agent = get_agent(agent_id)
            assert hasattr(agent, "model_id")
            assert isinstance(agent.model_id, str)

    def test_all_agents_have_temperature(self):
        """所有 Agent 应有 temperature"""
        for agent_id in ["searcher", "reasoner", "critic", "mentor", "writer", "orchestrator"]:
            agent = get_agent(agent_id)
            assert hasattr(agent, "temperature")
            assert 0 <= agent.temperature <= 2
