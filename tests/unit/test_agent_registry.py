"""agent_registry 模块单元测试

测试 backend/agents/agent_registry.py 的全局注册表功能：
  - register_agent 注册 Agent 类
  - get_agent 获取 Agent 单例实例
  - list_agents 列出所有已注册 Agent 元数据
  - reset_all_contexts 重置所有 Agent 上下文
  - 未注册 Agent 的错误处理
  - 单例实例缓存验证
"""
import os
import sys
import tempfile
from unittest.mock import patch

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ===== 临时数据库初始化 =====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_registry_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.agents.agent_registry import (
    AGENT_REGISTRY,
    _AGENT_INSTANCES,
    register_agent,
    get_agent,
    list_agents,
    reset_all_contexts,
)


# ===== 测试用 Agent 实现 =====


class TestAgentA(BaseAgent):
    """测试 Agent A"""

    def __init__(self):
        super().__init__(
            agent_id="test-a",
            name="TestAgentA",
            description="测试Agent A",
            system_prompt="你是Agent A",
            model_id="model-a",
            capabilities=["thinking"],
        )

    async def run(self, task_input: dict) -> AgentResult:
        return AgentResult(agent_id=self.agent_id, success=True)


class TestAgentB(BaseAgent):
    """测试 Agent B"""

    def __init__(self):
        super().__init__(
            agent_id="test-b",
            name="TestAgentB",
            description="测试Agent B",
            system_prompt="你是Agent B",
            model_id="model-b",
            capabilities=["streaming", "thinking"],
        )

    async def run(self, task_input: dict) -> AgentResult:
        return AgentResult(agent_id=self.agent_id, success=True)


class SimpleAgent(BaseAgent):
    """简单测试 Agent"""

    def __init__(self, **kwargs):
        super().__init__(
            agent_id=kwargs.get("agent_id", "simple"),
            name=kwargs.get("name", "Simple"),
            description=kwargs.get("description", "简单Agent"),
            system_prompt=kwargs.get("system_prompt", "简单提示"),
            model_id=kwargs.get("model_id", "simple-model"),
        )

    async def run(self, task_input: dict) -> AgentResult:
        return AgentResult(agent_id=self.agent_id, success=True)


# ===== register_agent 测试 =====


class TestRegisterAgent:
    """register_agent 函数测试"""

    def setup_method(self):
        """每个测试前清空注册表"""
        AGENT_REGISTRY.clear()
        _AGENT_INSTANCES.clear()

    def test_register_single_agent(self):
        """测试：注册单个 Agent"""
        register_agent("test-a", TestAgentA)
        assert "test-a" in AGENT_REGISTRY
        assert AGENT_REGISTRY["test-a"] == TestAgentA

    def test_register_multiple_agents(self):
        """测试：注册多个 Agent"""
        register_agent("test-a", TestAgentA)
        register_agent("test-b", TestAgentB)
        assert len(AGENT_REGISTRY) == 2
        assert AGENT_REGISTRY["test-a"] == TestAgentA
        assert AGENT_REGISTRY["test-b"] == TestAgentB

    def test_register_overwrites_existing(self):
        """测试：重复注册覆盖已有 Agent"""
        register_agent("test-a", TestAgentA)
        register_agent("test-a", TestAgentB)
        assert AGENT_REGISTRY["test-a"] == TestAgentB

    def test_register_does_not_create_instance(self):
        """测试：注册时不创建实例"""
        register_agent("test-a", TestAgentA)
        assert "test-a" not in _AGENT_INSTANCES


# ===== get_agent 测试 =====


class TestGetAgent:
    """get_agent 函数测试"""

    def setup_method(self):
        """每个测试前清空注册表"""
        AGENT_REGISTRY.clear()
        _AGENT_INSTANCES.clear()

    def test_get_registered_agent(self):
        """测试：获取已注册的 Agent 实例"""
        register_agent("test-a", TestAgentA)
        agent = get_agent("test-a")
        assert agent is not None
        assert agent.agent_id == "test-a"
        assert isinstance(agent, TestAgentA)

    def test_get_agent_returns_singleton(self):
        """测试：多次获取返回同一实例（单例）"""
        register_agent("test-a", TestAgentA)
        agent1 = get_agent("test-a")
        agent2 = get_agent("test-a")
        assert agent1 is agent2

    def test_get_agent_caches_instance(self):
        """测试：获取后实例被缓存"""
        register_agent("test-a", TestAgentA)
        get_agent("test-a")
        assert "test-a" in _AGENT_INSTANCES

    def test_get_unregistered_agent_raises_error(self):
        """测试：获取未注册的 Agent 抛出 ValueError"""
        with pytest.raises(ValueError, match="未注册"):
            get_agent("nonexistent-agent")

    def test_get_multiple_different_agents(self):
        """测试：获取多个不同的 Agent"""
        register_agent("test-a", TestAgentA)
        register_agent("test-b", TestAgentB)
        agent_a = get_agent("test-a")
        agent_b = get_agent("test-b")
        assert agent_a is not agent_b
        assert agent_a.agent_id == "test-a"
        assert agent_b.agent_id == "test-b"

    def test_get_agent_is_base_agent_subclass(self):
        """测试：获取的 Agent 是 BaseAgent 子类实例"""
        register_agent("test-a", TestAgentA)
        agent = get_agent("test-a")
        assert isinstance(agent, BaseAgent)


