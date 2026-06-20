"""DST 对话状态追踪器与压缩器单元测试

测试 backend/sessions/dialogue_state_tracker.py 与 dst_compactor.py。
覆盖以下功能：
  - extract_state: 从对话历史提取结构化状态槽
  - _extract_selected_topic: 提取已选定论题
  - _extract_confirmed_methods: 提取已确认研究方法
  - _extract_confirmed_discipline: 提取已确认学科方向
  - _extract_open_questions: 提取待解决问题
  - _has_question_marker: 判断疑问词
  - _dedupe: 列表去重
  - compact_history: 压缩历史为 DST 状态块
  - _format_dst_state: 格式化 DST 状态

测试策略：
  - 纯逻辑测试，不依赖数据库
  - 覆盖各种关键词匹配模式
  - 边界条件：空输入、非字典项、无匹配内容
"""
import os
import sys

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.sessions.dialogue_state_tracker import (
    extract_state,
    _extract_selected_topic,
    _extract_confirmed_methods,
    _extract_confirmed_discipline,
    _extract_open_questions,
    _has_question_marker,
    _dedupe,
)
from backend.sessions.dst_compactor import (
    compact_history,
    _format_dst_state,
)


# ===== 测试类：extract_state =====

class TestExtractState:
    """测试 extract_state 函数。"""

    def test_extract_empty_history(self):
        """空历史应返回初始状态。"""
        state = extract_state([])
        assert state["selected_topic"] is None
        assert state["confirmed_methods"] == []
        assert state["confirmed_discipline"] is None
        assert state["open_questions"] == []
        assert state["iteration_count"] == 0

    def test_extract_none_history(self):
        """None 输入应返回初始状态。"""
        state = extract_state(None)
        assert state["selected_topic"] is None
        assert state["iteration_count"] == 0

    def test_extract_sets_iteration_count(self):
        """iteration_count 应等于历史长度。"""
        history = [
            {"role": "user", "content": "消息1"},
            {"role": "assistant", "content": "回复1"},
            {"role": "user", "content": "消息2"},
        ]
        state = extract_state(history)
        assert state["iteration_count"] == 3

    def test_extract_with_selected_topic(self):
        """提取已选定论题。"""
        history = [
            {"role": "assistant", "content": "选定论题：基于深度学习的论文推荐"},
        ]
        state = extract_state(history)
        assert state["selected_topic"] == "基于深度学习的论文推荐"

    def test_extract_with_confirmed_methods(self):
        """提取已确认研究方法。"""
        history = [
            {"role": "user", "content": "确认方法：文献计量、内容分析"},
        ]
        state = extract_state(history)
        assert "文献计量" in state["confirmed_methods"]
        assert "内容分析" in state["confirmed_methods"]

    def test_extract_with_confirmed_discipline(self):
        """提取已确认学科方向。"""
        history = [
            {"role": "user", "content": "确认学科：计算机科学"},
        ]
        state = extract_state(history)
        assert state["confirmed_discipline"] == "计算机科学"

    def test_extract_with_open_questions(self):
        """提取待解决问题。"""
        history = [
            {"role": "user", "content": "待解决问题：如何评估模型效果？"},
        ]
        state = extract_state(history)
        assert len(state["open_questions"]) >= 1

    def test_extract_dedupes_methods(self):
        """重复的方法应去重。"""
        history = [
            {"role": "user", "content": "确认方法：实验法"},
            {"role": "assistant", "content": "确认方法：实验法、问卷调查"},
        ]
        state = extract_state(history)
        assert state["confirmed_methods"].count("实验法") == 1

    def test_extract_skips_non_dict_items(self):
        """非字典项应跳过。"""
        history = [
            "not a dict",
            {"role": "user", "content": "选定论题：测试论题"},
            None,
        ]
        state = extract_state(history)
        assert state["selected_topic"] == "测试论题"

    def test_extract_skips_non_string_content(self):
        """非字符串 content 应跳过。"""
        history = [
            {"role": "user", "content": 123},
            {"role": "user", "content": None},
        ]
        state = extract_state(history)
        assert state["selected_topic"] is None

    def test_extract_with_question_mark(self):
        """问号结尾的句子应提取为待解决问题。"""
        history = [
            {"role": "user", "content": "如何评估这个方法？"},
        ]
        state = extract_state(history)
        assert len(state["open_questions"]) >= 1

    def test_extract_with_question_marker_keywords(self):
        """包含疑问词的句子应提取为待解决问题。"""
        history = [
            {"role": "user", "content": "如何评估这个模型的效果"},
        ]
        state = extract_state(history)
        assert len(state["open_questions"]) >= 1


