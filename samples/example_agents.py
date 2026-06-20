"""
ThesisMiner v8.0 Agent 示例代码
================================

本文件提供 ThesisMiner 多 Agent 架构的完整示例代码，包括：
1. 自定义 Agent 实现（继承 BaseAgent）
2. Agent 协作示例（多 Agent 编排）
3. 流式输出示例（AsyncGenerator + SSE）
4. 错误处理与重试示例
5. 上下文管理示例（DST 压缩）

使用方法：
    python samples/example_agents.py

依赖：
    - Python 3.10+
    - httpx
    - 参见 requirements.txt
"""

from __future__ import annotations

import asyncio
import json
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Type

import httpx

# ============================================================================
# 日志配置
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("thesisminer.samples")


# ============================================================================
# 基础数据结构
# ============================================================================

@dataclass
class AgentContext:
    """Agent 运行上下文

    每个 Agent 实例拥有独立的上下文，包含会话信息、对话历史与元数据。
    上下文隔离确保不同 Agent 之间不会互相干扰。
    """

    session_id: str
    conversation_id: str
    stage: str  # 当前阶段：information_confirmation / ideation / validation / generation / deep_assistance
    history: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str):
        """添加消息到历史"""
        self.history.append({"role": role, "content": content})

    def get_recent(self, n: int = 3) -> List[Dict[str, str]]:
        """获取最近 n 条消息"""
        return self.history[-n:] if self.history else []

    def clear_history(self):
        """清空历史"""
        self.history.clear()


@dataclass
class AgentConfig:
    """Agent 配置"""

    model: str = "deepseek-r2"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    retry_count: int = 3
    retry_delay: float = 1.0


@dataclass
class AgentResult:
    """Agent 执行结果"""

    success: bool
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    cache_hit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "content": self.content,
            "metadata": self.metadata,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
            "cache_hit": self.cache_hit,
        }


# ============================================================================
# BaseAgent 抽象基类
# ============================================================================

class BaseAgent(ABC):
    """所有 Agent 的抽象基类

    自定义 Agent 必须继承此类并实现 run 方法。
    可选实现 stream 方法以支持流式输出。
    """

    def __init__(
        self,
        name: str,
        model: str,
        context: AgentContext,
        config: Optional[AgentConfig] = None,
        api_key: str = "",
        base_url: str = "",
    ):
        self.name = name
        self.model = model
        self.context = context
        self.config = config or AgentConfig(model=model)
        self.api_key = api_key
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    @abstractmethod
    async def run(self, input: str) -> AgentResult:
        """执行 Agent 任务（非流式）

        Args:
            input: 输入文本

        Returns:
            AgentResult: 执行结果
        """
        pass

    async def stream(self, input: str) -> AsyncGenerator[str, None]:
        """执行 Agent 任务（流式）

        默认实现调用 run 方法并一次性 yield 结果。
        子类可重写以实现真正的流式输出。

        Args:
            input: 输入文本

        Yields:
            str: 输出文本块
        """
        result = await self.run(input)
        if result.success:
            yield result.content

    def reset(self):
        """重置 Agent 上下文"""
        self.context.clear_history()
        self.context.metadata.clear()

    async def get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（懒加载）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    def build_prompt(self, input: str) -> List[Dict[str, str]]:
        """构建三段式 Prompt

        结构：
        1. 稳定前缀（system）：角色定义、规则说明
        2. 动态中间（user）：用户输入
        3. DST 尾部（assistant）：历史对话压缩

        Returns:
            消息列表
        """
        system_prompt = self.get_system_prompt()
        dst_summary = self.get_dst_summary()

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input},
            {"role": "assistant", "content": dst_summary},
        ]

    def get_system_prompt(self) -> str:
        """获取系统提示（稳定前缀）

        子类应重写此方法返回特定的系统提示。
        系统提示应保持稳定，以利于缓存命中。
        """
        return "你是一个有帮助的助手。"

    def get_dst_summary(self) -> str:
        """获取 DST 压缩摘要

        将历史对话压缩为摘要，控制 Token 使用。
        """
        if not self.context.history:
            return "（无历史对话）"

        recent = self.context.get_recent(3)
        summary_parts = []
        for msg in recent:
            role = msg["role"]
            content = msg["content"][:200]
            summary_parts.append(f"{role}: {content}")

        return "历史摘要：\n" + "\n".join(summary_parts)

    def get_cache_key(self) -> str:
        """计算缓存 key（基于稳定前缀的 SHA-256）"""
        stable_content = self.get_system_prompt()
        return hashlib.sha256(stable_content.encode()).hexdigest()

    async def call_model(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """调用底层模型

        Args:
            messages: 消息列表

        Returns:
            模型响应
        """
        client = await self.get_client()

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        response = await client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        )
        response.raise_for_status()

        return response.json()

    async def call_model_stream(
        self, messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """流式调用模型

        Args:
            messages: 消息列表

        Yields:
            str: 输出文本块
        """
        client = await self.get_client()

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }

        async with client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


