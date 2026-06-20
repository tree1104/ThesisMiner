"""集成测试：五阶段流程端到端验证

覆盖：
- 完整五阶段流程：信息确权 → 创意 → 校验 → 生成 → 深度辅助
- 阶段门禁转移
- 低评分回退（retry）
- 用户确认门禁
- Mock AI 调用，使用真实 DB

运行方式：python -m pytest tests/integration/test_five_stage_flow.py -v
"""
import asyncio
import os
import sys
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 在导入 backend 模块前，切换到临时数据库，避免污染正式数据
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_integration_")
_tmp_db = os.path.join(_tmp_dir, "test_five_stage.db")
_db.DB_PATH = _tmp_db
_db.init_db()

from backend.agents.base_agent import AgentResult
from backend.constraints.stage_gate import (
    STAGE_GATES,
    Stage,
    StageGate,
    GateResult,
    check_gate,
)
from backend.orchestration.state_machine import (
    Event,
    Stage as SMStage,
    TRANSITIONS,
    TransitionResult,
    transition,
    get_next_events,
    is_valid_transition,
)
from backend.agents.orchestrator import OrchestratorAgent
from backend.sessions import session_manager
from backend.models import SessionCreate, DegreeType, DisciplineType


# ===== 辅助函数 =====

def _make_llm_result(content: str, cached: int = 0) -> dict:
    """构造模拟的 call_llm 返回值"""
    return {
        "content": content,
        "model": "mock-model",
        "prompt_tokens": 200,
        "completion_tokens": 100,
        "total_tokens": 300,
        "cached_tokens": cached,
        "cost": 0.0,
    }


def _make_session(title: str = "五阶段测试会话") -> str:
    """创建测试会话，返回 session_id"""
    req = SessionCreate(
        title=title,
        degree=DegreeType.master,
        discipline=DisciplineType.science_engineering,
        mentor_info="测试导师",
    )
    session = session_manager.create_session(req)
    return session["id"]


def _mock_searcher_result() -> AgentResult:
    """构造 SearcherAgent 的模拟结果"""
    return AgentResult(
        agent_id="searcher",
        success=True,
        content="检索完成，找到3篇相关文献",
        data={
            "papers": [
                {"title": "GNN for Vulnerability Detection", "year": 2024},
                {"title": "Devign", "year": 2019},
                {"title": "ReVeal", "year": 2021},
            ]
        },
        citations=[
            {"url": "https://arxiv.org/abs/001", "title": "GNN for Vuln"},
        ],
    )


def _mock_reasoner_result(score_pass: bool = True) -> AgentResult:
    """构造 ReasonerAgent 的模拟结果"""
    candidates = [
        {"title": "基于图神经网络的代码漏洞检测方法研究", "dimension": "method_transfer", "rationale": "迁移GNN到代码分析"},
        {"title": "面向跨项目泛化的GNN漏洞检测框架", "dimension": "pain_point_breakthrough", "rationale": "解决跨项目泛化痛点"},
        {"title": "基于注意力机制的可解释漏洞检测", "dimension": "trend_forecast", "rationale": "顺应可解释AI趋势"},
        {"title": "基于大语言模型的领域知识问答系统研究", "dimension": "cross_discipline", "rationale": "LLM+RAG交叉"},
    ]
    return AgentResult(
        agent_id="reasoner",
        success=True,
        content="生成4个候选论题",
        data={"candidates": candidates, "discipline": "computer_science", "degree": "master"},
    )