# ===== 测试类：_extract_selected_topic =====

class TestExtractSelectedTopic:
    """测试 _extract_selected_topic 函数。"""

    def test_extract_with_colon(self):
        """冒号分隔的论题应提取。"""
        state = {"selected_topic": None}
        _extract_selected_topic("选定论题：AI教育研究", state)
        assert state["selected_topic"] == "AI教育研究"

    def test_extract_with_chinese_colon(self):
        """中文冒号分隔的论题应提取。"""
        state = {"selected_topic": None}
        _extract_selected_topic("确认论题：基于图谱的推荐", state)
        assert state["selected_topic"] == "基于图谱的推荐"

    def test_extract_with_choice_keyword(self):
        """选择关键词应匹配。"""
        state = {"selected_topic": None}
        _extract_selected_topic("选择论题：深度学习应用", state)
        assert state["selected_topic"] == "深度学习应用"

    def test_extract_no_match(self):
        """无匹配时应保持 None。"""
        state = {"selected_topic": None}
        _extract_selected_topic("今天天气不错", state)
        assert state["selected_topic"] is None

    def test_extract_strips_whitespace(self):
        """提取的论题应去除首尾空白。"""
        state = {"selected_topic": None}
        _extract_selected_topic("选定论题：  带空格的论题  ", state)
        assert state["selected_topic"] == "带空格的论题"

    def test_extract_with_newline_terminator(self):
        """换行符终止的论题应正确提取。"""
        state = {"selected_topic": None}
        _extract_selected_topic("选定论题：第一行论题\n第二行内容", state)
        assert state["selected_topic"] == "第一行论题"


# ===== 测试类：_extract_confirmed_methods =====

class TestExtractConfirmedMethods:
    """测试 _extract_confirmed_methods 函数。"""

    def test_extract_single_method(self):
        """提取单个方法。"""
        state = {"confirmed_methods": []}
        _extract_confirmed_methods("确认方法：实验法", state)
        assert "实验法" in state["confirmed_methods"]

    def test_extract_multiple_methods_with_dunhao(self):
        """顿号分隔的多个方法应全部提取。"""
        state = {"confirmed_methods": []}
        _extract_confirmed_methods("确认方法：实验法、问卷调查、统计分析", state)
        assert len(state["confirmed_methods"]) == 3

    def test_extract_multiple_methods_with_comma(self):
        """逗号分隔的多个方法应全部提取。"""
        state = {"confirmed_methods": []}
        _extract_confirmed_methods("研究方法：定量分析,定性分析", state)
        assert "定量分析" in state["confirmed_methods"]
        assert "定性分析" in state["confirmed_methods"]

    def test_extract_with_research_keyword(self):
        """研究方法关键词应匹配。"""
        state = {"confirmed_methods": []}
        _extract_confirmed_methods("研究方法：文献计量", state)
        assert "文献计量" in state["confirmed_methods"]

    def test_extract_with_adopt_keyword(self):
        """采用方法关键词应匹配。"""
        state = {"confirmed_methods": []}
        _extract_confirmed_methods("采用方法：深度学习", state)
        assert "深度学习" in state["confirmed_methods"]

    def test_extract_no_match(self):
        """无匹配时应保持空列表。"""
        state = {"confirmed_methods": []}
        _extract_confirmed_methods("今天天气不错", state)
        assert state["confirmed_methods"] == []


# ===== 测试类：_extract_confirmed_discipline =====

