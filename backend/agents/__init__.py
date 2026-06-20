"""ThesisMiner Agent 模块

v8.0 多 Agent 架构：
    - BaseAgent: 抽象基类，定义 Agent 接口
    - AgentResult: Agent 执行结果
    - agent_registry: 全局注册表
    - SearcherAgent: 文献检索 Agent
    - ReasonerAgent: 四维创意引擎 Agent
    - CriticAgent: 候选论题评估 Agent
    - MentorAgent: 导师视角评审 Agent
    - WriterAgent: 多粒度开题内容生成 Agent
    - OrchestratorAgent: 主管理 Agent，调度五阶段流程
    - ThesisWriterAgent: 论文撰写助手 Agent（v9.0 Task 9）
    - DefenseAgent: 答辩准备助手 Agent（v9.0 Task 10）

导入此包时会自动注册所有子 Agent 到 agent_registry。
"""
from backend.agents.base_agent import AgentResult, BaseAgent
from backend.agents.agent_registry import (
    AGENT_REGISTRY,
    get_agent,
    list_agents,
    register_agent,
    reset_all_contexts,
    restore_all_histories,
)

# 导入子 Agent 类（触发注册）
from backend.agents.searcher_wrapper import SearcherAgent
from backend.agents.reasoner import ReasonerAgent
from backend.agents.critic import CriticAgent
from backend.agents.mentor_agent import MentorAgent
from backend.agents.proposal_writer import WriterAgent
from backend.agents.orchestrator import OrchestratorAgent
from backend.agents.thesis_writer import ThesisWriterAgent
from backend.agents.defense_agent import DefenseAgent

# 保留 v7 既有模块的导出，确保向后兼容
from backend.agents import reasoner_proposal  # noqa: F401


def _register_all_agents() -> None:
    """注册所有子 Agent 到全局注册表

    在包导入时自动调用，确保所有 Agent 可通过 get_agent(agent_id) 获取。
    """
    register_agent("searcher", SearcherAgent)
    register_agent("reasoner", ReasonerAgent)
    register_agent("critic", CriticAgent)
    register_agent("mentor", MentorAgent)
    register_agent("writer", WriterAgent)
    register_agent("orchestrator", OrchestratorAgent)
    register_agent("thesis_writer", ThesisWriterAgent)
    register_agent("defense_agent", DefenseAgent)


# 模块导入时自动注册
_register_all_agents()


__all__ = [
    # 基类与结果
    "BaseAgent",
    "AgentResult",
    # 注册表
    "AGENT_REGISTRY",
    "register_agent",
    "get_agent",
    "list_agents",
    "reset_all_contexts",
    "restore_all_histories",
    # 子 Agent 类
    "SearcherAgent",
    "ReasonerAgent",
    "CriticAgent",
    "MentorAgent",
    "WriterAgent",
    "OrchestratorAgent",
    "ThesisWriterAgent",
    "DefenseAgent",
]
