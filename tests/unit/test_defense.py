"""答辩准备助手 Agent 单元测试（Task 10 / v9.0）

测试 backend/agents/defense_agent.py 的 DefenseAgent：
  - 初始化与属性
  - generate_defense_ppt 答辩 PPT 大纲生成
  - generate_questions 答辩问题生成
  - simulate_defense 模拟答辩
  - generate_defense_speech 答辩话术生成
  - evaluate_answer 回答评估
  - run 统一入口

测试 backend/routes/defense.py 的 API 端点：
  - PPT / questions / simulate / speech / evaluate
  - 400 错误（未配置 API Key / 缺失字段）

所有 LLM 调用均被 mock，不发起真实 API 请求。
"""
import asyncio
import json
import os
import sys
import tempfile
import uuid
from unittest.mock import AsyncMock, patch

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ===== 临时数据库初始化（必须在导入 main 之前） =====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_defense_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

# 重置 Settings 单例以使用新数据库
import backend.config as _config_module
_config_module._settings_instance = None

from backend.agents.base_agent import AgentResult
from backend.agents.defense_agent import (
    DefenseAgent,
    _normalize_degree,
    _degree_label,
    _format_chapters,
)


# ===== 辅助函数 =====


def _run_async(coro):
    """辅助函数：运行异步协程。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_llm_result(
    content="# 生成的答辩内容\n\n## 第1页 封面\n这是模拟的答辩内容。",
    prompt_tokens=100,
    completion_tokens=200,
):
    """构造模拟的 call_llm 返回值。"""
    return {
        "content": content,
        "model": "mock-model",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cached_tokens": 0,
        "cost": 0.0,
        "citations": [],
    }


def _mock_questions_llm_result():
    """构造模拟的答辩问题 LLM 返回值（JSON 数组）。"""
    questions_json = json.dumps([
        {
            "question": "请简述你论文的核心研究问题是什么？",
            "category": "研究动机",
            "difficulty": "basic",
            "suggested_answer_points": [
                "明确研究问题的来源与背景",
                "说明该问题的研究意义",
            ],
        },
        {
            "question": "你的方法相比现有工作有哪些创新？",
            "category": "方法论",
            "difficulty": "intermediate",
            "suggested_answer_points": [
                "对比现有方法的局限性",
                "阐述本方法的创新点",
                "给出理论或实验支撑",
            ],
        },
        {
            "question": "实验结果是否具有统计显著性？如何证明？",
            "category": "实验结果",
            "difficulty": "challenging",
            "suggested_answer_points": [
                "说明显著性检验方法",
                "给出 p 值或置信区间",
            ],
        },
    ], ensure_ascii=False)
    return _mock_llm_result(content=questions_json)


def _mock_evaluate_llm_result():
    """构造模拟的回答评估 LLM 返回值（JSON）。"""
    evaluate_json = json.dumps({
        "score": 78,
        "strengths": [
            "回答结构清晰，逻辑连贯",
            "正确引用了论文中的实验数据",
        ],
        "weaknesses": [
            "对方法创新点的阐述不够深入",
            "缺少与现有工作的对比",
        ],
        "suggestions": [
            "补充方法创新点的具体技术细节",
            "增加与基线方法的定量对比",
        ],
        "model_answer": "针对该问题，本研究通过引入XX机制解决了YY问题。"
        "实验结果表明，本方法在ZZ指标上提升了15%，"
        "相比基线方法具有显著优势。",
    }, ensure_ascii=False)
    return _mock_llm_result(content=evaluate_json)


# ============================================================
# 第一部分：初始化测试
# ============================================================


class TestDefenseAgentInit:
    """DefenseAgent 初始化测试。"""

    def test_init_agent_id(self):
        """测试：agent_id 为 defense_agent。"""
        agent = DefenseAgent()
        assert agent.agent_id == "defense_agent"

    def test_init_name(self):
        """测试：name 为答辩准备助手。"""
        agent = DefenseAgent()
        assert agent.name == "答辩准备助手"

    def test_init_description(self):
        """测试：description 包含答辩关键词。"""
        agent = DefenseAgent()
        assert "答辩" in agent.description

    def test_init_has_system_prompt(self):
        """测试：有系统提示且为中文。"""
        agent = DefenseAgent()
        assert len(agent.system_prompt) > 0
        assert "答辩" in agent.system_prompt

    def test_init_temperature(self):
        """测试：temperature 为 0.6。"""
        agent = DefenseAgent()
        assert agent.temperature == 0.6

    def test_init_max_tokens(self):
        """测试：max_tokens 为 8192。"""
        agent = DefenseAgent()
        assert agent.max_tokens == 8192

    def test_init_capabilities(self):
        """测试：capabilities 包含 streaming。"""
        agent = DefenseAgent()
        assert "streaming" in agent.capabilities

    def test_init_messages_has_system(self):
        """测试：messages 初始化包含系统提示。"""
        agent = DefenseAgent()
        assert len(agent.messages) >= 1
        assert agent.messages[0]["role"] == "system"


# ============================================================
# 第二部分：辅助函数测试
# ============================================================


class TestDefenseHelpers:
    """辅助函数测试。"""

    def test_normalize_bachelor_english(self):
        assert _normalize_degree("bachelor") == "bachelor"

    def test_normalize_bachelor_chinese(self):
        assert _normalize_degree("本科") == "bachelor"

    def test_normalize_master_english(self):
        assert _normalize_degree("master") == "master"

    def test_normalize_master_chinese(self):
        assert _normalize_degree("硕士") == "master"

    def test_normalize_doctor_english(self):
        assert _normalize_degree("doctor") == "doctor"

    def test_normalize_doctor_chinese(self):
        assert _normalize_degree("博士") == "doctor"

    def test_normalize_empty_falls_back_to_master(self):
        assert _normalize_degree("") == "master"

    def test_degree_label_bachelor(self):
        assert _degree_label("bachelor") == "本科"

    def test_degree_label_master(self):
        assert _degree_label("master") == "硕士"

    def test_degree_label_doctor(self):
        assert _degree_label("doctor") == "博士"

    def test_format_chapters_empty(self):
        """测试：空章节列表返回占位文本。"""
        result = _format_chapters([])
        assert "未提供" in result

    def test_format_chapters_strings(self):
        """测试：字符串章节列表格式化。"""
        result = _format_chapters(["第一章 绪论", "第二章 方法"])
        assert "第一章 绪论" in result
        assert "第二章 方法" in result

    def test_format_chapters_dicts(self):
        """测试：字典章节列表格式化。"""
        result = _format_chapters([
            {"title": "第一章", "content": "背景介绍"},
            {"title": "第二章", "content": "方法设计"},
        ])
        assert "第一章" in result
        assert "背景介绍" in result


# ============================================================
# 第三部分：generate_defense_ppt 测试
# ============================================================


class TestGenerateDefensePpt:
    """generate_defense_ppt 方法测试。"""

    def test_ppt_returns_non_empty_string(self):
        """测试：PPT 大纲返回非空字符串。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(
                "# 答辩 PPT 大纲\n## 第1页 封面\n- 论文题目\n> 讲稿内容"
            )
            result = _run_async(agent.generate_defense_ppt(
                thesis_title="基于深度学习的论文挖掘",
                chapters=["第一章 绪论", "第二章 方法"],
                degree="master",
            ))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_ppt_has_slide_structure(self):
        """测试：PPT 大纲包含分页结构。"""
        agent = DefenseAgent()
        ppt_content = (
            "# 答辩 PPT 大纲\n\n"
            "## 第1页 封面\n- 论文题目\n> 讲稿\n\n"
            "## 第2页 研究背景\n- 背景\n> 讲稿"
        )
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content=ppt_content)
            result = _run_async(agent.generate_defense_ppt(
                thesis_title="论文题目",
                chapters=["章节1"],
                degree="master",
            ))
        assert "第1页" in result or "第2页" in result or "##" in result

    def test_ppt_bachelor(self):
        """测试：本科学位 PPT 生成。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("# 本科答辩 PPT\n## 第1页")
            result = _run_async(agent.generate_defense_ppt(
                thesis_title="题目",
                chapters=["章节"],
                degree="本科",
            ))
        assert len(result) > 0
        assert mock_llm.called

    def test_ppt_doctor(self):
        """测试：博士学位 PPT 生成。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("# 博士答辩 PPT\n## 第1页")
            result = _run_async(agent.generate_defense_ppt(
                thesis_title="题目",
                chapters=["章节"],
                degree="博士",
            ))
        assert len(result) > 0

    def test_ppt_empty_llm_response_uses_fallback(self):
        """测试：LLM 返回空内容时使用兜底大纲。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="")
            result = _run_async(agent.generate_defense_ppt(
                thesis_title="题目",
                chapters=["章节"],
                degree="master",
            ))
        assert len(result) > 0
        assert "#" in result  # Markdown 标题

    def test_ppt_prompt_contains_degree_label(self):
        """测试：提示包含学位标签。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            _run_async(agent.generate_defense_ppt(
                thesis_title="题目",
                chapters=["章节"],
                degree="博士",
            ))
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        assert "博士" in user_prompt

    def test_ppt_prompt_contains_thesis_title(self):
        """测试：提示包含论文标题。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            _run_async(agent.generate_defense_ppt(
                thesis_title="基于深度学习的研究",
                chapters=["章节"],
                degree="master",
            ))
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        assert "基于深度学习的研究" in user_prompt


# ============================================================
# 第四部分：generate_questions 测试
# ============================================================


class TestGenerateQuestions:
    """generate_questions 方法测试。"""

    def test_questions_returns_list(self):
        """测试：问题返回列表。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_questions_llm_result()
            result = _run_async(agent.generate_questions(
                thesis_title="论文题目",
                chapters=["章节1", "章节2"],
                degree="master",
            ))
        assert isinstance(result, list)
        assert len(result) > 0

    def test_questions_has_required_fields(self):
        """测试：每个问题包含必需字段。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_questions_llm_result()
            result = _run_async(agent.generate_questions(
                thesis_title="论文题目",
                chapters=["章节"],
                degree="master",
            ))
        for q in result:
            assert "question" in q
            assert "category" in q
            assert "difficulty" in q
            assert "suggested_answer_points" in q

    def test_questions_difficulty_valid(self):
        """测试：难度字段取值合法。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_questions_llm_result()
            result = _run_async(agent.generate_questions(
                thesis_title="论文题目",
                chapters=["章节"],
                degree="master",
            ))
        valid = {"basic", "intermediate", "challenging"}
        for q in result:
            assert q["difficulty"] in valid

    def test_questions_answer_points_is_list(self):
        """测试：建议回答要点为列表。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_questions_llm_result()
            result = _run_async(agent.generate_questions(
                thesis_title="论文题目",
                chapters=["章节"],
                degree="master",
            ))
        for q in result:
            assert isinstance(q["suggested_answer_points"], list)

    def test_questions_invalid_json_returns_empty(self):
        """测试：LLM 返回非 JSON 时返回空列表。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="这不是JSON")
            result = _run_async(agent.generate_questions(
                thesis_title="题目",
                chapters=["章节"],
                degree="master",
            ))
        assert result == []

    def test_questions_json_in_code_block(self):
        """测试：JSON 包裹在代码块中可解析。"""
        agent = DefenseAgent()
        json_content = (
            "```json\n"
            '[{"question": "问题1", "category": "动机", "difficulty": "basic", '
            '"suggested_answer_points": ["要点1"]}]\n'
            "```"
        )
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content=json_content)
            result = _run_async(agent.generate_questions(
                thesis_title="题目",
                chapters=["章节"],
                degree="master",
            ))
        assert len(result) == 1
        assert result[0]["question"] == "问题1"

    def test_questions_empty_llm_response_returns_empty(self):
        """测试：LLM 返回空内容时返回空列表。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="")
            result = _run_async(agent.generate_questions(
                thesis_title="题目",
                chapters=["章节"],
                degree="master",
            ))
        assert result == []

    def test_questions_custom_num(self):
        """测试：自定义问题数量。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_questions_llm_result()
            _run_async(agent.generate_questions(
                thesis_title="题目",
                chapters=["章节"],
                degree="master",
                num_questions=15,
            ))
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        assert "15" in user_prompt