class TestExtractConfirmedDiscipline:
    """测试 _extract_confirmed_discipline 函数。"""

    def test_extract_with_confirm_keyword(self):
        """确认学科应提取。"""
        state = {"confirmed_discipline": None}
        _extract_confirmed_discipline("确认学科：计算机科学", state)
        assert state["confirmed_discipline"] == "计算机科学"

    def test_extract_with_select_keyword(self):
        """选定学科应提取。"""
        state = {"confirmed_discipline": None}
        _extract_confirmed_discipline("选定学科：教育学", state)
        assert state["confirmed_discipline"] == "教育学"

    def test_extract_with_direction_keyword(self):
        """学科方向应提取。"""
        state = {"confirmed_discipline": None}
        _extract_confirmed_discipline("确认学科方向：人工智能", state)
        assert state["confirmed_discipline"] == "人工智能"

    def test_extract_no_match(self):
        """无匹配时应保持 None。"""
        state = {"confirmed_discipline": None}
        _extract_confirmed_discipline("今天天气不错", state)
        assert state["confirmed_discipline"] is None


# ===== 测试类：_extract_open_questions =====

class TestExtractOpenQuestions:
    """测试 _extract_open_questions 函数。"""

    def test_extract_with_explicit_keyword(self):
        """待解决问题关键词应提取。"""
        state = {"open_questions": []}
        _extract_open_questions("待解决问题：如何评估模型效果", state)
        assert len(state["open_questions"]) >= 1

    def test_extract_with_unresolved_keyword(self):
        """未解决关键词应提取。"""
        state = {"open_questions": []}
        _extract_open_questions("未解决：数据来源不足", state)
        assert len(state["open_questions"]) >= 1

    def test_extract_with_question_mark(self):
        """问号结尾的句子应提取。"""
        state = {"open_questions": []}
        _extract_open_questions("如何评估这个方法？", state)
        assert len(state["open_questions"]) >= 1

    def test_extract_with_chinese_question_mark(self):
        """中文问号结尾的句子应提取。"""
        state = {"open_questions": []}
        _extract_open_questions("数据集怎么构建？", state)
        assert len(state["open_questions"]) >= 1

    def test_extract_with_question_marker(self):
        """包含疑问词的句子应提取。"""
        state = {"open_questions": []}
        _extract_open_questions("如何选择合适的评估指标", state)
        assert len(state["open_questions"]) >= 1

    def test_extract_no_match(self):
        """无匹配时应保持空列表。"""
        state = {"open_questions": []}
        _extract_open_questions("今天天气不错", state)
        assert state["open_questions"] == []


# ===== 测试类：_has_question_marker =====

class TestHasQuestionMarker:
    """测试 _has_question_marker 函数。"""

    def test_with_ruhe(self):
        """包含"如何"应返回 True。"""
        assert _has_question_marker("如何评估模型") is True

    def test_with_zenme(self):
        """包含"怎么"应返回 True。"""
        assert _has_question_marker("怎么选择方法") is True

    def test_with_weishenme(self):
        """包含"为什么"应返回 True。"""
        assert _has_question_marker("为什么选择这个方案") is True

    def test_with_shifou(self):
        """包含"是否"应返回 True。"""
        assert _has_question_marker("是否可行") is True

    def test_with_shenme(self):
        """包含"什么"应返回 True。"""
        assert _has_question_marker("有什么方法") is True

    def test_without_marker(self):
        """不包含疑问词应返回 False。"""
        assert _has_question_marker("今天天气不错") is False

    def test_empty_string(self):
        """空字符串应返回 False。"""
        assert _has_question_marker("") is False


# ===== 测试类：_dedupe =====

class TestDedupe:
    """测试 _dedupe 函数。"""

    def test_dedupe_empty_list(self):
        """空列表去重应返回空列表。"""
        assert _dedupe([]) == []

    def test_dedupe_no_duplicates(self):
        """无重复项应保持原样。"""
        assert _dedupe(["a", "b", "c"]) == ["a", "b", "c"]

    def test_dedupe_with_duplicates(self):
        """有重复项应去重。"""
        result = _dedupe(["a", "b", "a", "c", "b"])
        assert result == ["a", "b", "c"]

    def test_dedupe_preserves_order(self):
        """去重应保持原始顺序。"""
        result = _dedupe(["c", "a", "b", "a", "c"])
        assert result == ["c", "a", "b"]

    def test_dedupe_all_same(self):
        """全部相同应只保留一个。"""
        assert _dedupe(["x", "x", "x"]) == ["x"]


# ===== 测试类：compact_history =====

