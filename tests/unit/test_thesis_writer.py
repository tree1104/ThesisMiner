"""论文撰写助手 Agent 单元测试（Task 9 / v9.0）

测试 backend/agents/thesis_writer.py 的 ThesisWriterAgent：
  - 初始化与属性
  - generate_outline 大纲生成（各学位层次）
  - write_chapter 章节撰写
  - revise_chapter 章节修订
  - check_plagiarism 查重检测
  - reduce_similarity 降重改写
  - run 统一入口

测试 backend/database.py 的论文章节 CRUD：
  - save_chapter / get_chapter / list_chapters / update_chapter / delete_chapter

测试 backend/routes/thesis.py 的 API 端点：
  - 大纲生成、章节撰写、修订、查重、降重
  - 章节 CRUD（GET/POST/PUT/DELETE）

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
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_thesis_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

# 重置 Settings 单例以使用新数据库
import backend.config as _config_module
_config_module._settings_instance = None

from backend.agents.base_agent import AgentResult
from backend.agents.thesis_writer import (
    ThesisWriterAgent,
    _normalize_degree,
    _degree_label,
)
from backend.database import (
    save_chapter,
    get_chapter,
    list_chapters,
    update_chapter,
    delete_chapter,
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
    content="# 生成的论文内容\n\n## 第一章 绪论\n\n这是模拟的学术内容[1]。",
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


def _mock_plagiarism_llm_result():
    """构造模拟的查重 LLM 返回值（JSON 格式）。"""
    plagiarism_json = json.dumps({
        "similarity_score": 35.5,
        "high_risk_sections": [
            "2.1 相关工作定义部分存在连续表述风险",
            "3.2 算法描述与文献原文高度相似",
        ],
        "suggestions": [
            "将定义部分改写为自己的语言表述",
            "对算法描述进行句式重构，调整语序",
        ],
    }, ensure_ascii=False)
    return _mock_llm_result(content=plagiarism_json)


# ============================================================
# 第一部分：初始化测试
# ============================================================


class TestThesisWriterInit:
    """ThesisWriterAgent 初始化测试。"""

    def test_init_agent_id(self):
        """测试：agent_id 为 thesis_writer。"""
        agent = ThesisWriterAgent()
        assert agent.agent_id == "thesis_writer"

    def test_init_name(self):
        """测试：name 为论文撰写助手。"""
        agent = ThesisWriterAgent()
        assert agent.name == "论文撰写助手"

    def test_init_description(self):
        """测试：description 包含撰写关键词。"""
        agent = ThesisWriterAgent()
        assert "撰写" in agent.description

    def test_init_has_system_prompt(self):
        """测试：有系统提示且为中文。"""
        agent = ThesisWriterAgent()
        assert len(agent.system_prompt) > 0
        assert "学术" in agent.system_prompt or "论文" in agent.system_prompt

    def test_init_temperature(self):
        """测试：temperature 为 0.6。"""
        agent = ThesisWriterAgent()
        assert agent.temperature == 0.6

    def test_init_max_tokens(self):
        """测试：max_tokens 为 8192。"""
        agent = ThesisWriterAgent()
        assert agent.max_tokens == 8192

    def test_init_capabilities(self):
        """测试：capabilities 包含 streaming。"""
        agent = ThesisWriterAgent()
        assert "streaming" in agent.capabilities

    def test_init_messages_has_system(self):
        """测试：messages 初始化包含系统提示。"""
        agent = ThesisWriterAgent()
        assert len(agent.messages) >= 1
        assert agent.messages[0]["role"] == "system"


# ============================================================
# 第二部分：辅助函数测试
# ============================================================


class TestDegreeHelpers:
    """学位规范化辅助函数测试。"""

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

    def test_normalize_doctor_phd(self):
        assert _normalize_degree("phd") == "doctor"

    def test_normalize_empty_falls_back_to_master(self):
        assert _normalize_degree("") == "master"

    def test_normalize_unknown_falls_back_to_master(self):
        assert _normalize_degree("unknown") == "master"

    def test_degree_label_bachelor(self):
        assert _degree_label("bachelor") == "本科"

    def test_degree_label_master(self):
        assert _degree_label("master") == "硕士"

    def test_degree_label_doctor(self):
        assert _degree_label("doctor") == "博士"


# ============================================================
# 第三部分：generate_outline 测试
# ============================================================


class TestGenerateOutline:
    """generate_outline 方法测试。"""

    def test_outline_returns_non_empty_string(self):
        """测试：大纲返回非空字符串。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("# 论文大纲\n## 第一章 绪论\n...")
            result = _run_async(agent.generate_outline("论题描述", "master"))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_outline_bachelor(self):
        """测试：本科学位大纲生成。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("# 本科论文大纲\n## 第一章 绪论")
            result = _run_async(agent.generate_outline("论题", "本科"))
        assert len(result) > 0
        assert mock_llm.called

    def test_outline_master(self):
        """测试：硕士学位大纲生成。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("# 硕士论文大纲\n## 第一章 绪论")
            result = _run_async(agent.generate_outline("论题", "硕士"))
        assert len(result) > 0

    def test_outline_doctor(self):
        """测试：博士学位大纲生成。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("# 博士论文大纲\n## 第一章 绪论")
            result = _run_async(agent.generate_outline("论题", "博士"))
        assert len(result) > 0

    def test_outline_empty_llm_response_uses_fallback(self):
        """测试：LLM 返回空内容时使用兜底大纲。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="")
            result = _run_async(agent.generate_outline("论题", "master"))
        assert len(result) > 0
        assert "#" in result  # Markdown 标题

    def test_outline_llm_exception_returns_fallback(self):
        """测试：LLM 异常时抛出（由调用方处理）。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 不可用")
            with pytest.raises(Exception):
                _run_async(agent.generate_outline("论题", "master"))

    def test_outline_prompt_contains_degree_label(self):
        """测试：提示包含学位标签。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            _run_async(agent.generate_outline("论题", "博士"))
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        assert "博士" in user_prompt


