"""orchestrator 模块单元测试

测试 backend/agents/orchestrator.py 的 OrchestratorAgent：
  - 初始化与默认属性
  - 五阶段顺序调度（info_confirm → creativity → validation → generation → deep_assist）
  - 阶段间门禁（评分 < 60 回退）
  - confirm_info 用户确认
  - reset 重置状态
  - get_stage 获取当前阶段
  - orchestrate 流式编排
  - run 非流式执行
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
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_orchestrator_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.agents.base_agent import AgentResult
from backend.agents.orchestrator import OrchestratorAgent


def _make_mock_agent_result(agent_id="mock", success=True, content="模拟内容", data=None):
    """构造模拟的 AgentResult"""
    return AgentResult(
        agent_id=agent_id,
        success=success,
        content=content,
        data=data or {},
    )


def _run_async(coro):
    """辅助函数：运行异步协程"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===== 初始化测试 =====


class TestOrchestratorInit:
    """OrchestratorAgent 初始化测试"""

    def test_init_sets_agent_id(self):
        """测试：初始化后 agent_id 为 orchestrator"""
        agent = OrchestratorAgent()
        assert agent.agent_id == "orchestrator"

    def test_init_sets_name(self):
        """测试：初始化后 name 为 Orchestrator"""
        agent = OrchestratorAgent()
        assert agent.name == "Orchestrator"

    def test_init_sets_description(self):
        """测试：初始化后包含描述"""
        agent = OrchestratorAgent()
        assert "主管理" in agent.description or "调度" in agent.description

    def test_init_default_stage_is_info_confirm(self):
        """测试：初始阶段为 info_confirm"""
        agent = OrchestratorAgent()
        assert agent.current_stage == "info_confirm"

    def test_init_stage_results_empty(self):
        """测试：初始化后阶段结果为空"""
        agent = OrchestratorAgent()
        assert agent.stage_results == {}

    def test_init_has_five_stages(self):
        """测试：STAGES 包含五个阶段"""
        assert len(OrchestratorAgent.STAGES) == 5
        assert "info_confirm" in OrchestratorAgent.STAGES
        assert "creativity" in OrchestratorAgent.STAGES
        assert "validation" in OrchestratorAgent.STAGES
        assert "generation" in OrchestratorAgent.STAGES
        assert "deep_assist" in OrchestratorAgent.STAGES

    def test_init_has_system_prompt(self):
        """测试：初始化后有系统提示"""
        agent = OrchestratorAgent()
        assert len(agent.system_prompt) > 0
        assert "Orchestrator" in agent.system_prompt or "主管理" in agent.system_prompt

    def test_init_has_capabilities(self):
        """测试：初始化后包含 capabilities"""
        agent = OrchestratorAgent()
        assert "streaming" in agent.capabilities
        assert "thinking" in agent.capabilities


# ===== get_stage 测试 =====


class TestGetStage:
    """get_stage 方法测试"""

    def test_get_stage_returns_current(self):
        """测试：get_stage 返回当前阶段"""
        agent = OrchestratorAgent()
        assert agent.get_stage() == "info_confirm"

    def test_get_stage_after_manual_change(self):
        """测试：手动修改阶段后 get_stage 返回新值"""
        agent = OrchestratorAgent()
        agent.current_stage = "creativity"
        assert agent.get_stage() == "creativity"


# ===== confirm_info 测试 =====


class TestConfirmInfo:
    """confirm_info 方法测试"""

    def test_confirm_info_from_info_confirm(self):
        """测试：从 info_confirm 阶段确认后进入 creativity"""
        agent = OrchestratorAgent()
        agent.current_stage = "info_confirm"
        result = agent.confirm_info()
        assert result is True
        assert agent.current_stage == "creativity"

    def test_confirm_info_from_wrong_stage(self):
        """测试：非 info_confirm 阶段确认返回 False"""
        agent = OrchestratorAgent()
        agent.current_stage = "creativity"
        result = agent.confirm_info()
        assert result is False
        assert agent.current_stage == "creativity"

    def test_confirm_info_from_validation(self):
        """测试：从 validation 阶段确认返回 False"""
        agent = OrchestratorAgent()
        agent.current_stage = "validation"
        result = agent.confirm_info()
        assert result is False


# ===== reset 测试 =====