# ============================================================================
# Agent 注册表
# ============================================================================

AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {}


def register_agent(name: str, agent_class: Type[BaseAgent]):
    """注册 Agent 到全局注册表

    Args:
        name: Agent 名称（唯一标识）
        agent_class: Agent 类（BaseAgent 子类）
    """
    if name in AGENT_REGISTRY:
        raise ValueError(f"Agent '{name}' 已注册")
    AGENT_REGISTRY[name] = agent_class
    logger.info(f"已注册 Agent: {name}")


def get_agent_class(name: str) -> Type[BaseAgent]:
    """获取已注册的 Agent 类"""
    if name not in AGENT_REGISTRY:
        raise KeyError(f"Agent '{name}' 未注册")
    return AGENT_REGISTRY[name]


def list_agents() -> List[str]:
    """列出所有已注册的 Agent"""
    return list(AGENT_REGISTRY.keys())


# ============================================================================
# 内置 Agent 实现
# ============================================================================

class ReasonerAgent(BaseAgent):
    """推理 Agent

    负责信息确权与逻辑推理。
    分析用户输入，提取关键信息，构建初始上下文。
    """

    def __init__(
        self,
        context: AgentContext,
        config: Optional[AgentConfig] = None,
        api_key: str = "",
        base_url: str = "",
    ):
        super().__init__(
            name="ReasonerAgent",
            model="deepseek-r2",
            context=context,
            config=config or AgentConfig(
                model="deepseek-r2",
                temperature=0.3,  # 低温度，保证推理准确
                max_tokens=4096,
            ),
            api_key=api_key,
            base_url=base_url,
        )

    def get_system_prompt(self) -> str:
        return """你是一位学术研究推理专家。你的任务是分析用户提供的信息，提取关键要素，并进行逻辑推理。

你的职责：
1. 分析用户的研究背景、兴趣与约束
2. 提取关键信息（学位、学科、导师、兴趣等）
3. 识别用户的需求与痛点
4. 构建结构化的上下文摘要

请以 JSON 格式返回分析结果，包含以下字段：
- degree: 学位类型
- discipline: 学科方向
- research_interests: 研究兴趣列表
- advisor_info: 导师信息
- constraints: 约束条件
- key_insights: 关键洞察
- recommended_direction: 推荐方向"""

    async def run(self, input: str) -> AgentResult:
        start_time = time.time()
        try:
            messages = self.build_prompt(input)
            response = await self.call_model(messages)

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {}).get("total_tokens", 0)

            # 记录到上下文
            self.context.add_message("user", input)
            self.context.add_message("assistant", content)

            latency = (time.time() - start_time) * 1000

            return AgentResult(
                success=True,
                content=content,
                metadata={
                    "agent": self.name,
                    "model": self.model,
                    "stage": "information_confirmation",
                },
                tokens_used=tokens,
                cost_usd=tokens * 0.000001,  # 简化成本计算
                latency_ms=latency,
            )

        except Exception as e:
            logger.error(f"ReasonerAgent 执行失败: {e}")
            return AgentResult(
                success=False,
                content="",
                error=str(e),
                metadata={"agent": self.name},
            )


