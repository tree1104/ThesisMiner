"""Agent 全局注册表

提供 Agent 类的注册、单例实例获取与元数据列举。
所有子 Agent 在 backend/agents/__init__.py 导入时自动注册。
"""
import logging
from typing import Type

from backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# 全局注册表：agent_id -> Agent 类
AGENT_REGISTRY: dict[str, Type[BaseAgent]] = {}
# 单例实例缓存：agent_id -> Agent 实例
_AGENT_INSTANCES: dict[str, BaseAgent] = {}


def register_agent(agent_id: str, agent_class: Type[BaseAgent]):
    """注册 Agent 类

    Args:
        agent_id: Agent 唯一标识。
        agent_class: BaseAgent 子类。
    """
    AGENT_REGISTRY[agent_id] = agent_class


def get_agent(agent_id: str) -> BaseAgent:
    """获取 Agent 实例（单例）

    首次获取时实例化并缓存，后续直接返回缓存实例。

    Args:
        agent_id: Agent 唯一标识。

    Returns:
        Agent 实例。

    Raises:
        ValueError: 当 agent_id 未注册时抛出。
    """
    if agent_id not in AGENT_REGISTRY:
        raise ValueError(f"Agent '{agent_id}' 未注册")
    if agent_id not in _AGENT_INSTANCES:
        _AGENT_INSTANCES[agent_id] = AGENT_REGISTRY[agent_id]()
    return _AGENT_INSTANCES[agent_id]


def list_agents() -> list[dict]:
    """列出所有已注册 Agent 的元数据

    Returns:
        元数据字典列表，每项包含 id / name / description / default_model / capabilities。
    """
    result = []
    for agent_id, agent_class in AGENT_REGISTRY.items():
        # 优先复用已存在的单例实例，避免重复实例化开销
        try:
            instance = _AGENT_INSTANCES.get(agent_id) or agent_class()
            result.append(instance.get_metadata())
        except Exception:
            # 实例化失败时返回最小元数据，确保列表不中断
            result.append({
                "id": agent_id,
                "name": agent_id,
                "description": "",
                "default_model": "",
                "capabilities": [],
            })
    return result


def reset_all_contexts():
    """重置所有 Agent 的上下文（用于新会话）

    仅清空历史交互消息，保留系统提示。
    """
    for agent in _AGENT_INSTANCES.values():
        agent.reset_context()


def restore_all_histories() -> dict:
    """从数据库恢复所有已注册 Agent 的历史消息到内存上下文。

    在应用启动时调用，确保 Agent 在重启后仍能延续之前的对话历史。
    仅恢复已实例化的 Agent；若 Agent 尚未实例化，则跳过。

    Returns:
        字典 {agent_id: restored_message_count}，记录每个 Agent 恢复的消息数。
    """
    from backend import database

    restored_counts: dict[str, int] = {}
    all_histories = database.load_all_agent_histories()

    for agent_id, messages in all_histories.items():
        agent = _AGENT_INSTANCES.get(agent_id)
        if agent is None:
            # Agent 尚未实例化，仅记录数量，跳过内存恢复
            restored_counts[agent_id] = len(messages)
            continue
        try:
            # 通过 load_history 重建内存上下文
            agent.load_history()
            restored_counts[agent_id] = len(messages)
            logger.info(
                "Agent %s 历史恢复完成，共 %d 条消息", agent_id, len(messages)
            )
        except Exception:
            logger.warning("Agent %s 历史恢复失败", agent_id, exc_info=True)
            restored_counts[agent_id] = 0

    return restored_counts