class TestCompactHistory:
    """测试 compact_history 函数。"""

    def test_compact_short_history(self):
        """短历史（≤5条）不压缩。"""
        history = [
            {"role": "user", "content": "消息1"},
            {"role": "assistant", "content": "回复1"},
        ]
        result = compact_history(history, {})
        assert len(result) == 2
        assert result == history

    def test_compact_long_history(self):
        """长历史（>5条）应压缩。"""
        history = [
            {"role": "user", "content": f"消息{i}"}
            for i in range(10)
        ]
        result = compact_history(history, {"selected_topic": "测试论题"})
        # 压缩后应为 1 条摘要 + 最近 4 条
        assert len(result) == 5
        # 第一条应为 system 角色的摘要
        assert result[0]["role"] == "system"
        assert "[对话状态摘要]" in result[0]["content"]

    def test_compact_non_list_input(self):
        """非列表输入应返回空列表。"""
        result = compact_history("not a list", {})
        assert result == []

    def test_compact_empty_history(self):
        """空历史应返回空列表。"""
        result = compact_history([], {})
        assert result == []

    def test_compact_preserves_recent_messages(self):
        """压缩后应保留最近 4 条原始消息。"""
        history = [
            {"role": "user", "content": f"消息{i}"}
            for i in range(10)
        ]
        result = compact_history(history, {})
        # 最近 4 条应在结果末尾
        recent = result[-4:]
        assert recent[0]["content"] == "消息6"
        assert recent[3]["content"] == "消息9"

    def test_compact_summary_contains_state(self):
        """压缩摘要应包含 DST 状态信息。"""
        history = [
            {"role": "user", "content": f"消息{i}"}
            for i in range(10)
        ]
        dst_state = {
            "selected_topic": "AI教育研究",
            "confirmed_methods": ["实验法"],
            "confirmed_discipline": "计算机科学",
            "open_questions": ["如何评估？"],
            "iteration_count": 10,
        }
        result = compact_history(history, dst_state)
        summary = result[0]["content"]
        assert "AI教育研究" in summary
        assert "实验法" in summary
        assert "计算机科学" in summary


# ===== 测试类：_format_dst_state =====

class TestFormatDstState:
    """测试 _format_dst_state 函数。"""

    def test_format_empty_state(self):
        """空状态应返回默认文本。"""
        result = _format_dst_state({})
        assert "对话轮数：0" in result

    def test_format_none_state(self):
        """None 状态应返回默认文本。"""
        result = _format_dst_state(None)
        assert "对话轮数：0" in result

    def test_format_with_selected_topic(self):
        """含选定论题的状态应包含论题。"""
        result = _format_dst_state({"selected_topic": "AI研究", "iteration_count": 5})
        assert "已选定论题：AI研究" in result

    def test_format_with_methods(self):
        """含方法的状态应包含方法。"""
        result = _format_dst_state({
            "confirmed_methods": ["实验法", "问卷调查"],
            "iteration_count": 3,
        })
        assert "已确认方法" in result
        assert "实验法" in result

    def test_format_with_discipline(self):
        """含学科的状态应包含学科。"""
        result = _format_dst_state({
            "confirmed_discipline": "计算机科学",
            "iteration_count": 2,
        })
        assert "已确认学科：计算机科学" in result

    def test_format_with_open_questions(self):
        """含待解决问题的状态应包含问题。"""
        result = _format_dst_state({
            "open_questions": ["如何评估？", "数据从哪来？"],
            "iteration_count": 4,
        })
        assert "待解决问题" in result

    def test_format_iteration_count(self):
        """应包含对话轮数。"""
        result = _format_dst_state({"iteration_count": 7})
        assert "对话轮数：7" in result

    def test_format_full_state(self):
        """完整状态应包含所有字段。"""
        state = {
            "selected_topic": "深度学习",
            "confirmed_methods": ["实验法"],
            "confirmed_discipline": "AI",
            "open_questions": ["如何评估？"],
            "iteration_count": 5,
        }
        result = _format_dst_state(state)
        assert "已选定论题：深度学习" in result
        assert "已确认方法" in result
        assert "已确认学科：AI" in result
        assert "待解决问题" in result
        assert "对话轮数：5" in result