# ===== list_agents 测试 =====


class TestListAgents:
    """list_agents 函数测试"""

    def setup_method(self):
        """每个测试前清空注册表"""
        AGENT_REGISTRY.clear()
        _AGENT_INSTANCES.clear()

    def test_list_empty_registry(self):
        """测试：空注册表返回空列表"""
        result = list_agents()
        assert result == []

    def test_list_single_agent(self):
        """测试：列出单个 Agent 元数据"""
        register_agent("test-a", TestAgentA)
        result = list_agents()
        assert len(result) == 1
        assert result[0]["id"] == "test-a"
        assert result[0]["name"] == "TestAgentA"

    def test_list_multiple_agents(self):
        """测试：列出多个 Agent 元数据"""
        register_agent("test-a", TestAgentA)
        register_agent("test-b", TestAgentB)
        result = list_agents()
        assert len(result) == 2
        ids = [r["id"] for r in result]
        assert "test-a" in ids
        assert "test-b" in ids

    def test_list_metadata_contains_required_keys(self):
        """测试：元数据包含所有必需键"""
        register_agent("test-a", TestAgentA)
        result = list_agents()
        required_keys = {"id", "name", "description", "default_model", "capabilities"}
        assert required_keys.issubset(result[0].keys())

    def test_list_reuses_cached_instances(self):
        """测试：list_agents 复用已缓存的实例"""
        register_agent("test-a", TestAgentA)
        # 先 get_agent 创建缓存实例
        cached_agent = get_agent("test-a")
        # list_agents 应复用该实例
        result = list_agents()
        assert len(result) == 1
        assert result[0]["id"] == "test-a"

    def test_list_agent_capabilities(self):
        """测试：元数据包含 capabilities"""
        register_agent("test-b", TestAgentB)
        result = list_agents()
        assert result[0]["capabilities"] == ["streaming", "thinking"]


# ===== reset_all_contexts 测试 =====


class TestResetAllContexts:
    """reset_all_contexts 函数测试"""

    def setup_method(self):
        """每个测试前清空注册表"""
        AGENT_REGISTRY.clear()
        _AGENT_INSTANCES.clear()

    def test_reset_clears_agent_messages(self):
        """测试：重置后 Agent 上下文仅保留系统提示"""
        register_agent("test-a", TestAgentA)
        agent = get_agent("test-a")
        agent.add_message("user", "临时消息")
        assert len(agent.messages) > 1
        reset_all_contexts()
        assert len(agent.messages) == 1
        assert agent.messages[0]["role"] == "system"

    def test_reset_preserves_system_prompt(self):
        """测试：重置后系统提示保留"""
        register_agent("test-a", TestAgentA)
        agent = get_agent("test-a")
        original_prompt = agent.system_prompt
        reset_all_contexts()
        assert agent.messages[0]["content"] == original_prompt

    def test_reset_multiple_agents(self):
        """测试：同时重置多个 Agent 的上下文"""
        register_agent("test-a", TestAgentA)
        register_agent("test-b", TestAgentB)
        agent_a = get_agent("test-a")
        agent_b = get_agent("test-b")
        agent_a.add_message("user", "消息A")
        agent_b.add_message("user", "消息B")
        reset_all_contexts()
        assert len(agent_a.messages) == 1
        assert len(agent_b.messages) == 1

    def test_reset_with_no_instances(self):
        """测试：无实例时 reset 不报错"""
        reset_all_contexts()  # 不应抛出异常

    def test_reset_does_not_remove_instances(self):
        """测试：重置不删除实例缓存"""
        register_agent("test-a", TestAgentA)
        get_agent("test-a")
        assert "test-a" in _AGENT_INSTANCES
        reset_all_contexts()
        # 实例仍存在
        assert "test-a" in _AGENT_INSTANCES


# ===== 集成测试 =====


class TestRegistryIntegration:
    """注册表集成测试"""

    def setup_method(self):
        """每个测试前清空注册表"""
        AGENT_REGISTRY.clear()
        _AGENT_INSTANCES.clear()

    def test_full_lifecycle(self):
        """测试：注册→获取→使用→重置 完整生命周期"""
        # 1. 注册
        register_agent("simple", SimpleAgent)
        # 2. 获取
        agent = get_agent("simple")
        assert agent.agent_id == "simple"
        # 3. 使用（添加消息）
        agent.add_message("user", "测试消息")
        assert len(agent.messages) == 2
        # 4. 重置
        reset_all_contexts()
        assert len(agent.messages) == 1
        # 5. 再次获取（应返回同一实例）
        agent2 = get_agent("simple")
        assert agent is agent2

    def test_singleton_pattern_across_gets(self):
        """测试：单例模式 - 多次 get_agent 返回同一对象"""
        register_agent("simple", SimpleAgent)
        instances = [get_agent("simple") for _ in range(5)]
        # 所有引用应为同一对象
        assert all(inst is instances[0] for inst in instances)