class MentorAgent(BaseAgent):
    """导师 Agent

    负责创意生成与导师指导。
    基于四维引擎生成候选论题。
    """

    def __init__(
        self,
        context: AgentContext,
        config: Optional[AgentConfig] = None,
        api_key: str = "",
        base_url: str = "",
    ):
        super().__init__(
            name="MentorAgent",
            model="claude-opus-4.5",
            context=context,
            config=config or AgentConfig(
                model="claude-opus-4.5",
                temperature=0.9,  # 高温度，激发创意
                max_tokens=8192,
            ),
            api_key=api_key,
            base_url=base_url,
        )

    def get_system_prompt(self) -> str:
        return """你是一位经验丰富的学术导师。你的任务是基于学生的背景信息，生成高质量的学术论题。

你使用四维创意引擎生成论题：
1. 导师项目延伸：基于导师近期项目延伸新的研究点
2. 前辈工作继承：基于同门师兄师姐的工作继续深入
3. 问题意识驱动：基于领域痛点提出解决方案
4. 跨学科迁移：将其他领域的方法迁移到本领域

请生成 8-12 个候选论题，以 JSON 数组格式返回，每个论题包含：
- title: 论题标题（15-40 字符）
- source: 创意来源（mentor_project / senior_inherit / problem_awareness / cross_domain）
- background: 研究背景
- problem: 拟解决问题
- method: 拟采用方法
- contribution: 预期贡献
- score: 综合评分（0-100）"""

    async def run(self, input: str) -> AgentResult:
        start_time = time.time()
        try:
            messages = self.build_prompt(input)
            response = await self.call_model(messages)

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {}).get("total_tokens", 0)

            self.context.add_message("user", input)
            self.context.add_message("assistant", content)

            latency = (time.time() - start_time) * 1000

            return AgentResult(
                success=True,
                content=content,
                metadata={
                    "agent": self.name,
                    "model": self.model,
                    "stage": "ideation",
                },
                tokens_used=tokens,
                cost_usd=tokens * 0.000015,
                latency_ms=latency,
            )

        except Exception as e:
            logger.error(f"MentorAgent 执行失败: {e}")
            return AgentResult(
                success=False,
                content="",
                error=str(e),
                metadata={"agent": self.name},
            )

    async def stream(self, input: str) -> AsyncGenerator[str, None]:
        """流式生成创意"""
        messages = self.build_prompt(input)
        async for chunk in self.call_model_stream(messages):
            yield chunk


class SearcherAgent(BaseAgent):
    """检索 Agent

    负责文献检索与谱系构建。
    搜索相关文献，构建学术谱系。
    """

    def __init__(
        self,
        context: AgentContext,
        config: Optional[AgentConfig] = None,
        api_key: str = "",
        base_url: str = "",
    ):
        super().__init__(
            name="SearcherAgent",
            model="deepseek-r2",
            context=context,
            config=config or AgentConfig(
                model="deepseek-r2",
                temperature=0.5,
                max_tokens=4096,
            ),
            api_key=api_key,
            base_url=base_url,
        )

    def get_system_prompt(self) -> str:
        return """你是一位学术文献检索专家。你的任务是检索相关文献，构建学术谱系。

你的职责：
1. 根据研究方向检索相关文献
2. 识别导师的学术谱系（师承关系）
3. 找出同门前辈的工作
4. 评估文献与论题的关联度

请以 JSON 格式返回检索结果，包含：
- papers: 相关文献列表（每篇含 title, authors, year, abstract, relevance_score）
- lineage: 学术谱系（含 advisor, seniors, their_works）
- key_findings: 关键发现"""

    async def run(self, input: str) -> AgentResult:
        start_time = time.time()
        try:
            messages = self.build_prompt(input)
            response = await self.call_model(messages)

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {}).get("total_tokens", 0)

            latency = (time.time() - start_time) * 1000

            return AgentResult(
                success=True,
                content=content,
                metadata={
                    "agent": self.name,
                    "model": self.model,
                    "stage": "ideation",
                },
                tokens_used=tokens,
                cost_usd=tokens * 0.000001,
                latency_ms=latency,
            )

        except Exception as e:
            logger.error(f"SearcherAgent 执行失败: {e}")
            return AgentResult(
                success=False,
                content="",
                error=str(e),
                metadata={"agent": self.name},
            )