# ============================================================
# 第五部分：simulate_defense 测试
# ============================================================


class TestSimulateDefense:
    """simulate_defense 方法测试。"""

    def test_simulate_returns_non_empty_string(self):
        """测试：模拟答辩返回非空字符串。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(
                "针对该问题，本研究通过引入XX机制解决了YY问题。"
                "实验结果表明本方法具有显著优势。"
            )
            result = _run_async(agent.simulate_defense(
                question="你的方法有哪些创新？",
                thesis_content="论文内容摘要",
            ))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_simulate_empty_llm_response_uses_fallback(self):
        """测试：LLM 返回空内容时使用兜底。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="")
            result = _run_async(agent.simulate_defense(
                question="你的方法有哪些创新？",
                thesis_content="论文内容",
            ))
        assert len(result) > 0

    def test_simulate_prompt_contains_question(self):
        """测试：提示包含问题。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            _run_async(agent.simulate_defense(
                question="请解释你的核心算法",
                thesis_content="论文内容",
            ))
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        assert "请解释你的核心算法" in user_prompt


# ============================================================
# 第六部分：generate_defense_speech 测试
# ============================================================


class TestGenerateDefenseSpeech:
    """generate_defense_speech 方法测试。"""

    def test_speech_returns_non_empty_string(self):
        """测试：答辩话术返回非空字符串。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(
                "## 开场问候\n各位评委老师大家好\n## 研究背景\n..."
            )
            result = _run_async(agent.generate_defense_speech(
                thesis_title="论文题目",
                chapters=["章节1"],
                degree="master",
                duration_minutes=10,
            ))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_speech_empty_llm_response_uses_fallback(self):
        """测试：LLM 返回空内容时使用兜底。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="")
            result = _run_async(agent.generate_defense_speech(
                thesis_title="论文题目",
                chapters=["章节"],
                degree="master",
                duration_minutes=10,
            ))
        assert len(result) > 0
        assert "开场" in result or "问候" in result

    def test_speech_prompt_contains_duration(self):
        """测试：提示包含演讲时长。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            _run_async(agent.generate_defense_speech(
                thesis_title="题目",
                chapters=["章节"],
                degree="master",
                duration_minutes=15,
            ))
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        assert "15" in user_prompt

    def test_speech_prompt_contains_thesis_title(self):
        """测试：提示包含论文标题。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            _run_async(agent.generate_defense_speech(
                thesis_title="基于AI的研究",
                chapters=["章节"],
                degree="master",
            ))
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        assert "基于AI的研究" in user_prompt


# ============================================================
# 第七部分：evaluate_answer 测试
# ============================================================


class TestEvaluateAnswer:
    """evaluate_answer 方法测试。"""

    def test_evaluate_returns_dict(self):
        """测试：评估返回字典。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_evaluate_llm_result()
            result = _run_async(agent.evaluate_answer(
                answer="用户的回答内容",
                question="你的方法有哪些创新？",
                thesis_content="论文内容",
            ))
        assert isinstance(result, dict)

    def test_evaluate_has_score(self):
        """测试：结果包含 score。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_evaluate_llm_result()
            result = _run_async(agent.evaluate_answer(
                answer="回答",
                question="问题",
                thesis_content="内容",
            ))
        assert "score" in result

    def test_evaluate_has_strengths(self):
        """测试：结果包含 strengths。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_evaluate_llm_result()
            result = _run_async(agent.evaluate_answer(
                answer="回答",
                question="问题",
                thesis_content="内容",
            ))
        assert "strengths" in result
        assert isinstance(result["strengths"], list)

    def test_evaluate_has_weaknesses(self):
        """测试：结果包含 weaknesses。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_evaluate_llm_result()
            result = _run_async(agent.evaluate_answer(
                answer="回答",
                question="问题",
                thesis_content="内容",
            ))
        assert "weaknesses" in result
        assert isinstance(result["weaknesses"], list)

    def test_evaluate_has_suggestions(self):
        """测试：结果包含 suggestions。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_evaluate_llm_result()
            result = _run_async(agent.evaluate_answer(
                answer="回答",
                question="问题",
                thesis_content="内容",
            ))
        assert "suggestions" in result
        assert isinstance(result["suggestions"], list)

    def test_evaluate_has_model_answer(self):
        """测试：结果包含 model_answer。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_evaluate_llm_result()
            result = _run_async(agent.evaluate_answer(
                answer="回答",
                question="问题",
                thesis_content="内容",
            ))
        assert "model_answer" in result
        assert isinstance(result["model_answer"], str)

    def test_evaluate_score_in_range(self):
        """测试：评分在 0-100 范围内。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_evaluate_llm_result()
            result = _run_async(agent.evaluate_answer(
                answer="回答",
                question="问题",
                thesis_content="内容",
            ))
        assert 0 <= result["score"] <= 100

    def test_evaluate_invalid_json_returns_fallback(self):
        """测试：LLM 返回非 JSON 时返回兜底结果。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="这不是JSON")
            result = _run_async(agent.evaluate_answer(
                answer="回答",
                question="问题",
                thesis_content="内容",
            ))
        assert result["score"] == 0
        assert result["strengths"] == []
        assert result["weaknesses"] == []
        assert result["suggestions"] == []

    def test_evaluate_json_in_code_block(self):
        """测试：JSON 包裹在代码块中可解析。"""
        agent = DefenseAgent()
        json_content = (
            "```json\n"
            '{"score": 85, "strengths": ["优点1"], "weaknesses": ["不足1"], '
            '"suggestions": ["建议1"], "model_answer": "参考答案"}\n'
            "```"
        )
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content=json_content)
            result = _run_async(agent.evaluate_answer(
                answer="回答",
                question="问题",
                thesis_content="内容",
            ))
        assert result["score"] == 85
        assert "优点1" in result["strengths"]


# ============================================================
# 第八部分：run 统一入口测试
# ============================================================


class TestRun:
    """run 方法统一入口测试。"""

    def test_run_ppt_action(self):
        """测试：run 执行 ppt 动作。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("# PPT 大纲")
            result = _run_async(agent.run({
                "action": "ppt",
                "thesis_title": "题目",
                "chapters": ["章节"],
                "degree": "master",
            }))
        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.agent_id == "defense_agent"

    def test_run_questions_action(self):
        """测试：run 执行 questions 动作。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_questions_llm_result()
            result = _run_async(agent.run({
                "action": "questions",
                "thesis_title": "题目",
                "chapters": ["章节"],
                "degree": "master",
                "num_questions": 10,
            }))
        assert result.success is True
        assert isinstance(result.data["questions"], list)

    def test_run_simulate_action(self):
        """测试：run 执行 simulate 动作。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("模拟回答内容")
            result = _run_async(agent.run({
                "action": "simulate",
                "question": "问题",
                "thesis_content": "内容",
            }))
        assert result.success is True

    def test_run_speech_action(self):
        """测试：run 执行 speech 动作。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 开场白\n各位老师好")
            result = _run_async(agent.run({
                "action": "speech",
                "thesis_title": "题目",
                "chapters": ["章节"],
                "degree": "master",
                "duration_minutes": 10,
            }))
        assert result.success is True

    def test_run_evaluate_action(self):
        """测试：run 执行 evaluate 动作。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_evaluate_llm_result()
            result = _run_async(agent.run({
                "action": "evaluate",
                "answer": "回答",
                "question": "问题",
                "thesis_content": "内容",
            }))
        assert result.success is True
        assert isinstance(result.data["result"], dict)

    def test_run_unknown_action_returns_failure(self):
        """测试：未知 action 返回失败。"""
        agent = DefenseAgent()
        result = _run_async(agent.run({"action": "unknown"}))
        assert result.success is False

    def test_run_llm_exception_returns_failure(self):
        """测试：LLM 异常时返回失败结果。"""
        agent = DefenseAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 不可用")
            result = _run_async(agent.run({
                "action": "ppt",
                "thesis_title": "题目",
                "chapters": ["章节"],
                "degree": "master",
            }))
        assert result.success is False