# ============================================================
# 第四部分：write_chapter 测试
# ============================================================


class TestWriteChapter:
    """write_chapter 方法测试。"""

    def test_chapter_returns_non_empty_string(self):
        """测试：章节返回非空字符串。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 第一章 绪论\n\n### 1.1 背景\n...")
            result = _run_async(agent.write_chapter(
                chapter_title="第一章 绪论",
                outline="研究背景与意义",
                references=["文献1", "文献2"],
                degree="master",
            ))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_chapter_with_empty_references(self):
        """测试：空参考文献列表不崩溃。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 章节\n内容")
            result = _run_async(agent.write_chapter(
                chapter_title="第二章",
                outline="",
                references=[],
                degree="master",
            ))
        assert len(result) > 0

    def test_chapter_empty_llm_response_uses_fallback(self):
        """测试：LLM 返回空内容时使用兜底。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="")
            result = _run_async(agent.write_chapter(
                chapter_title="第一章",
                outline="",
                references=[],
                degree="master",
            ))
        assert len(result) > 0
        assert "第一章" in result

    def test_chapter_prompt_contains_references(self):
        """测试：提示包含参考文献。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            _run_async(agent.write_chapter(
                chapter_title="第一章",
                outline="",
                references=["张三. AI研究. 2025."],
                degree="master",
            ))
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        assert "张三" in user_prompt
        assert "[1]" in user_prompt


# ============================================================
# 第五部分：revise_chapter 测试
# ============================================================


class TestReviseChapter:
    """revise_chapter 方法测试。"""

    def test_revise_returns_non_empty_string(self):
        """测试：修订返回非空字符串。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 修订后章节\n\n改进的内容[1]。")
            result = _run_async(agent.revise_chapter(
                chapter_content="## 原始章节\n\n原始内容",
                feedback="需要加强文献支撑",
            ))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_revise_empty_llm_response_returns_original(self):
        """测试：LLM 返回空内容时返回原始内容。"""
        agent = ThesisWriterAgent()
        original = "## 原始章节\n\n原始内容"
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="")
            result = _run_async(agent.revise_chapter(
                chapter_content=original,
                feedback="反馈",
            ))
        assert result == original

    def test_revise_prompt_contains_feedback(self):
        """测试：提示包含反馈意见。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            _run_async(agent.revise_chapter(
                chapter_content="内容",
                feedback="需要补充实验数据",
            ))
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        assert "需要补充实验数据" in user_prompt


# ============================================================
# 第六部分：check_plagiarism 测试
# ============================================================