class CriticAgent(BaseAgent):
    """评审 Agent

    负责约束校验与质量评分。
    对论题进行多维度评估，不通过则触发回退。
    """

    def __init__(
        self,
        context: AgentContext,
        config: Optional[AgentConfig] = None,
        api_key: str = "",
        base_url: str = "",
    ):
        super().__init__(
            name="CriticAgent",
            model="deepseek-r2",
            context=context,
            config=config or AgentConfig(
                model="deepseek-r2",
                temperature=0.2,  # 极低温度，保证评估一致
                max_tokens=4096,
            ),
            api_key=api_key,
            base_url=base_url,
        )

    def get_system_prompt(self) -> str:
        return """你是一位严格的学术评审专家。你的任务是对论题进行多维度评估。

评估维度：

硬约束（必须通过）：
1. 标题长度 15-40 字符
2. 学科匹配
3. 导师方向一致性
4. 时间可行性
5. 重复度 ≤ 30%
6. AI 痕迹检测

软约束（评分制，0-100）：
1. 新颖性（学科交叉/方法迁移/痛点突破/趋势前瞻）
2. 可行性（技术/资源/时间/学术）
3. 风格质量（句式/词汇/逻辑/规范）

请以 JSON 格式返回评估结果：
- hard_constraints: 硬约束检查结果（每项含 passed, message）
- soft_constraints: 软约束评分（每项含 score, reasoning）
- overall_score: 综合评分
- passed: 是否通过（bool）
- suggestions: 改进建议"""

    async def run(self, input: str) -> AgentResult:
        start_time = time.time()
        try:
            messages = self.build_prompt(input)
            response = await self.call_model(messages)

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {}).get("total_tokens", 0)

            latency = (time.time() - start_time) * 1000

            return AgentResult(
                success=True,
                content=content,
                metadata={
                    "agent": self.name,
                    "model": self.model,
                    "stage": "validation",
                },
                tokens_used=tokens,
                cost_usd=tokens * 0.000001,
                latency_ms=latency,
            )

        except Exception as e:
            logger.error(f"CriticAgent 执行失败: {e}")
            return AgentResult(
                success=False,
                content="",
                error=str(e),
                metadata={"agent": self.name},
            )


# ============================================================================
# 自定义 Agent 实现
# ============================================================================

class LiteratureAgent(BaseAgent):
    """文献分析 Agent（自定义示例）

    深度分析文献并提取关键信息。
    """

    def __init__(
        self,
        context: AgentContext,
        config: Optional[AgentConfig] = None,
        api_key: str = "",
        base_url: str = "",
    ):
        super().__init__(
            name="LiteratureAgent",
            model="claude-opus-4.5",
            context=context,
            config=config or AgentConfig(
                model="claude-opus-4.5",
                temperature=0.3,
                max_tokens=8192,
                timeout=120,
            ),
            api_key=api_key,
            base_url=base_url,
        )

    def get_system_prompt(self) -> str:
        return """你是一位学术文献分析专家。你的任务是深度分析文献，提取关键信息。

分析维度：
1. 研究问题与动机
2. 方法核心创新
3. 实验设计与结果
4. 与当前论题的关联
5. 可借鉴之处
6. 局限性与改进空间

请以 JSON 格式返回分析结果。"""

    async def run(self, input: str) -> AgentResult:
        start_time = time.time()
        try:
            messages = self.build_prompt(input)
            response = await self.call_model(messages)

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {}).get("total_tokens", 0)

            latency = (time.time() - start_time) * 1000

            return AgentResult(
                success=True,
                content=content,
                metadata={
                    "agent": self.name,
                    "model": self.model,
                    "stage": "deep_assistance",
                    "analysis_type": "literature",
                },
                tokens_used=tokens,
                cost_usd=tokens * 0.000015,
                latency_ms=latency,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                content="",
                error=str(e),
                metadata={"agent": self.name},
            )