def _mock_critic_result(score_pass: bool = True) -> AgentResult:
    """构造 CriticAgent 的模拟结果"""
    if score_pass:
        evaluations = [
            {"title": "基于图神经网络的代码漏洞检测方法研究", "score": 82, "novelty": 78, "feasibility": 85},
            {"title": "面向跨项目泛化的GNN漏洞检测框架", "score": 75, "novelty": 70, "feasibility": 80},
            {"title": "基于注意力机制的可解释漏洞检测", "score": 88, "novelty": 90, "feasibility": 75},
            {"title": "基于大语言模型的领域知识问答系统研究", "score": 91, "novelty": 85, "feasibility": 92},
        ]
    else:
        evaluations = [
            {"title": "候选1", "score": 42, "novelty": 40, "feasibility": 45},
            {"title": "候选2", "score": 48, "novelty": 45, "feasibility": 50},
            {"title": "候选3", "score": 50, "novelty": 48, "feasibility": 52},
            {"title": "候选4", "score": 40, "novelty": 38, "feasibility": 42},
        ]
    return AgentResult(
        agent_id="critic",
        success=True,
        content=f"评估完成，平均评分 {sum(e['score'] for e in evaluations) // len(evaluations)}",
        data={"evaluations": evaluations},
    )


def _mock_writer_result() -> AgentResult:
    """构造 WriterAgent 的模拟结果"""
    return AgentResult(
        agent_id="writer",
        success=True,
        content="# 开题报告\n\n## 一、选题背景\n...\n## 二、研究内容\n...",
        data={
            "granularity": "outline",
            "content": "# 开题报告\n\n## 一、选题背景\n...",
            "topic": "基于大语言模型的领域知识问答系统研究",
        },
    )


# ===== 五阶段枚举与门禁定义测试 =====

class TestStageGateDefinitions:
    """五阶段门禁定义测试"""

    def test_five_stages_defined(self):
        """应定义5个阶段门禁"""
        assert len(STAGE_GATES) == 5
        expected_stages = {
            Stage.INFO_CONFIRM,
            Stage.CREATIVITY,
            Stage.VALIDATION,
            Stage.GENERATION,
            Stage.DEEP_ASSIST,
        }
        assert set(STAGE_GATES.keys()) == expected_stages

    def test_info_confirm_gate_requires_user_confirmation(self):
        """信息确权阶段应要求用户确认"""
        gate = STAGE_GATES[Stage.INFO_CONFIRM]
        assert gate.require_user_confirmation is True
        assert gate.name == "信息确权"

    def test_creativity_gate_no_user_confirmation(self):
        """创意阶段不应要求用户确认"""
        gate = STAGE_GATES[Stage.CREATIVITY]
        assert gate.require_user_confirmation is False
        assert gate.name == "谱系解析与四维创意"

    def test_validation_gate_has_min_score(self):
        """校验阶段应有最低评分要求"""
        gate = STAGE_GATES[Stage.VALIDATION]
        assert gate.min_score == 60
        assert gate.retry_on_fail == Stage.CREATIVITY

    def test_generation_gate_exit_condition(self):
        """生成阶段应有退出条件"""
        gate = STAGE_GATES[Stage.GENERATION]
        assert "style_normalizer" in gate.exit_condition

    def test_deep_assist_gate_enter_condition(self):
        """深度辅助阶段应有进入条件"""
        gate = STAGE_GATES[Stage.DEEP_ASSIST]
        assert gate.name == "深度辅助闭环"


# ===== 门禁检查函数测试 =====