class TestCheckPlagiarism:
    """check_plagiarism 方法测试。"""

    def test_plagiarism_returns_dict(self):
        """测试：查重返回字典。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_plagiarism_llm_result()
            result = _run_async(agent.check_plagiarism("待查重内容"))
        assert isinstance(result, dict)

    def test_plagiarism_has_similarity_score(self):
        """测试：结果包含 similarity_score。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_plagiarism_llm_result()
            result = _run_async(agent.check_plagiarism("内容"))
        assert "similarity_score" in result

    def test_plagiarism_has_high_risk_sections(self):
        """测试：结果包含 high_risk_sections。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_plagiarism_llm_result()
            result = _run_async(agent.check_plagiarism("内容"))
        assert "high_risk_sections" in result
        assert isinstance(result["high_risk_sections"], list)

    def test_plagiarism_has_suggestions(self):
        """测试：结果包含 suggestions。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_plagiarism_llm_result()
            result = _run_async(agent.check_plagiarism("内容"))
        assert "suggestions" in result
        assert isinstance(result["suggestions"], list)

    def test_plagiarism_score_is_float(self):
        """测试：相似度评分为 float 类型。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_plagiarism_llm_result()
            result = _run_async(agent.check_plagiarism("内容"))
        assert isinstance(result["similarity_score"], float)

    def test_plagiarism_score_in_range(self):
        """测试：相似度评分在 0-100 范围内。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_plagiarism_llm_result()
            result = _run_async(agent.check_plagiarism("内容"))
        assert 0.0 <= result["similarity_score"] <= 100.0

    def test_plagiarism_invalid_json_returns_fallback(self):
        """测试：LLM 返回非 JSON 时返回兜底结果。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="这不是JSON")
            result = _run_async(agent.check_plagiarism("内容"))
        assert result["similarity_score"] == 0.0
        assert result["high_risk_sections"] == []
        assert result["suggestions"] == []

    def test_plagiarism_json_in_code_block(self):
        """测试：JSON 包裹在代码块中可解析。"""
        agent = ThesisWriterAgent()
        json_content = (
            "```json\n"
            '{"similarity_score": 42.0, "high_risk_sections": ["段落A"], '
            '"suggestions": ["建议1"]}\n'
            "```"
        )
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content=json_content)
            result = _run_async(agent.check_plagiarism("内容"))
        assert result["similarity_score"] == 42.0
        assert "段落A" in result["high_risk_sections"]


# ============================================================
# 第七部分：reduce_similarity 测试
# ============================================================


class TestReduceSimilarity:
    """reduce_similarity 方法测试。"""

    def test_reduce_returns_non_empty_string(self):
        """测试：降重返回非空字符串。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 降重后内容\n\n改写的表述[1]。")
            result = _run_async(agent.reduce_similarity(
                chapter_content="## 原始内容\n\n原始表述",
                suggestions=["改写第一段"],
            ))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_reduce_empty_llm_response_returns_original(self):
        """测试：LLM 返回空内容时返回原始内容。"""
        agent = ThesisWriterAgent()
        original = "## 原始内容\n\n原始表述"
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result(content="")
            result = _run_async(agent.reduce_similarity(
                chapter_content=original,
                suggestions=["建议"],
            ))
        assert result == original

    def test_reduce_prompt_contains_suggestions(self):
        """测试：提示包含降重建议。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result()
            _run_async(agent.reduce_similarity(
                chapter_content="内容",
                suggestions=["重构第二段句式"],
            ))
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        assert "重构第二段句式" in user_prompt


# ============================================================
# 第八部分：run 统一入口测试
# ============================================================


class TestRun:
    """run 方法统一入口测试。"""

    def test_run_outline_action(self):
        """测试：run 执行 outline 动作。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("# 大纲")
            result = _run_async(agent.run({
                "action": "outline",
                "proposal": "论题",
                "degree": "master",
            }))
        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.agent_id == "thesis_writer"

    def test_run_write_action(self):
        """测试：run 执行 write 动作。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 章节")
            result = _run_async(agent.run({
                "action": "write",
                "chapter_title": "第一章",
                "outline": "",
                "references": [],
                "degree": "master",
            }))
        assert result.success is True

    def test_run_revise_action(self):
        """测试：run 执行 revise 动作。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 修订")
            result = _run_async(agent.run({
                "action": "revise",
                "chapter_content": "内容",
                "feedback": "反馈",
            }))
        assert result.success is True

    def test_run_plagiarism_action(self):
        """测试：run 执行 plagiarism 动作。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_plagiarism_llm_result()
            result = _run_async(agent.run({
                "action": "plagiarism",
                "chapter_content": "内容",
            }))
        assert result.success is True
        assert isinstance(result.data["result"], dict)

    def test_run_reduce_action(self):
        """测试：run 执行 reduce 动作。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 降重")
            result = _run_async(agent.run({
                "action": "reduce",
                "chapter_content": "内容",
                "suggestions": ["建议"],
            }))
        assert result.success is True

    def test_run_unknown_action_returns_failure(self):
        """测试：未知 action 返回失败。"""
        agent = ThesisWriterAgent()
        result = _run_async(agent.run({"action": "unknown"}))
        assert result.success is False

    def test_run_llm_exception_returns_failure(self):
        """测试：LLM 异常时返回失败结果。"""
        agent = ThesisWriterAgent()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 不可用")
            result = _run_async(agent.run({
                "action": "outline",
                "proposal": "论题",
                "degree": "master",
            }))
        assert result.success is False