class DefenseSimulatorAgent(BaseAgent):
    """答辩模拟 Agent（自定义示例）

    模拟答辩场景，生成问题并评估回答。
    """

    JUDGE_PROFILES = {
        "friendly": "友善型评委：多鼓励，少追问，关注亮点",
        "rigorous": "严谨型评委：追问细节，质疑方法，关注严谨性",
        "challenging": "挑战型评委：强烈质疑，压力测试，关注创新性",
    }

    def __init__(
        self,
        context: AgentContext,
        judge_style: str = "rigorous",
        config: Optional[AgentConfig] = None,
        api_key: str = "",
        base_url: str = "",
    ):
        super().__init__(
            name="DefenseSimulatorAgent",
            model="claude-opus-4.5",
            context=context,
            config=config or AgentConfig(
                model="claude-opus-4.5",
                temperature=0.7,
                max_tokens=4096,
            ),
            api_key=api_key,
            base_url=base_url,
        )
        self.judge_style = judge_style

    def get_system_prompt(self) -> str:
        profile = self.JUDGE_PROFILES.get(self.judge_style, self.JUDGE_PROFILES["rigorous"])
        return f"""你是一位答辩评委。你的角色设定：{profile}

你的任务：
1. 基于论题内容生成有深度的问题
2. 对学生的回答进行评估
3. 给出改进建议

请以 JSON 格式返回：
- questions: 问题列表（每个问题含 type, question, expected_points）
- evaluation: 评估（含 scores, feedback）"""

    async def run(self, input: str) -> AgentResult:
        start_time = time.time()
        try:
            messages = self.build_prompt(input)
            response = await self.call_model(messages)

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {}).get("total_tokens", 0)

            latency = (time.time() - start_time) * 1000

            return AgentResult(
                success=True,
                content=content,
                metadata={
                    "agent": self.name,
                    "model": self.model,
                    "stage": "deep_assistance",
                    "judge_style": self.judge_style,
                },
                tokens_used=tokens,
                cost_usd=tokens * 0.000015,
                latency_ms=latency,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                content="",
                error=str(e),
                metadata={"agent": self.name},
            )


# ============================================================================
# Agent 编排器
# ============================================================================