class TestCheckGateFunction:
    """check_gate 函数测试"""

    def test_info_confirm_gate_without_user_confirmation(self):
        """信息确权阶段无用户确认时应不通过"""
        result = check_gate(Stage.INFO_CONFIRM, {})
        assert result.passed is False
        assert "等待用户确认" in result.message

    def test_info_confirm_gate_with_user_confirmation(self):
        """信息确权阶段有用户确认时应通过"""
        result = check_gate(Stage.INFO_CONFIRM, {"user_confirmed": True})
        assert result.passed is True
        assert "用户已确认" in result.message

    def test_creativity_gate_with_enough_candidates(self):
        """创意阶段候选数≥3时应通过"""
        candidates = [{"title": "t1"}, {"title": "t2"}, {"title": "t3"}]
        result = check_gate(Stage.CREATIVITY, {"candidates": candidates})
        assert result.passed is True
        assert "3" in result.message

    def test_creativity_gate_with_insufficient_candidates(self):
        """创意阶段候选数<3时应不通过"""
        candidates = [{"title": "t1"}, {"title": "t2"}]
        result = check_gate(Stage.CREATIVITY, {"candidates": candidates})
        assert result.passed is False
        assert "候选不足" in result.message

    def test_validation_gate_with_high_score(self):
        """校验阶段平均分≥60时应通过"""
        evaluations = [{"score": 80}, {"score": 70}]
        result = check_gate(Stage.VALIDATION, {"evaluations": evaluations})
        assert result.passed is True
        assert "75" in result.message

    def test_validation_gate_with_low_score(self):
        """校验阶段平均分<60时应不通过并设置 retry_stage"""
        evaluations = [{"score": 40}, {"score": 50}]
        result = check_gate(Stage.VALIDATION, {"evaluations": evaluations})
        assert result.passed is False
        assert result.retry_stage == Stage.CREATIVITY
        assert "45" in result.message

    def test_validation_gate_without_evaluations(self):
        """校验阶段无评估结果时应不通过"""
        result = check_gate(Stage.VALIDATION, {"evaluations": []})
        assert result.passed is False
        assert "无评估结果" in result.message

    def test_generation_gate_with_content(self):
        """生成阶段有内容时应通过"""
        result = check_gate(Stage.GENERATION, {"content": "生成的开题报告..."})
        assert result.passed is True
        assert "内容生成完成" in result.message

    def test_generation_gate_without_content(self):
        """生成阶段无内容时应不通过"""
        result = check_gate(Stage.GENERATION, {"content": ""})
        assert result.passed is False
        assert "生成内容为空" in result.message

    def test_deep_assist_gate_always_passes(self):
        """深度辅助阶段应总是通过"""
        result = check_gate(Stage.DEEP_ASSIST, {})
        assert result.passed is True

    def test_unknown_stage_returns_failure(self):
        """未知阶段应返回失败"""
        result = check_gate("unknown_stage", {})
        assert result.passed is False
        assert "未知阶段" in result.message


# ===== 状态机转移测试 =====