# ============================================================
# 第九部分：兜底方法测试
# ============================================================


class TestFallbacks:
    """兜底生成方法测试。"""

    def test_outline_fallback_bachelor(self):
        """测试：本科大纲兜底。"""
        result = ThesisWriterAgent._outline_fallback("bachelor")
        assert "#" in result
        assert "本科" in result

    def test_outline_fallback_master(self):
        """测试：硕士大纲兜底。"""
        result = ThesisWriterAgent._outline_fallback("master")
        assert "#" in result
        assert "硕士" in result

    def test_outline_fallback_doctor(self):
        """测试：博士大纲兜底。"""
        result = ThesisWriterAgent._outline_fallback("doctor")
        assert "#" in result
        assert "博士" in result

    def test_chapter_fallback(self):
        """测试：章节兜底。"""
        result = ThesisWriterAgent._chapter_fallback("第一章 绪论")
        assert "第一章 绪论" in result
        assert "#" in result


# ============================================================
# 第十部分：章节 CRUD 测试
# ============================================================


class TestChapterCRUD:
    """论文章节 CRUD 操作测试。"""

    def _insert_session(self, sid: str):
        """插入会话以满足外键约束。"""
        from backend.database import get_db_connection
        conn = get_db_connection()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at)
                   VALUES (?, ?, datetime('now'), datetime('now'))""",
                (sid, f"测试会话-{sid}"),
            )
            conn.commit()
        finally:
            conn.close()

    def test_save_chapter_returns_id(self):
        """测试：保存章节返回 ID。"""
        self._insert_session("test-session-crud")
        chapter_id = save_chapter(
            session_id="test-session-crud",
            title="第一章 绪论",
            content="章节内容",
            word_count=3000,
            chapter_order=1,
        )
        assert isinstance(chapter_id, str)
        assert len(chapter_id) > 0

    def test_get_chapter_existing(self):
        """测试：获取已存在的章节。"""
        self._insert_session("test-session-crud")
        chapter_id = save_chapter(
            session_id="test-session-crud",
            title="第二章",
            content="内容",
            word_count=2000,
            chapter_order=2,
        )
        chapter = get_chapter(chapter_id)
        assert chapter is not None
        assert chapter["title"] == "第二章"
        assert chapter["word_count"] == 2000

    def test_get_chapter_nonexistent(self):
        """测试：获取不存在的章节返回 None。"""
        chapter = get_chapter("nonexistent-id")
        assert chapter is None

    def test_list_chapters_by_session(self):
        """测试：按会话列出章节。"""
        sid = "test-session-list"
        self._insert_session(sid)
        save_chapter(sid, "第一章", "内容1", chapter_order=1)
        save_chapter(sid, "第二章", "内容2", chapter_order=2)
        chapters = list_chapters(sid)
        assert len(chapters) >= 2
        # 按 chapter_order 升序
        assert chapters[0]["chapter_order"] <= chapters[1]["chapter_order"]

    def test_list_chapters_empty_session(self):
        """测试：空会话返回空列表。"""
        chapters = list_chapters("empty-session-id")
        assert chapters == []

    def test_update_chapter_title(self):
        """测试：更新章节标题。"""
        self._insert_session("test-session-update")
        chapter_id = save_chapter(
            session_id="test-session-update",
            title="原标题",
            content="内容",
        )
        affected = update_chapter(chapter_id, title="新标题")
        assert affected == 1
        chapter = get_chapter(chapter_id)
        assert chapter["title"] == "新标题"

    def test_update_chapter_content_and_status(self):
        """测试：更新章节内容与状态。"""
        self._insert_session("test-session-update")
        chapter_id = save_chapter(
            session_id="test-session-update",
            title="章节",
            content="原内容",
        )
        affected = update_chapter(
            chapter_id, content="新内容", status="revised", word_count=5000
        )
        assert affected == 1
        chapter = get_chapter(chapter_id)
        assert chapter["content"] == "新内容"
        assert chapter["status"] == "revised"
        assert chapter["word_count"] == 5000

    def test_update_chapter_plagiarism_score(self):
        """测试：更新查重评分。"""
        self._insert_session("test-session-update")
        chapter_id = save_chapter(
            session_id="test-session-update",
            title="章节",
            content="内容",
        )
        update_chapter(chapter_id, plagiarism_score=25.5)
        chapter = get_chapter(chapter_id)
        assert chapter["plagiarism_score"] == 25.5

    def test_update_chapter_nonexistent(self):
        """测试：更新不存在的章节返回 0。"""
        affected = update_chapter("nonexistent-id", title="标题")
        assert affected == 0

    def test_update_chapter_no_fields(self):
        """测试：不传任何字段返回 0。"""
        self._insert_session("test-session-update")
        chapter_id = save_chapter(
            session_id="test-session-update",
            title="章节",
            content="内容",
        )
        affected = update_chapter(chapter_id)
        assert affected == 0

    def test_delete_chapter(self):
        """测试：删除章节。"""
        self._insert_session("test-session-delete")
        chapter_id = save_chapter(
            session_id="test-session-delete",
            title="待删除",
            content="内容",
        )
        affected = delete_chapter(chapter_id)
        assert affected == 1
        assert get_chapter(chapter_id) is None

    def test_delete_chapter_nonexistent(self):
        """测试：删除不存在的章节返回 0。"""
        affected = delete_chapter("nonexistent-id")
        assert affected == 0

    def test_chapter_crud_full_cycle(self):
        """测试：完整 CRUD 周期（保存→获取→更新→删除）。"""
        self._insert_session("test-session-cycle")
        # 保存
        chapter_id = save_chapter(
            session_id="test-session-cycle",
            title="测试章节",
            content="初始内容",
            word_count=1000,
            chapter_order=1,
            status="draft",
        )
        # 获取
        chapter = get_chapter(chapter_id)
        assert chapter["title"] == "测试章节"
        # 更新
        update_chapter(chapter_id, title="更新标题", status="final")
        chapter = get_chapter(chapter_id)
        assert chapter["title"] == "更新标题"
        assert chapter["status"] == "final"
        # 删除
        delete_chapter(chapter_id)
        assert get_chapter(chapter_id) is None


# ============================================================
# 第十一部分：API 端点测试
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


class TestThesisAPIEndpoints:
    """论文撰写 API 端点测试。"""

    def test_outline_endpoint_success(self):
        """测试：POST /api/thesis/{sid}/outline 成功。"""
        sid = _insert_session()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("# 生成的大纲")
            with patch("backend.routes.thesis.check_api_configured", return_value=True):
                with TestClient(app) as client:
                    resp = client.post(f"/api/thesis/{sid}/outline", json={
                        "proposal": "论题描述",
                        "degree": "master",
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "outline" in data
        assert len(data["outline"]) > 0

    def test_outline_endpoint_no_api_key(self):
        """测试：未配置 API Key 返回 400。"""
        sid = _insert_session()
        with patch("backend.routes.thesis.check_api_configured", return_value=False):
            with TestClient(app) as client:
                resp = client.post(f"/api/thesis/{sid}/outline", json={
                    "proposal": "论题",
                    "degree": "master",
                })
        assert resp.status_code == 400

    def test_chapter_endpoint_success(self):
        """测试：POST /api/thesis/{sid}/chapter 成功。"""
        sid = _insert_session()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 第一章\n内容")
            with patch("backend.routes.thesis.check_api_configured", return_value=True):
                with TestClient(app) as client:
                    resp = client.post(f"/api/thesis/{sid}/chapter", json={
                        "chapter_title": "第一章 绪论",
                        "outline": "大纲",
                        "references": ["文献1"],
                        "degree": "master",
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "chapter" in data

    def test_revise_endpoint_success(self):
        """测试：POST /api/thesis/{sid}/revise 成功。"""
        sid = _insert_session()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 修订后")
            with patch("backend.routes.thesis.check_api_configured", return_value=True):
                with TestClient(app) as client:
                    resp = client.post(f"/api/thesis/{sid}/revise", json={
                        "chapter_content": "原始内容",
                        "feedback": "加强论证",
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "chapter" in data

    def test_plagiarism_endpoint_success(self):
        """测试：POST /api/thesis/{sid}/plagiarism 成功。"""
        sid = _insert_session()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_plagiarism_llm_result()
            with patch("backend.routes.thesis.check_api_configured", return_value=True):
                with TestClient(app) as client:
                    resp = client.post(f"/api/thesis/{sid}/plagiarism", json={
                        "chapter_content": "待查重内容",
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "similarity_score" in data["result"]

    def test_reduce_similarity_endpoint_success(self):
        """测试：POST /api/thesis/{sid}/reduce-similarity 成功。"""
        sid = _insert_session()
        with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_llm_result("## 降重后内容")
            with patch("backend.routes.thesis.check_api_configured", return_value=True):
                with TestClient(app) as client:
                    resp = client.post(f"/api/thesis/{sid}/reduce-similarity", json={
                        "chapter_content": "原始内容",
                        "suggestions": ["改写第一段"],
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "chapter" in data

    def test_list_chapters_endpoint_empty(self):
        """测试：GET /api/thesis/{sid}/chapters 空列表。"""
        sid = _insert_session()
        with TestClient(app) as client:
            resp = client.get(f"/api/thesis/{sid}/chapters")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chapters"] == []

    def test_save_chapter_endpoint_success(self):
        """测试：POST /api/thesis/{sid}/chapters 保存章节成功。"""
        sid = _insert_session()
        with TestClient(app) as client:
            resp = client.post(f"/api/thesis/{sid}/chapters", json={
                "title": "第一章 绪论",
                "content": "章节内容",
                "word_count": 3000,
                "chapter_order": 1,
                "status": "draft",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "chapter_id" in data
        assert data["chapter"]["title"] == "第一章 绪论"

    def test_get_chapters_after_save(self):
        """测试：保存后 GET 列表包含该章节。"""
        sid = _insert_session()
        with TestClient(app) as client:
            client.post(f"/api/thesis/{sid}/chapters", json={
                "title": "测试章节",
                "content": "内容",
                "word_count": 1000,
                "chapter_order": 1,
            })
            resp = client.get(f"/api/thesis/{sid}/chapters")
        assert resp.status_code == 200
        chapters = resp.json()["chapters"]
        assert len(chapters) >= 1
        assert any(c["title"] == "测试章节" for c in chapters)

    def test_update_chapter_endpoint_success(self):
        """测试：PUT /api/thesis/{sid}/chapters/{cid} 更新章节成功。"""
        sid = _insert_session()
        with TestClient(app) as client:
            save_resp = client.post(f"/api/thesis/{sid}/chapters", json={
                "title": "原标题",
                "content": "原内容",
                "word_count": 1000,
            })
            chapter_id = save_resp.json()["chapter_id"]
            resp = client.put(f"/api/thesis/{sid}/chapters/{chapter_id}", json={
                "title": "新标题",
                "status": "revised",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] is True
        assert data["chapter"]["title"] == "新标题"
        assert data["chapter"]["status"] == "revised"

    def test_update_chapter_nonexistent_returns_404(self):
        """测试：更新不存在的章节返回 404。"""
        sid = _insert_session()
        with TestClient(app) as client:
            resp = client.put(f"/api/thesis/{sid}/chapters/nonexistent-id", json={
                "title": "新标题",
            })
        assert resp.status_code == 404

    def test_update_chapter_wrong_session_returns_404(self):
        """测试：更新其他会话的章节返回 404。"""
        sid1 = _insert_session()
        sid2 = _insert_session()
        with TestClient(app) as client:
            save_resp = client.post(f"/api/thesis/{sid1}/chapters", json={
                "title": "章节",
                "content": "内容",
            })
            chapter_id = save_resp.json()["chapter_id"]
            resp = client.put(f"/api/thesis/{sid2}/chapters/{chapter_id}", json={
                "title": "篡改",
            })
        assert resp.status_code == 404

    def test_delete_chapter_endpoint_success(self):
        """测试：DELETE /api/thesis/{sid}/chapters/{cid} 删除章节成功。"""
        sid = _insert_session()
        with TestClient(app) as client:
            save_resp = client.post(f"/api/thesis/{sid}/chapters", json={
                "title": "待删除",
                "content": "内容",
            })
            chapter_id = save_resp.json()["chapter_id"]
            resp = client.delete(f"/api/thesis/{sid}/chapters/{chapter_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_chapter_nonexistent_returns_404(self):
        """测试：删除不存在的章节返回 404。"""
        sid = _insert_session()
        with TestClient(app) as client:
            resp = client.delete(f"/api/thesis/{sid}/chapters/nonexistent-id")
        assert resp.status_code == 404