class Orchestrator:
    """Agent 编排器

    管理多 Agent 协作流程，支持顺序、并行、管道三种执行模式。
    """

    def __init__(self, context: AgentContext):
        self.context = context
        self.agents: List[BaseAgent] = []
        self.results: List[AgentResult] = []

    def add_agent(self, agent: BaseAgent) -> "Orchestrator":
        """添加 Agent 到编排流程"""
        self.agents.append(agent)
        return self

    async def run_sequential(self, input: str) -> List[AgentResult]:
        """顺序执行所有 Agent

        前一个 Agent 的输出作为后一个 Agent 的输入。
        如果某个 Agent 失败，停止执行。
        """
        current_input = input
        for agent in self.agents:
            logger.info(f"执行 Agent: {agent.name}")
            result = await agent.run(current_input)
            self.results.append(result)

            if not result.success:
                logger.error(f"Agent {agent.name} 失败: {result.error}")
                break

            current_input = result.content

        return self.results

    async def run_parallel(self, input: str) -> List[AgentResult]:
        """并行执行所有 Agent

        所有 Agent 接收相同的输入，并行执行。
        """
        tasks = [agent.run(input) for agent in self.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                self.results.append(AgentResult(
                    success=False,
                    content="",
                    error=str(r),
                ))
            else:
                self.results.append(r)

        return self.results

    async def run_pipeline(self, inputs: List[str]) -> List[AgentResult]:
        """管道执行

        每个 Agent 处理不同的输入，并行执行。
        """
        if len(inputs) != len(self.agents):
            raise ValueError("输入数量与 Agent 数量不匹配")

        tasks = [agent.run(inp) for agent, inp in zip(self.agents, inputs)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                self.results.append(AgentResult(
                    success=False,
                    content="",
                    error=str(r),
                ))
            else:
                self.results.append(r)

        return self.results

    async def close_all(self):
        """关闭所有 Agent"""
        for agent in self.agents:
            await agent.close()


# ============================================================================
# 错误处理与重试
# ============================================================================

class AgentExecutor:
    """带错误处理与重试的 Agent 执行器"""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: int = 60,
        fallback_models: Optional[List[str]] = None,
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.fallback_models = fallback_models or []

    async def execute_with_retry(
        self,
        agent: BaseAgent,
        input: str,
    ) -> AgentResult:
        """带重试的执行

        Args:
            agent: Agent 实例
            input: 输入

        Returns:
            AgentResult: 执行结果
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"执行 {agent.name}（尝试 {attempt + 1}/{self.max_retries}）"
                )

                result = await asyncio.wait_for(
                    agent.run(input),
                    timeout=self.timeout,
                )

                if result.success:
                    return result

                last_error = result.error

            except asyncio.TimeoutError:
                last_error = f"超时（{self.timeout}s）"
                logger.warning(f"{agent.name} 超时")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"{agent.name} 异常: {e}")

            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)  # 指数退避
                logger.info(f"等待 {delay}s 后重试...")
                await asyncio.sleep(delay)

        # 所有重试失败，尝试 fallback 模型
        if self.fallback_models:
            for fallback_model in self.fallback_models:
                logger.info(f"尝试 fallback 模型: {fallback_model}")
                try:
                    agent.config.model = fallback_model
                    result = await asyncio.wait_for(
                        agent.run(input),
                        timeout=self.timeout,
                    )
                    if result.success:
                        result.metadata["used_fallback"] = True
                        result.metadata["fallback_model"] = fallback_model
                        return result
                except Exception as e:
                    logger.warning(f"Fallback {fallback_model} 失败: {e}")

        return AgentResult(
            success=False,
            content="",
            error=f"所有重试失败: {last_error}",
            metadata={
                "agent": agent.name,
                "retries": self.max_retries,
                "fallbacks_tried": self.fallback_models,
            },
        )


# ============================================================================
# DST 压缩器
# ============================================================================

class DSTCompressor:
    """DST（Dialog State Tracking）压缩器

    将长对话历史压缩为摘要，控制 Token 使用。
    """

    def __init__(
        self,
        max_recent_turns: int = 3,
        max_summary_tokens: int = 500,
        compression_threshold: int = 10,
    ):
        self.max_recent_turns = max_recent_turns
        self.max_summary_tokens = max_summary_tokens
        self.compression_threshold = compression_threshold

    def compress(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """压缩对话历史

        Args:
            history: 完整对话历史

        Returns:
            {
                "summary": "压缩摘要",
                "recent_turns": [最近几轮对话],
                "compressed_count": 被压缩的轮数
            }
        """
        if len(history) <= self.compression_threshold:
            return {
                "summary": "",
                "recent_turns": history,
                "compressed_count": 0,
            }

        to_compress = history[:-self.max_recent_turns]
        to_keep = history[-self.max_recent_turns:]

        summary = self._generate_summary(to_compress)

        return {
            "summary": summary,
            "recent_turns": to_keep,
            "compressed_count": len(to_compress),
        }

    def _generate_summary(self, turns: List[Dict[str, str]]) -> str:
        """生成对话摘要"""
        summary_parts = []
        for turn in turns:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")

            if role == "user":
                intent = content[:50].replace("\n", " ")
                summary_parts.append(f"用户询问: {intent}")
            elif role == "assistant":
                points = content[:100].replace("\n", " ")
                summary_parts.append(f"助手回答: {points}")

        return "；".join(summary_parts)


# ============================================================================
# 示例 1：自定义 Agent 完整实现
# ============================================================================

async def example_1_custom_agent():
    """示例 1：实现并使用自定义 Agent"""
    print("\n" + "=" * 60)
    print("示例 1：自定义 Agent 实现")
    print("=" * 60)

    # 创建上下文
    context = AgentContext(
        session_id="sess_example_1",
        conversation_id="conv_example_1",
        stage="deep_assistance",
        metadata={"topic": "基于半监督学习的小病灶检测"},
    )

    # 创建 Agent（使用模拟 API）
    agent = LiteratureAgent(
        context=context,
        api_key="sk-mock-key",
        base_url="https://api.mock.com/v1",
    )

    # 模拟运行（不实际调用 API）
    print(f"Agent 名称: {agent.name}")
    print(f"Agent 模型: {agent.model}")
    print(f"缓存 Key: {agent.get_cache_key()[:16]}...")
    print(f"系统提示前 100 字符: {agent.get_system_prompt()[:100]}...")

    await agent.close()


# ============================================================================
# 示例 2：Agent 协作编排
# ============================================================================

async def example_2_orchestration():
    """示例 2：多 Agent 协作编排"""
    print("\n" + "=" * 60)
    print("示例 2：Agent 协作编排")
    print("=" * 60)

    context = AgentContext(
        session_id="sess_example_2",
        conversation_id="conv_example_2",
        stage="ideation",
    )

    # 创建编排器
    orchestrator = Orchestrator(context)

    # 添加 Agent（使用模拟配置）
    reasoner = ReasonerAgent(
        context=context,
        api_key="sk-mock",
        base_url="https://api.mock.com/v1",
    )
    mentor = MentorAgent(
        context=context,
        api_key="sk-mock",
        base_url="https://api.mock.com/v1",
    )

    orchestrator.add_agent(reasoner)
    orchestrator.add_agent(mentor)

    print(f"已添加 {len(orchestrator.agents)} 个 Agent:")
    for agent in orchestrator.agents:
        print(f"  - {agent.name} (model: {agent.model})")

    await orchestrator.close_all()


# ============================================================================
# 示例 3：流式输出
# ============================================================================

async def example_3_streaming():
    """示例 3：流式输出示例"""
    print("\n" + "=" * 60)
    print("示例 3：流式输出")
    print("=" * 60)

    context = AgentContext(
        session_id="sess_example_3",
        conversation_id="conv_example_3",
        stage="ideation",
    )

    agent = MentorAgent(
        context=context,
        api_key="sk-mock",
        base_url="https://api.mock.com/v1",
    )

    # 演示流式接口（模拟）
    print("流式输出接口已就绪（实际调用需配置有效 API Key）")
    print(f"Agent: {agent.name}")
    print(f"支持流式: 是")

    await agent.close()


# ============================================================================
# 示例 4：错误处理与重试
# ============================================================================

async def example_4_error_handling():
    """示例 4：错误处理与重试"""
    print("\n" + "=" * 60)
    print("示例 4：错误处理与重试")
    print("=" * 60)

    context = AgentContext(
        session_id="sess_example_4",
        conversation_id="conv_example_4",
        stage="ideation",
    )

    agent = MentorAgent(
        context=context,
        api_key="sk-invalid-key",  # 故意使用无效 Key
        base_url="https://api.mock.com/v1",
    )

    # 创建执行器
    executor = AgentExecutor(
        max_retries=3,
        retry_delay=0.5,
        timeout=10,
        fallback_models=["gpt-4.1", "deepseek-r2"],
    )

    print(f"执行器配置:")
    print(f"  最大重试: {executor.max_retries}")
    print(f"  超时: {executor.timeout}s")
    print(f"  Fallback 模型: {executor.fallback_models}")

    # 注意：实际执行会因无效 API Key 而失败
    # result = await executor.execute_with_retry(agent, "生成论题")
    # print(f"结果: {result.success}, 错误: {result.error}")

    await agent.close()
    print("（演示完成，未实际调用 API）")


# ============================================================================
# 示例 5：DST 压缩
# ============================================================================

async def example_5_dst_compression():
    """示例 5：DST 压缩"""
    print("\n" + "=" * 60)
    print("示例 5：DST 压缩")
    print("=" * 60)

    # 创建模拟对话历史
    history = []
    for i in range(15):
        history.append({"role": "user", "content": f"这是第 {i+1} 轮用户消息，内容较长..."})
        history.append({"role": "assistant", "content": f"这是第 {i+1} 轮助手回答，内容也很长..."})

    print(f"原始历史: {len(history)} 条消息")

    # 创建压缩器
    compressor = DSTCompressor(
        max_recent_turns=3,
        max_summary_tokens=500,
        compression_threshold=10,
    )

    result = compressor.compress(history)

    print(f"压缩后:")
    print(f"  摘要长度: {len(result['summary'])} 字符")
    print(f"  保留轮数: {len(result['recent_turns'])}")
    print(f"  压缩轮数: {result['compressed_count']}")
    print(f"  摘要预览: {result['summary'][:100]}...")


# ============================================================================
# 示例 6：Agent 注册与查询
# ============================================================================

async def example_6_registration():
    """示例 6：Agent 注册与查询"""
    print("\n" + "=" * 60)
    print("示例 6：Agent 注册与查询")
    print("=" * 60)

    # 注册内置 Agent
    register_agent("Reasoner", ReasonerAgent)
    register_agent("Mentor", MentorAgent)
    register_agent("Searcher", SearcherAgent)
    register_agent("Critic", CriticAgent)

    # 注册自定义 Agent
    register_agent("Literature", LiteratureAgent)
    register_agent("DefenseSimulator", DefenseSimulatorAgent)

    # 列出所有 Agent
    agents = list_agents()
    print(f"已注册 {len(agents)} 个 Agent:")
    for name in agents:
        agent_class = get_agent_class(name)
        print(f"  - {name}: {agent_class.__name__}")


# ============================================================================
# 主函数
# ============================================================================

async def main():
    """主函数：运行所有示例"""
    print("=" * 60)
    print("ThesisMiner v8.0 Agent 示例代码")
    print("=" * 60)

    await example_1_custom_agent()
    await example_2_orchestration()
    await example_3_streaming()
    await example_4_error_handling()
    await example_5_dst_compression()
    await example_6_registration()

    print("\n" + "=" * 60)
    print("所有示例执行完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
