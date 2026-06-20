"""Agent 基类 - Claude Code 式主管理+子Agent架构

每个 Agent 有独立系统提示、独立上下文窗口、独立模型路由。
通过 ai_proxy.call_llm 调用 LLM，使用自己的 model_id 与 system_prompt，
维护独立的 messages 上下文列表，避免子 Agent 之间相互污染。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    """Agent 执行结果

    所有子 Agent 的 run() 方法都应返回此结构，
    便于 Orchestrator 统一汇总与门禁判断。
    """
    agent_id: str
    success: bool
    content: str = ""
    reasoning: str = ""
    data: dict = field(default_factory=dict)
    citations: list = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)
    error: str = ""


class BaseAgent(ABC):
    """Agent 抽象基类

    每个 Agent 维护独立的 messages 上下文列表，
    通过 ai_proxy.call_llm 调用 LLM，使用自己的 model_id 与 system_prompt。

    子类必须实现 run() 方法，在其中：
        1. 基于自身 messages 上下文构建提示
        2. 调用 ai_proxy.call_llm（传入自己的 model_id）
        3. 解析响应为 AgentResult
        4. 将本轮交互追加到自身 messages 列表
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        system_prompt: str,
        model_id: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        capabilities: list[str] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.capabilities = capabilities or []
        # 独立上下文窗口：仅初始化时包含系统提示
        self.messages: list[dict] = [{"role": "system", "content": system_prompt}]

    def reset_context(self):
        """重置上下文，仅保留系统提示

        用于新会话开始时清空历史交互，避免跨会话污染。
        """
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def add_message(self, role: str, content: str):
        """添加消息到上下文

        Args:
            role: 消息角色（user / assistant）。
            content: 消息内容。
        """
        self.messages.append({"role": role, "content": content})

    def save_message(
        self,
        role: str,
        content: str,
        reasoning: str = None,
        citations: list = None,
        conversation_id: str = None,
        session_id: str = None,
        metadata: dict = None,
    ) -> str:
        """持久化一条消息到数据库，并同步追加到内存上下文。

        Args:
            role: 消息角色（'user' / 'assistant' / 'system'）。
            content: 消息内容。
            reasoning: 推理/思维链内容（可选）。
            citations: 引用列表（可选）。
            conversation_id: 关联的对话 ID（可选）。
            session_id: 关联的会话 ID（可选）。
            metadata: 额外元数据（可选）。

        Returns:
            生成的消息 ID。
        """
        # 延迟导入以避免循环依赖
        from backend import database

        msg_id = database.save_agent_message(
            agent_id=self.agent_id,
            role=role,
            content=content,
            conversation_id=conversation_id,
            session_id=session_id,
            reasoning=reasoning,
            citations=citations,
            metadata=metadata,
        )
        # 同步到内存上下文（system 角色不重复追加，避免污染上下文）
        if role != "system":
            self.messages.append({"role": role, "content": content})
        return msg_id

    def load_history(
        self,
        conversation_id: str = None,
        session_id: str = None,
        limit: int = 100,
    ) -> list:
        """从数据库加载该 Agent 的消息历史，并重建内存上下文。

        加载后会重置内存上下文为 [system_prompt] + 加载到的消息，
        确保内存与数据库一致。

        Args:
            conversation_id: 对话 ID 过滤（可选）。
            session_id: 会话 ID 过滤（可选）。
            limit: 返回的最大消息数，默认 100。

        Returns:
            消息字典列表（不含系统提示）。
        """
        from backend import database

        rows = database.load_agent_history(
            agent_id=self.agent_id,
            conversation_id=conversation_id,
            session_id=session_id,
            limit=limit,
        )
        # 重建内存上下文：系统提示 + 历史消息
        self.messages = [{"role": "system", "content": self.system_prompt}]
        for row in rows:
            if row.get("role") == "system":
                continue
            self.messages.append({
                "role": row.get("role", "user"),
                "content": row.get("content", ""),
            })
        return rows

    def get_history(self) -> list:
        """获取当前内存上下文中的消息历史。

        若内存上下文仅有系统提示（即尚未加载历史），则尝试从数据库加载。

        Returns:
            消息字典列表（含系统提示）。
        """
        if len(self.messages) <= 1:
            self.load_history()
        return self.messages.copy()

    def get_context(self) -> list[dict]:
        """获取当前上下文（返回副本，避免外部修改）"""
        return self.messages.copy()

    @abstractmethod
    async def run(self, task_input: dict) -> AgentResult:
        """执行任务（子类实现）

        Args:
            task_input: 任务输入字典，结构由各子 Agent 自定义。

        Returns:
            AgentResult 实例。
        """
        pass

    def get_metadata(self) -> dict:
        """返回 Agent 元数据"""
        return {
            "id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "default_model": self.model_id,
            "capabilities": self.capabilities,
        }