class TestStateMachineTransitions:
    """状态机转移测试"""

    def test_info_confirm_to_creativity_on_user_confirm(self):
        """信息确权 → 创意（用户确认事件）"""
        result = transition(SMStage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert result.success is True
        assert result.from_stage == SMStage.INFO_CONFIRM
        assert result.to_stage == SMStage.CREATIVITY
        assert result.is_retry is False

    def test_creativity_to_validation_on_candidates_generated(self):
        """创意 → 校验（候选生成完成事件）"""
        result = transition(SMStage.CREATIVITY, Event.CANDIDATES_GENERATED)
        assert result.success is True
        assert result.to_stage == SMStage.VALIDATION

    def test_validation_to_generation_on_score_pass(self):
        """校验 → 生成（评分通过事件）"""
        result = transition(SMStage.VALIDATION, Event.SCORE_PASS)
        assert result.success is True
        assert result.to_stage == SMStage.GENERATION
        assert result.is_retry is False

    def test_validation_to_creativity_on_score_fail(self):
        """校验 → 创意（评分失败事件，回退）"""
        result = transition(SMStage.VALIDATION, Event.SCORE_FAIL)
        assert result.success is True
        assert result.to_stage == SMStage.CREATIVITY
        assert result.is_retry is True

    def test_generation_to_deep_assist_on_generation_done(self):
        """生成 → 深度辅助（生成完成事件）"""
        result = transition(SMStage.GENERATION, Event.GENERATION_DONE)
        assert result.success is True
        assert result.to_stage == SMStage.DEEP_ASSIST

    def test_reset_from_any_stage(self):
        """从任意阶段可重置到信息确权"""
        for stage in SMStage:
            result = transition(stage, Event.RESET)
            assert result.success is True
            assert result.to_stage == SMStage.INFO_CONFIRM

    def test_invalid_transition_rejected(self):
        """非法转移应被拒绝"""
        result = transition(SMStage.INFO_CONFIRM, Event.SCORE_PASS)
        assert result.success is False
        assert "非法转移" in result.message

    def test_get_next_events_for_info_confirm(self):
        """信息确权阶段的可触发事件"""
        events = get_next_events(SMStage.INFO_CONFIRM)
        assert Event.USER_CONFIRM in events

    def test_get_next_events_for_validation(self):
        """校验阶段的可触发事件"""
        events = get_next_events(SMStage.VALIDATION)
        assert Event.SCORE_PASS in events
        assert Event.SCORE_FAIL in events

    def test_is_valid_transition_for_valid(self):
        """合法转移应返回 True"""
        assert is_valid_transition(SMStage.INFO_CONFIRM, Event.USER_CONFIRM) is True

    def test_is_valid_transition_for_invalid(self):
        """非法转移应返回 False"""
        assert is_valid_transition(SMStage.INFO_CONFIRM, Event.SCORE_PASS) is False

    def test_is_valid_transition_for_reset(self):
        """RESET 事件在任意阶段都应合法"""
        for stage in SMStage:
            assert is_valid_transition(stage, Event.RESET) is True


# ===== Orchestrator 五阶段流程测试 =====

class TestOrchestratorFiveStageFlow:
    """Orchestrator 五阶段流程测试"""

    def test_orchestrator_initial_stage(self):
        """Orchestrator 初始阶段应为 info_confirm"""
        orchestrator = OrchestratorAgent()
        assert orchestrator.current_stage == "info_confirm"
        assert orchestrator.get_stage() == "info_confirm"

    def test_orchestrator_has_five_stages(self):
        """Orchestrator 应定义5个阶段"""
        assert len(OrchestratorAgent.STAGES) == 5
        assert "info_confirm" in OrchestratorAgent.STAGES
        assert "creativity" in OrchestratorAgent.STAGES
        assert "validation" in OrchestratorAgent.STAGES
        assert "generation" in OrchestratorAgent.STAGES
        assert "deep_assist" in OrchestratorAgent.STAGES

    def test_confirm_info_advances_to_creativity(self):
        """confirm_info 应推进到创意阶段"""
        orchestrator = OrchestratorAgent()
        result = orchestrator.confirm_info()
        assert result is True
        assert orchestrator.current_stage == "creativity"

    def test_confirm_info_returns_false_when_not_in_info_confirm(self):
        """非 info_confirm 阶段调用 confirm_info 应返回 False"""
        orchestrator = OrchestratorAgent()
        orchestrator.current_stage = "creativity"
        result = orchestrator.confirm_info()
        assert result is False

    def test_reset_returns_to_info_confirm(self):
        """reset 应重置到 info_confirm"""
        orchestrator = OrchestratorAgent()
        orchestrator.current_stage = "generation"
        orchestrator.stage_results = {"some": "data"}
        orchestrator.reset()
        assert orchestrator.current_stage == "info_confirm"
        assert orchestrator.stage_results == {}

    @pytest.mark.asyncio
    async def test_full_five_stage_flow_with_mock(self):
        """完整五阶段流程（Mock AI 调用）"""
        orchestrator = OrchestratorAgent()

        # Mock 子 Agent 的 run 方法
        with patch("backend.agents.agent_registry.get_agent") as mock_get_agent:
            class MockSearcher:
                async def run(self, task_input):
                    return _mock_searcher_result()

            class MockReasoner:
                async def run(self, task_input):
                    return _mock_reasoner_result()

            class MockCritic:
                async def run(self, task_input):
                    return _mock_critic_result(score_pass=True)

            class MockWriter:
                async def run(self, task_input):
                    return _mock_writer_result()

            def get_agent_side_effect(agent_id):
                agents = {
                    "searcher": MockSearcher(),
                    "reasoner": MockReasoner(),
                    "critic": MockCritic(),
                    "writer": MockWriter(),
                }
                return agents.get(agent_id)

            mock_get_agent.side_effect = get_agent_side_effect

            # 执行编排
            chunks = []
            async for chunk in orchestrator.orchestrate("GNN漏洞检测", conversation_id=""):
                chunks.append(chunk)

            # 验证产出的阶段
            stages_seen = [c["stage"] for c in chunks]
            assert "info_confirm" in stages_seen
            assert "creativity" in stages_seen
            assert "validation" in stages_seen
            assert "generation" in stages_seen
            assert "deep_assist" in stages_seen

            # 验证最终阶段
            assert orchestrator.current_stage == "deep_assist"

            # 验证各阶段状态
            for chunk in chunks:
                if chunk.get("status") == "completed":
                    assert chunk["stage"] in OrchestratorAgent.STAGES

    @pytest.mark.asyncio
    async def test_low_score_triggers_retry(self):
        """低评分应触发回退到创意阶段"""
        orchestrator = OrchestratorAgent()

        with patch("backend.agents.agent_registry.get_agent") as mock_get_agent:
            class MockSearcher:
                async def run(self, task_input):
                    return _mock_searcher_result()

            class MockReasoner:
                async def run(self, task_input):
                    return _mock_reasoner_result()

            class MockCritic:
                async def run(self, task_input):
                    return _mock_critic_result(score_pass=False)

            def get_agent_side_effect(agent_id):
                agents = {
                    "searcher": MockSearcher(),
                    "reasoner": MockReasoner(),
                    "critic": MockCritic(),
                }
                return agents.get(agent_id)

            mock_get_agent.side_effect = get_agent_side_effect

            chunks = []
            async for chunk in orchestrator.orchestrate("测试论题", conversation_id=""):
                chunks.append(chunk)

            # 应存在 retry 状态的 chunk
            retry_chunks = [c for c in chunks if c.get("status") == "retry"]
            assert len(retry_chunks) > 0
            assert "回退" in retry_chunks[0]["content"] or "评分" in retry_chunks[0]["content"]

            # 最终阶段应回退到 creativity
            assert orchestrator.current_stage == "creativity"

    @pytest.mark.asyncio
    async def test_stage_results_are_cached(self):
        """各阶段结果应被缓存到 stage_results"""
        orchestrator = OrchestratorAgent()

        with patch("backend.agents.agent_registry.get_agent") as mock_get_agent:
            class MockSearcher:
                async def run(self, task_input):
                    return _mock_searcher_result()

            class MockReasoner:
                async def run(self, task_input):
                    return _mock_reasoner_result()

            class MockCritic:
                async def run(self, task_input):
                    return _mock_critic_result(score_pass=True)

            class MockWriter:
                async def run(self, task_input):
                    return _mock_writer_result()

            def get_agent_side_effect(agent_id):
                agents = {
                    "searcher": MockSearcher(),
                    "reasoner": MockReasoner(),
                    "critic": MockCritic(),
                    "writer": MockWriter(),
                }
                return agents.get(agent_id)

            mock_get_agent.side_effect = get_agent_side_effect

            async for _ in orchestrator.orchestrate("测试", conversation_id=""):
                pass

            # 验证 stage_results 缓存
            assert "info_confirm" in orchestrator.stage_results
            assert "creativity" in orchestrator.stage_results
            assert "validation" in orchestrator.stage_results
            assert "generation" in orchestrator.stage_results

    @pytest.mark.asyncio
    async def test_orchestrator_run_returns_agent_result(self):
        """Orchestrator.run 应返回 AgentResult"""
        orchestrator = OrchestratorAgent()

        with patch("backend.agents.agent_registry.get_agent") as mock_get_agent:
            class MockSearcher:
                async def run(self, task_input):
                    return _mock_searcher_result()

            class MockReasoner:
                async def run(self, task_input):
                    return _mock_reasoner_result()

            class MockCritic:
                async def run(self, task_input):
                    return _mock_critic_result(score_pass=True)

            class MockWriter:
                async def run(self, task_input):
                    return _mock_writer_result()

            def get_agent_side_effect(agent_id):
                agents = {
                    "searcher": MockSearcher(),
                    "reasoner": MockReasoner(),
                    "critic": MockCritic(),
                    "writer": MockWriter(),
                }
                return agents.get(agent_id)

            mock_get_agent.side_effect = get_agent_side_effect

            result = await orchestrator.run({"user_input": "GNN漏洞检测"})

            assert result.success is True
            assert result.agent_id == "orchestrator"
            assert "stages" in result.data
            assert "final_stage" in result.data


# ===== 用户确认门禁测试 =====

class TestUserConfirmationGate:
    """用户确认门禁测试"""

    def test_user_confirmation_advances_stage(self):
        """用户确认应推进阶段"""
        orchestrator = OrchestratorAgent()
        assert orchestrator.current_stage == "info_confirm"

        # 模拟用户确认
        confirmed = orchestrator.confirm_info()
        assert confirmed is True
        assert orchestrator.current_stage == "creativity"

    def test_double_confirmation_returns_false(self):
        """重复确认应返回 False"""
        orchestrator = OrchestratorAgent()
        first = orchestrator.confirm_info()
        second = orchestrator.confirm_info()
        assert first is True
        assert second is False

    def test_check_gate_with_user_confirmed_data(self):
        """check_gate 应识别 user_confirmed 数据"""
        result = check_gate(Stage.INFO_CONFIRM, {"user_confirmed": True})
        assert result.passed is True

    def test_check_gate_without_user_confirmed_data(self):
        """check_gate 无 user_confirmed 数据应不通过"""
        result = check_gate(Stage.INFO_CONFIRM, {})
        assert result.passed is False


# ===== 真实 DB 集成测试 =====

class TestRealDBIntegration:
    """真实 DB 集成测试"""

    def test_create_session_for_five_stage(self):
        """为五阶段流程创建会话"""
        sid = _make_session("五阶段DB测试")
        assert sid is not None
        session = session_manager.get_session(sid)
        assert session is not None
        assert session["title"] == "五阶段DB测试"
        assert session["status"] == "active"

    def test_session_has_default_conversation(self):
        """会话应自动创建默认对话"""
        sid = _make_session("默认对话测试")
        session = session_manager.get_session(sid)
        assert session.get("conversations") is not None
        assert len(session["conversations"]) >= 1
        assert session.get("active_conversation_id") is not None

    def test_orchestrator_reset_clears_stage_results(self):
        """Orchestrator reset 应清空 stage_results"""
        orchestrator = OrchestratorAgent()
        orchestrator.stage_results = {"info_confirm": "data", "creativity": "data"}
        orchestrator.current_stage = "generation"
        orchestrator.reset()
        assert orchestrator.stage_results == {}
        assert orchestrator.current_stage == "info_confirm"

    def test_stage_gate_definitions_match_orchestrator(self):
        """门禁定义应与 Orchestrator 阶段一致"""
        for stage in OrchestratorAgent.STAGES:
            stage_enum = Stage(stage)
            assert stage_enum in STAGE_GATES

    def test_five_stage_order_in_orchestrator(self):
        """Orchestrator 阶段顺序应正确"""
        expected_order = ["info_confirm", "creativity", "validation", "generation", "deep_assist"]
        assert OrchestratorAgent.STAGES == expected_order

    def test_transition_table_covers_all_stages(self):
        """状态转移表应覆盖所有阶段"""
        stages_in_transitions = set()
        for (from_stage, event) in TRANSITIONS.keys():
            stages_in_transitions.add(from_stage)
        # 至少应包含4个阶段（deep_assist 只有 RESET，不在 TRANSITIONS 中）
        assert len(stages_in_transitions) >= 4

    def test_session_persists_after_creation(self):
        """会话应在创建后持久化"""
        sid = _make_session("持久化测试")
        # 重新查询验证持久化
        session = session_manager.get_session(sid)
        assert session is not None
        assert session["id"] == sid

    def test_multiple_sessions_coexist(self):
        """多个会话应能共存"""
        sid1 = _make_session("会话1")
        sid2 = _make_session("会话2")
        sid3 = _make_session("会话3")
        assert sid1 != sid2 != sid3
        sessions = session_manager.list_sessions(limit=100)
        ids = [s["id"] for s in sessions]
        assert sid1 in ids
        assert sid2 in ids
        assert sid3 in ids


# ===== 阶段流转综合测试 =====

class TestStageFlowIntegration:
    """阶段流转综合测试"""

    def test_full_transition_sequence(self):
        """完整阶段转移序列"""
        # info_confirm → creativity
        r1 = transition(SMStage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert r1.success and r1.to_stage == SMStage.CREATIVITY

        # creativity → validation
        r2 = transition(SMStage.CREATIVITY, Event.CANDIDATES_GENERATED)
        assert r2.success and r2.to_stage == SMStage.VALIDATION

        # validation → generation
        r3 = transition(SMStage.VALIDATION, Event.SCORE_PASS)
        assert r3.success and r3.to_stage == SMStage.GENERATION

        # generation → deep_assist
        r4 = transition(SMStage.GENERATION, Event.GENERATION_DONE)
        assert r4.success and r4.to_stage == SMStage.DEEP_ASSIST

    def test_retry_transition_sequence(self):
        """回退转移序列"""
        # info_confirm → creativity
        r1 = transition(SMStage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert r1.to_stage == SMStage.CREATIVITY

        # creativity → validation
        r2 = transition(SMStage.CREATIVITY, Event.CANDIDATES_GENERATED)
        assert r2.to_stage == SMStage.VALIDATION

        # validation → creativity (retry)
        r3 = transition(SMStage.VALIDATION, Event.SCORE_FAIL)
        assert r3.to_stage == SMStage.CREATIVITY
        assert r3.is_retry is True

    def test_reset_after_completion(self):
        """完成后重置流程"""
        # 完成五阶段
        stage = SMStage.INFO_CONFIRM
        stage = transition(stage, Event.USER_CONFIRM).to_stage
        stage = transition(stage, Event.CANDIDATES_GENERATED).to_stage
        stage = transition(stage, Event.SCORE_PASS).to_stage
        stage = transition(stage, Event.GENERATION_DONE).to_stage
        assert stage == SMStage.DEEP_ASSIST

        # 重置
        reset_result = transition(stage, Event.RESET)
        assert reset_result.to_stage == SMStage.INFO_CONFIRM

    def test_gate_check_at_each_stage(self):
        """每个阶段的门禁检查"""
        # info_confirm: 需用户确认
        assert check_gate(Stage.INFO_CONFIRM, {}).passed is False
        assert check_gate(Stage.INFO_CONFIRM, {"user_confirmed": True}).passed is True

        # creativity: 需≥3个候选
        assert check_gate(Stage.CREATIVITY, {"candidates": []}).passed is False
        assert check_gate(Stage.CREATIVITY, {"candidates": [1, 2, 3]}).passed is True

        # validation: 需平均分≥60
        assert check_gate(Stage.VALIDATION, {"evaluations": [{"score": 50}]}).passed is False
        assert check_gate(Stage.VALIDATION, {"evaluations": [{"score": 80}]}).passed is True

        # generation: 需内容非空
        assert check_gate(Stage.GENERATION, {"content": ""}).passed is False
        assert check_gate(Stage.GENERATION, {"content": "内容"}).passed is True

        # deep_assist: 总是通过
        assert check_gate(Stage.DEEP_ASSIST, {}).passed is True

    def test_orchestrator_stage_progression_with_gates(self):
        """Orchestrator 阶段推进与门禁配合"""
        orchestrator = OrchestratorAgent()
        assert orchestrator.get_stage() == "info_confirm"

        # 门禁检查：info_confirm 需用户确认
        gate_result = check_gate(Stage.INFO_CONFIRM, {})
        assert gate_result.passed is False

        # 用户确认
        orchestrator.confirm_info()
        assert orchestrator.get_stage() == "creativity"

        # 门禁检查：creativity 需≥3个候选
        gate_result = check_gate(Stage.CREATIVITY, {"candidates": [1, 2, 3]})
        assert gate_result.passed is True