class TestReset:
    """reset 方法测试"""

    def test_reset_clears_stage_results(self):
        """测试：reset 清空阶段结果"""
        agent = OrchestratorAgent()
        agent.stage_results = {"info_confirm": "some_result"}
        agent.reset()
        assert agent.stage_results == {}

    def test_reset_resets_current_stage(self):
        """测试：reset 将当前阶段重置为 info_confirm"""
        agent = OrchestratorAgent()
        agent.current_stage = "generation"
        agent.reset()
        assert agent.current_stage == "info_confirm"

    def test_reset_clears_context(self):
        """测试：reset 清空上下文历史"""
        agent = OrchestratorAgent()
        agent.add_message("user", "临时消息")
        assert len(agent.messages) > 1
        agent.reset()
        assert len(agent.messages) == 1
        assert agent.messages[0]["role"] == "system"


# ===== orchestrate 流式编排测试 =====


class TestOrchestrate:
    """orchestrate 流式编排测试"""

    def test_orchestrate_yields_info_confirm_stage(self):
        """测试：orchestrate 产出 info_confirm 阶段"""
        agent = OrchestratorAgent()
        mock_searcher = MagicMock()
        mock_searcher.run = AsyncMock(return_value=_make_mock_agent_result(
            agent_id="searcher",
            data={"papers": [{"title": "论文1"}]},
        ))
        mock_reasoner = MagicMock()
        mock_reasoner.run = AsyncMock(return_value=_make_mock_agent_result(
            agent_id="reasoner",
            data={"candidates": [{"title": "论题1", "dimension": "cross_discipline"}]},
        ))
        mock_critic = MagicMock()
        mock_critic.run = AsyncMock(return_value=_make_mock_agent_result(
            agent_id="critic",
            data={"evaluations": [{"title": "论题1", "score": 80}]},
        ))
        mock_writer = MagicMock()
        mock_writer.run = AsyncMock(return_value=_make_mock_agent_result(
            agent_id="writer",
            data={"content": "生成内容"},
        ))
        with patch("backend.agents.orchestrator.get_agent") as mock_get:
            mock_get.side_effect = [mock_searcher, mock_reasoner, mock_critic, mock_writer]
            chunks = _run_async(_collect_chunks(agent.orchestrate("机器学习")))

        stages = [c["stage"] for c in chunks]
        assert "info_confirm" in stages

    def test_orchestrate_yields_all_stages_on_success(self):
        """测试：成功时产出所有五个阶段"""
        agent = OrchestratorAgent()
        mock_searcher = MagicMock()
        mock_searcher.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"papers": []},
        ))
        mock_reasoner = MagicMock()
        mock_reasoner.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"candidates": [{"title": "T", "dimension": "cross_discipline"}]},
        ))
        mock_critic = MagicMock()
        mock_critic.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"evaluations": [{"title": "T", "score": 80}]},
        ))
        mock_writer = MagicMock()
        mock_writer.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"content": "内容"},
        ))
        with patch("backend.agents.orchestrator.get_agent") as mock_get:
            mock_get.side_effect = [mock_searcher, mock_reasoner, mock_critic, mock_writer]
            chunks = _run_async(_collect_chunks(agent.orchestrate("AI")))

        stages = set(c["stage"] for c in chunks)
        assert "info_confirm" in stages
        assert "creativity" in stages
        assert "validation" in stages
        assert "generation" in stages
        assert "deep_assist" in stages

    def test_orchestrate_retry_on_low_score(self):
        """测试：评分 < 60 时回退到创意阶段"""
        agent = OrchestratorAgent()
        mock_searcher = MagicMock()
        mock_searcher.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"papers": []},
        ))
        mock_reasoner = MagicMock()
        mock_reasoner.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"candidates": [{"title": "T", "dimension": "cross_discipline"}]},
        ))
        mock_critic = MagicMock()
        mock_critic.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"evaluations": [{"title": "T", "score": 40}]},
        ))
        with patch("backend.agents.orchestrator.get_agent") as mock_get:
            mock_get.side_effect = [mock_searcher, mock_reasoner, mock_critic]
            chunks = _run_async(_collect_chunks(agent.orchestrate("AI")))

        # 应有 retry 状态
        retry_chunks = [c for c in chunks if c.get("status") == "retry"]
        assert len(retry_chunks) >= 1
        # 当前阶段应回退到 creativity
        assert agent.current_stage == "creativity"

    def test_orchestrate_passes_on_high_score(self):
        """测试：评分 >= 60 时继续生成阶段"""
        agent = OrchestratorAgent()
        mock_searcher = MagicMock()
        mock_searcher.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"papers": []},
        ))
        mock_reasoner = MagicMock()
        mock_reasoner.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"candidates": [{"title": "T", "dimension": "cross_discipline"}]},
        ))
        mock_critic = MagicMock()
        mock_critic.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"evaluations": [{"title": "T", "score": 75}]},
        ))
        mock_writer = MagicMock()
        mock_writer.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"content": "内容"},
        ))
        with patch("backend.agents.orchestrator.get_agent") as mock_get:
            mock_get.side_effect = [mock_searcher, mock_reasoner, mock_critic, mock_writer]
            chunks = _run_async(_collect_chunks(agent.orchestrate("AI")))

        # 应到达 deep_assist 阶段
        assert agent.current_stage == "deep_assist"

    def test_orchestrate_final_stage_is_deep_assist(self):
        """测试：成功完成后最终阶段为 deep_assist"""
        agent = OrchestratorAgent()
        mock_searcher = MagicMock()
        mock_searcher.run = AsyncMock(return_value=_make_mock_agent_result(data={"papers": []}))
        mock_reasoner = MagicMock()
        mock_reasoner.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"candidates": [{"title": "T", "dimension": "cross_discipline"}]},
        ))
        mock_critic = MagicMock()
        mock_critic.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"evaluations": [{"title": "T", "score": 90}]},
        ))
        mock_writer = MagicMock()
        mock_writer.run = AsyncMock(return_value=_make_mock_agent_result(data={"content": "内容"}))
        with patch("backend.agents.orchestrator.get_agent") as mock_get:
            mock_get.side_effect = [mock_searcher, mock_reasoner, mock_critic, mock_writer]
            _run_async(_collect_chunks(agent.orchestrate("AI")))

        assert agent.get_stage() == "deep_assist"