# ============================================================
# 第九部分：兜底方法测试
# ============================================================


class TestFallbacks:
    """兜底生成方法测试。"""

    def test_ppt_fallback_master(self):
        """测试：硕士 PPT 兜底。"""
        result = DefenseAgent._ppt_fallback("论文题目", "硕士")
        assert "#" in result
        assert "硕士" in result
        assert "论文题目" in result

    def test_ppt_fallback_has_slides(self):
        """测试：PPT 兜底包含分页。"""
        result = DefenseAgent._ppt_fallback("题目", "硕士")
        assert "第1页" in result or "第10页" in result

    def test_simulate_fallback(self):
        """测试：模拟答辩兜底。"""
        result = DefenseAgent._simulate_fallback("测试问题")
        assert "测试问题" in result
        assert len(result) > 0

    def test_speech_fallback(self):
        """测试：答辩话术兜底。"""
        result = DefenseAgent._speech_fallback("论文题目", "硕士", 10)
        assert "开场" in result or "问候" in result
        assert "论文题目" in result


# ============================================================
# 第十部分：API 端点测试
# ============================================================


# 导入 FastAPI 应用（在数据库初始化之后）
from fastapi.testclient import TestClient
from main import app


def _insert_session(session_id: str = None, title: str = "测试会话") -> str:
    """向 sessions 表插入一条记录以满足外键约束。"""
    from backend.database import get_db_connection
    sid = session_id or f"test-session-{uuid.uuid4().hex[:12]}"
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at)
               VALUES (?, ?, datetime('now'), datetime('now'))""",
            (sid, title),
        )
        conn.commit()
    finally:
        conn.close()
    return sid


class TestDefenseAPIEndpoints:
    """答辩准备 API 端点测试。"""

    def test_ppt_endpoint_success(self):
        """测试：POST /api/defense/{sid}/ppt 成功。"""
        sid = _insert_session()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("# 答辩 PPT 大纲")
            with patch("backend.routes.defense.check_api_configured", return_value=True):
                with TestClient(app) as client:
                    resp = client.post(f"/api/defense/{sid}/ppt", json={
                        "thesis_title": "论文题目",
                        "chapters": ["第一章", "第二章"],
                        "degree": "master",
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "ppt" in data
        assert len(data["ppt"]) > 0

    def test_ppt_endpoint_no_api_key(self):
        """测试：未配置 API Key 返回 400。"""
        sid = _insert_session()
        with patch("backend.routes.defense.check_api_configured", return_value=False):
            with TestClient(app) as client:
                resp = client.post(f"/api/defense/{sid}/ppt", json={
                    "thesis_title": "题目",
                    "chapters": [],
                    "degree": "master",
                })
        assert resp.status_code == 400

    def test_questions_endpoint_success(self):
        """测试：POST /api/defense/{sid}/questions 成功。"""
        sid = _insert_session()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_questions_llm_result()
            with patch("backend.routes.defense.check_api_configured", return_value=True):
                with TestClient(app) as client:
                    resp = client.post(f"/api/defense/{sid}/questions", json={
                        "thesis_title": "论文题目",
                        "chapters": ["章节"],
                        "degree": "master",
                        "num_questions": 10,
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "questions" in data
        assert isinstance(data["questions"], list)
        assert len(data["questions"]) > 0

    def test_questions_endpoint_no_api_key(self):
        """测试：未配置 API Key 返回 400。"""
        sid = _insert_session()
        with patch("backend.routes.defense.check_api_configured", return_value=False):
            with TestClient(app) as client:
                resp = client.post(f"/api/defense/{sid}/questions", json={
                    "thesis_title": "题目",
                    "chapters": [],
                    "degree": "master",
                })
        assert resp.status_code == 400

    def test_simulate_endpoint_success(self):
        """测试：POST /api/defense/{sid}/simulate 成功。"""
        sid = _insert_session()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("模拟答辩回答内容")
            with patch("backend.routes.defense.check_api_configured", return_value=True):
                with TestClient(app) as client:
                    resp = client.post(f"/api/defense/{sid}/simulate", json={
                        "question": "你的方法有哪些创新？",
                        "thesis_content": "论文内容",
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 0

    def test_simulate_endpoint_no_api_key(self):
        """测试：未配置 API Key 返回 400。"""
        sid = _insert_session()
        with patch("backend.routes.defense.check_api_configured", return_value=False):
            with TestClient(app) as client:
                resp = client.post(f"/api/defense/{sid}/simulate", json={
                    "question": "问题",
                    "thesis_content": "内容",
                })
        assert resp.status_code == 400

    def test_speech_endpoint_success(self):
        """测试：POST /api/defense/{sid}/speech 成功。"""
        sid = _insert_session()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 开场问候\n各位评委老师好")
            with patch("backend.routes.defense.check_api_configured", return_value=True):
                with TestClient(app) as client:
                    resp = client.post(f"/api/defense/{sid}/speech", json={
                        "thesis_title": "论文题目",
                        "chapters": ["章节"],
                        "degree": "master",
                        "duration_minutes": 10,
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "speech" in data
        assert len(data["speech"]) > 0

    def test_speech_endpoint_no_api_key(self):
        """测试：未配置 API Key 返回 400。"""
        sid = _insert_session()
        with patch("backend.routes.defense.check_api_configured", return_value=False):
            with TestClient(app) as client:
                resp = client.post(f"/api/defense/{sid}/speech", json={
                    "thesis_title": "题目",
                    "chapters": [],
                    "degree": "master",
                })
        assert resp.status_code == 400

    def test_evaluate_endpoint_success(self):
        """测试：POST /api/defense/{sid}/evaluate 成功。"""
        sid = _insert_session()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_evaluate_llm_result()
            with patch("backend.routes.defense.check_api_configured", return_value=True):
                with TestClient(app) as client:
                    resp = client.post(f"/api/defense/{sid}/evaluate", json={
                        "answer": "用户回答",
                        "question": "问题",
                        "thesis_content": "论文内容",
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "score" in data["result"]
        assert "strengths" in data["result"]

    def test_evaluate_endpoint_no_api_key(self):
        """测试：未配置 API Key 返回 400。"""
        sid = _insert_session()
        with patch("backend.routes.defense.check_api_configured", return_value=False):
            with TestClient(app) as client:
                resp = client.post(f"/api/defense/{sid}/evaluate", json={
                    "answer": "回答",
                    "question": "问题",
                    "thesis_content": "内容",
                })
        assert resp.status_code == 400

    def test_ppt_endpoint_missing_body_returns_422(self):
        """测试：PPT 端点缺少请求体返回 422。"""
        sid = _insert_session()
        with patch("backend.routes.defense.check_api_configured", return_value=True):
            with TestClient(app) as client:
                resp = client.post(f"/api/defense/{sid}/ppt")
        assert resp.status_code == 422
