"""base_agent 模块单元测试

测试 backend/agents/base_agent.py 的 BaseAgent 抽象基类与 AgentResult 数据类：
  - AgentResult 默认值与字段赋值
  - BaseAgent 初始化与属性
  - 上下文管理（reset_context / add_message / get_context）
  - get_metadata 元数据返回
  - 抽象方法 run 的约束
  - 独立上下文隔离验证
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
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_base_agent_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.agents.base_agent import AgentResult, BaseAgent


# ===== 测试用具体 Agent 实现 =====


class MockAgent(BaseAgent):
    """用于测试的具体 Agent 实现"""

    def __init__(self, **kwargs):
        super().__init__(
            agent_id=kwargs.get("agent_id", "mock-agent"),
            name=kwargs.get("name", "Mock Agent"),
            description=kwargs.get("description", "测试用 Agent"),
            system_prompt=kwargs.get("system_prompt", "你是测试 Agent"),
            model_id=kwargs.get("model_id", "test-model"),
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 4096),
            capabilities=kwargs.get("capabilities", ["thinking"]),
        )

    async def run(self, task_input: dict) -> AgentResult:
        """模拟 run 方法"""
        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            content=f"处理了: {task_input.get('query', '')}",
            data={"input": task_input},
        )


class AnotherMockAgent(BaseAgent):
    """另一个用于测试的 Agent 实现"""

    def __init__(self):
        super().__init__(
            agent_id="another-agent",
            name="Another Agent",
            description="另一个测试 Agent",
            system_prompt="你是另一个测试 Agent",
            model_id="another-model",
        )

    async def run(self, task_input: dict) -> AgentResult:
        return AgentResult(agent_id=self.agent_id, success=True)


# ===== AgentResult 数据类测试 =====


class TestAgentResult:
    """AgentResult 数据类测试"""

    def test_agent_result_default_values(self):
        """测试：AgentResult 默认值"""
        result = AgentResult(agent_id="test", success=True)
        assert result.agent_id == "test"
        assert result.success is True
        assert result.content == ""
        assert result.reasoning == ""
        assert result.data == {}
        assert result.citations == []
        assert result.token_usage == {}
        assert result.error == ""

    def test_agent_result_with_all_fields(self):
        """测试：AgentResult 设置所有字段"""
        result = AgentResult(
            agent_id="reasoner",
            success=True,
            content="生成的内容",
            reasoning="思维链过程",
            data={"candidates": ["论题1", "论题2"]},
            citations=[{"url": "https://example.com"}],
            token_usage={"prompt_tokens": 100, "completion_tokens": 50},
            error="",
        )
        assert result.agent_id == "reasoner"
        assert result.success is True
        assert result.content == "生成的内容"
        assert result.reasoning == "思维链过程"
        assert result.data["candidates"] == ["论题1", "论题2"]
        assert len(result.citations) == 1
        assert result.token_usage["prompt_tokens"] == 100
        assert result.error == ""

    def test_agent_result_failure_with_error(self):
        """测试：失败的 AgentResult 包含错误信息"""
        result = AgentResult(
            agent_id="critic",
            success=False,
            error="LLM 调用超时",
        )
        assert result.success is False
        assert result.error == "LLM 调用超时"

    def test_agent_result_data_default_is_empty_dict(self):
        """测试：data 默认为独立空字典"""
        r1 = AgentResult(agent_id="a", success=True)
        r2 = AgentResult(agent_id="b", success=True)
        r1.data["key"] = "value"
        # r2 的 data 不应受影响（default_factory 独立实例）
        assert r2.data == {}

    def test_agent_result_citations_default_is_empty_list(self):
        """测试：citations 默认为独立空列表"""
        r1 = AgentResult(agent_id="a", success=True)
        r2 = AgentResult(agent_id="b", success=True)
        r1.citations.append({"url": "https://a.com"})
        assert r2.citations == []

    def test_agent_result_token_usage_default_is_empty_dict(self):
        """测试：token_usage 默认为独立空字典"""
        r1 = AgentResult(agent_id="a", success=True)
        r2 = AgentResult(agent_id="b", success=True)
        r1.token_usage["total"] = 100
        assert r2.token_usage == {}


# ===== BaseAgent 初始化测试 =====


class TestBaseAgentInit:
    """BaseAgent 初始化与属性测试"""

    def test_agent_init_with_required_fields(self):
        """测试：使用必需字段初始化 Agent"""
        agent = MockAgent(
            agent_id="test-1",
            name="测试Agent",
            description="测试描述",
            system_prompt="系统提示",
        )
        assert agent.agent_id == "test-1"
        assert agent.name == "测试Agent"
        assert agent.description == "测试描述"
        assert agent.system_prompt == "系统提示"

    def test_agent_init_with_optional_fields(self):
        """测试：可选字段默认值"""
        agent = MockAgent()
        assert agent.model_id == "test-model"
        assert agent.temperature == 0.7
        assert agent.max_tokens == 4096
        assert agent.capabilities == ["thinking"]

    def test_agent_init_custom_model_id(self):
        """测试：自定义 model_id"""
        agent = MockAgent(model_id="deepseek-r2")
        assert agent.model_id == "deepseek-r2"

    def test_agent_init_custom_temperature(self):
        """测试：自定义 temperature"""
        agent = MockAgent(temperature=0.2)
        assert agent.temperature == 0.2

    def test_agent_init_custom_max_tokens(self):
        """测试：自定义 max_tokens"""
        agent = MockAgent(max_tokens=8192)
        assert agent.max_tokens == 8192

    def test_agent_init_custom_capabilities(self):
        """测试：自定义 capabilities"""
        caps = ["streaming", "thinking", "web_search"]
        agent = MockAgent(capabilities=caps)
        assert agent.capabilities == caps

    def test_agent_init_capabilities_default_empty(self):
        """测试：capabilities 默认为空列表"""
        agent = MockAgent(capabilities=None)
        assert agent.capabilities == []

    def test_agent_init_messages_contains_system_prompt(self):
        """测试：初始化后 messages 仅包含系统提示"""
        agent = MockAgent(system_prompt="你是测试Agent")
        assert len(agent.messages) == 1
        assert agent.messages[0]["role"] == "system"
        assert agent.messages[0]["content"] == "你是测试Agent"


# ===== 上下文管理测试 =====


class TestContextManagement:
    """BaseAgent 上下文管理测试"""

    def test_reset_context_clears_history(self):
        """测试：reset_context 清空历史，仅保留系统提示"""
        agent = MockAgent(system_prompt="系统提示")
        agent.add_message("user", "用户消息1")
        agent.add_message("assistant", "回复1")
        assert len(agent.messages) == 3
        agent.reset_context()
        assert len(agent.messages) == 1
        assert agent.messages[0]["role"] == "system"
        assert agent.messages[0]["content"] == "系统提示"

    def test_add_message_user_role(self):
        """测试：添加 user 角色消息"""
        agent = MockAgent()
        agent.add_message("user", "用户输入")
        assert len(agent.messages) == 2
        assert agent.messages[1] == {"role": "user", "content": "用户输入"}

    def test_add_message_assistant_role(self):
        """测试：添加 assistant 角色消息"""
        agent = MockAgent()
        agent.add_message("assistant", "AI回复")
        assert len(agent.messages) == 2
        assert agent.messages[1] == {"role": "assistant", "content": "AI回复"}

    def test_add_multiple_messages(self):
        """测试：添加多条消息"""
        agent = MockAgent()
        for i in range(5):
            agent.add_message("user", f"消息{i}")
            agent.add_message("assistant", f"回复{i}")
        # 1 system + 10 messages = 11
        assert len(agent.messages) == 11

    def test_get_context_returns_copy(self):
        """测试：get_context 返回副本，修改不影响原始"""
        agent = MockAgent()
        agent.add_message("user", "测试")
        context = agent.get_context()
        # 修改副本
        context.append({"role": "user", "content": "注入"})
        # 原始不受影响
        assert len(agent.messages) == 2
        assert agent.messages[-1]["content"] == "测试"

    def test_get_context_preserves_system_prompt(self):
        """测试：get_context 包含系统提示"""
        agent = MockAgent(system_prompt="系统提示")
        context = agent.get_context()
        assert context[0]["role"] == "system"
        assert context[0]["content"] == "系统提示"

    def test_context_isolation_between_agents(self):
        """测试：不同 Agent 实例的上下文相互隔离"""
        agent1 = MockAgent(agent_id="agent-1", system_prompt="Agent1提示")
        agent2 = MockAgent(agent_id="agent-2", system_prompt="Agent2提示")
        agent1.add_message("user", "给Agent1的消息")
        # Agent2 的上下文不应包含 Agent1 的消息
        assert len(agent2.messages) == 1
        assert agent2.messages[0]["content"] == "Agent2提示"
        assert len(agent1.messages) == 2

    def test_reset_context_preserves_system_prompt(self):
        """测试：reset_context 后系统提示不变"""
        agent = MockAgent(system_prompt="不变的系统提示")
        agent.add_message("user", "临时消息")
        agent.reset_context()
        assert agent.messages[0]["content"] == "不变的系统提示"


# ===== get_metadata 测试 =====


class TestGetMetadata:
    """BaseAgent.get_metadata 方法测试"""

    def test_metadata_contains_id(self):
        """测试：元数据包含 agent id"""
        agent = MockAgent(agent_id="test-id")
        meta = agent.get_metadata()
        assert meta["id"] == "test-id"

    def test_metadata_contains_name(self):
        """测试：元数据包含 name"""
        agent = MockAgent(name="测试名称")
        meta = agent.get_metadata()
        assert meta["name"] == "测试名称"

    def test_metadata_contains_description(self):
        """测试：元数据包含 description"""
        agent = MockAgent(description="测试描述")
        meta = agent.get_metadata()
        assert meta["description"] == "测试描述"

    def test_metadata_contains_default_model(self):
        """测试：元数据包含 default_model"""
        agent = MockAgent(model_id="deepseek-r2")
        meta = agent.get_metadata()
        assert meta["default_model"] == "deepseek-r2"

    def test_metadata_contains_capabilities(self):
        """测试：元数据包含 capabilities"""
        caps = ["streaming", "thinking"]
        agent = MockAgent(capabilities=caps)
        meta = agent.get_metadata()
        assert meta["capabilities"] == caps

    def test_metadata_is_dict(self):
        """测试：元数据是字典类型"""
        agent = MockAgent()
        meta = agent.get_metadata()
        assert isinstance(meta, dict)

    def test_metadata_has_all_required_keys(self):
        """测试：元数据包含所有必需键"""
        agent = MockAgent()
        meta = agent.get_metadata()
        required_keys = {"id", "name", "description", "default_model", "capabilities"}
        assert required_keys.issubset(meta.keys())


# ===== run 方法测试 =====


class TestRunMethod:
    """BaseAgent.run 抽象方法测试"""

    def test_run_returns_agent_result(self):
        """测试：run 方法返回 AgentResult"""
        agent = MockAgent()
        result = asyncio.new_event_loop().run_until_complete(
            agent.run({"query": "测试查询"})
        )
        assert isinstance(result, AgentResult)
        assert result.agent_id == "mock-agent"
        assert result.success is True

    def test_run_preserves_agent_id(self):
        """测试：run 返回的 AgentResult 包含正确的 agent_id"""
        agent = MockAgent(agent_id="custom-id")
        result = asyncio.new_event_loop().run_until_complete(agent.run({}))
        assert result.agent_id == "custom-id"

    def test_run_with_empty_input(self):
        """测试：空输入不导致崩溃"""
        agent = MockAgent()
        result = asyncio.new_event_loop().run_until_complete(agent.run({}))
        assert result.success is True

    def test_run_with_complex_input(self):
        """测试：复杂输入正确处理"""
        agent = MockAgent()
        task_input = {
            "query": "机器学习",
            "discipline": "计算机科学",
            "degree": "master",
            "search_feeds": [{"title": "论文1"}, {"title": "论文2"}],
        }
        result = asyncio.new_event_loop().run_until_complete(agent.run(task_input))
        assert result.success is True
        assert result.data["input"] == task_input


# ===== 抽象基类约束测试 =====


class TestAbstractClass:
    """BaseAgent 抽象基类约束测试"""

    def test_cannot_instantiate_base_agent_directly(self):
        """测试：不能直接实例化 BaseAgent 抽象类"""
        with pytest.raises(TypeError):
            BaseAgent(
                agent_id="direct",
                name="Direct",
                description="直接实例化",
                system_prompt="提示",
            )

    def test_subclass_must_implement_run(self):
        """测试：子类必须实现 run 方法"""

        class IncompleteAgent(BaseAgent):
            pass

        with pytest.raises(TypeError):
            IncompleteAgent(
                agent_id="incomplete",
                name="Incomplete",
                description="未实现run",
                system_prompt="提示",
            )