# ===== run 非流式测试 =====


class TestRun:
    """run 非流式方法测试"""

    def test_run_returns_agent_result(self):
        """测试：run 返回 AgentResult"""
        agent = OrchestratorAgent()
        mock_searcher = MagicMock()
        mock_searcher.run = AsyncMock(return_value=_make_mock_agent_result(data={"papers": []}))
        mock_reasoner = MagicMock()
        mock_reasoner.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"candidates": [{"title": "T", "dimension": "cross_discipline"}]},
        ))
        mock_critic = MagicMock()
        mock_critic.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"evaluations": [{"title": "T", "score": 80}]},
        ))
        mock_writer = MagicMock()
        mock_writer.run = AsyncMock(return_value=_make_mock_agent_result(data={"content": "内容"}))
        with patch("backend.agents.orchestrator.get_agent") as mock_get:
            mock_get.side_effect = [mock_searcher, mock_reasoner, mock_critic, mock_writer]
            result = _run_async(agent.run({"user_input": "AI"}))

        assert isinstance(result, AgentResult)
        assert result.agent_id == "orchestrator"
        assert result.success is True

    def test_run_data_contains_stages(self):
        """测试：run 返回的 data 包含 stages 列表"""
        agent = OrchestratorAgent()
        mock_searcher = MagicMock()
        mock_searcher.run = AsyncMock(return_value=_make_mock_agent_result(data={"papers": []}))
        mock_reasoner = MagicMock()
        mock_reasoner.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"candidates": [{"title": "T", "dimension": "cross_discipline"}]},
        ))
        mock_critic = MagicMock()
        mock_critic.run = AsyncMock(return_value=_make_mock_agent_result(
            data={"evaluations": [{"title": "T", "score": 80}]},
        ))
        mock_writer = MagicMock()
        mock_writer.run = AsyncMock(return_value=_make_mock_agent_result(data={"content": "内容"}))
        with patch("backend.agents.orchestrator.get_agent") as mock_get:
            mock_get.side_effect = [mock_searcher, mock_reasoner, mock_critic, mock_writer]
            result = _run_async(agent.run({"user_input": "AI"}))

        assert "stages" in result.data
        assert "final_stage" in result.data
        assert isinstance(result.data["stages"], list)


async def _collect_chunks(gen):
    """辅助函数：收集异步生成器的所有产出"""
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
    return chunks
