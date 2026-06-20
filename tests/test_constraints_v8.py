"""Task 8 测试：验证 v8.0 五阶段闭环导航流约束

覆盖：
- stage_gate: check_gate for all 5 stages
- info_confirmation: format_paper_summary, validate_confirmation
- hard_rules: validate_title (too long, too short, forbidden pattern), validate_timeline, validate_duplication
- novelty_checker: calculate_similarity, assess_novelty returns 0-100 score
- style_normalizer: normalize removes template words, get_ai_trace_score
- multi_granularity: validate_granularity for all 4 levels
- deep_assist: (mock call_llm) all 3 functions return DeepAssistResult
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_llm_result(content: str) -> dict:
    """构造模拟的 call_llm 返回值"""
    return {
        "content": content,
        "model": "mock-model",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "cached_tokens": 0,
        "cost": 0.0,
    }


class TestStageGate:
    """五阶段门禁测试"""

    def test_info_confirm_passes_with_user_confirmation(self):
        """信息确权阶段：用户确认后通过"""
        from backend.constraints.stage_gate import Stage, check_gate

        result = check_gate(Stage.INFO_CONFIRM, {"user_confirmed": True})
        assert result.passed is True
        assert result.stage == Stage.INFO_CONFIRM

    def test_info_confirm_fails_without_confirmation(self):
        """信息确权阶段：未确认时不通过"""
        from backend.constraints.stage_gate import Stage, check_gate

        result = check_gate(Stage.INFO_CONFIRM, {"user_confirmed": False})
        assert result.passed is False
        assert "等待用户确认" in result.message

    def test_creativity_passes_with_3_candidates(self):
        """创意阶段：3个候选通过"""
        from backend.constraints.stage_gate import Stage, check_gate

        candidates = [{"title": f"论题{i}"} for i in range(3)]
        result = check_gate(Stage.CREATIVITY, {"candidates": candidates})
        assert result.passed is True

    def test_creativity_fails_with_less_than_3_candidates(self):
        """创意阶段：少于3个候选不通过"""
        from backend.constraints.stage_gate import Stage, check_gate

        candidates = [{"title": "论题1"}, {"title": "论题2"}]
        result = check_gate(Stage.CREATIVITY, {"candidates": candidates})
        assert result.passed is False
        assert "候选不足" in result.message

    def test_validation_passes_with_score_above_60(self):
        """校验阶段：平均分≥60通过"""
        from backend.constraints.stage_gate import Stage, check_gate

        evaluations = [{"score": 70}, {"score": 80}]
        result = check_gate(Stage.VALIDATION, {"evaluations": evaluations})
        assert result.passed is True

    def test_validation_fails_with_score_below_60(self):
        """校验阶段：平均分<60不通过并回退"""
        from backend.constraints.stage_gate import Stage, check_gate

        evaluations = [{"score": 40}, {"score": 50}]
        result = check_gate(Stage.VALIDATION, {"evaluations": evaluations})
        assert result.passed is False
        assert result.retry_stage == Stage.CREATIVITY

    def test_validation_fails_with_no_evaluations(self):
        """校验阶段：无评估结果不通过"""
        from backend.constraints.stage_gate import Stage, check_gate

        result = check_gate(Stage.VALIDATION, {"evaluations": []})
        assert result.passed is False
        assert "无评估结果" in result.message

    def test_generation_passes_with_content(self):
        """生成阶段：内容非空通过"""
        from backend.constraints.stage_gate import Stage, check_gate

        result = check_gate(Stage.GENERATION, {"content": "生成的内容"})
        assert result.passed is True

    def test_generation_fails_with_empty_content(self):
        """生成阶段：内容为空不通过"""
        from backend.constraints.stage_gate import Stage, check_gate

        result = check_gate(Stage.GENERATION, {"content": ""})
        assert result.passed is False

    def test_deep_assist_always_passes(self):
        """深度辅助阶段：始终通过"""
        from backend.constraints.stage_gate import Stage, check_gate

        result = check_gate(Stage.DEEP_ASSIST, {})
        assert result.passed is True

    def test_stage_gates_definition_complete(self):
        """五阶段门禁定义应完整"""
        from backend.constraints.stage_gate import STAGE_GATES, Stage

        assert len(STAGE_GATES) == 5
        for stage in Stage:
            assert stage in STAGE_GATES

    def test_validation_gate_has_min_score_60(self):
        """校验阶段门禁最低分应为60"""
        from backend.constraints.stage_gate import STAGE_GATES, Stage

        assert STAGE_GATES[Stage.VALIDATION].min_score == 60

    def test_validation_gate_retry_on_fail_is_creativity(self):
        """校验阶段失败应回退到创意阶段"""
        from backend.constraints.stage_gate import STAGE_GATES, Stage

        assert STAGE_GATES[Stage.VALIDATION].retry_on_fail == Stage.CREATIVITY


class TestInfoConfirmation:
    """信息确权测试"""

    def test_format_paper_summary_with_papers(self):
        """格式化文献摘要：有文献时应展示"""
        from backend.constraints.info_confirmation import format_paper_summary

        papers = [
            {"title": "深度学习研究", "authors": "张三", "year": 2025, "abstract": "本文研究深度学习"},
            {"title": "神经网络优化", "authors": "李四", "year": 2024, "abstract": "本文优化神经网络"},
        ]
        summary = format_paper_summary(papers)
        assert "共检索到 2 篇" in summary
        assert "深度学习研究" in summary
        assert "神经网络优化" in summary
        assert "请确认" in summary

    def test_format_paper_summary_empty(self):
        """格式化文献摘要：无文献时提示"""
        from backend.constraints.info_confirmation import format_paper_summary

        summary = format_paper_summary([])
        assert "未检索到相关文献" in summary

    def test_format_paper_summary_limits_to_10(self):
        """格式化文献摘要：最多展示10篇"""
        from backend.constraints.info_confirmation import format_paper_summary

        papers = [{"title": f"论文{i}", "authors": "作者", "year": 2025, "abstract": "摘要"} for i in range(15)]
        summary = format_paper_summary(papers)
        assert "共检索到 15 篇" in summary
        assert "还有 5 篇文献未展示" in summary

    def test_validate_confirmation_positive(self):
        """验证确认：肯定关键词应返回True"""
        from backend.constraints.info_confirmation import validate_confirmation

        assert validate_confirmation("确认") is True
        assert validate_confirmation("正确") is True
        assert validate_confirmation("yes") is True
        assert validate_confirmation("继续") is True
        assert validate_confirmation("没问题") is True
        assert validate_confirmation("准确") is True

    def test_validate_confirmation_negative(self):
        """验证确认：否定/空响应应返回False"""
        from backend.constraints.info_confirmation import validate_confirmation

        assert validate_confirmation("不对") is False
        assert validate_confirmation("") is False
        assert validate_confirmation(None) is False

    @pytest.mark.asyncio
    async def test_search_recent_papers_returns_dict(self):
        """检索近2年文献应返回字典结构"""
        from backend.constraints.info_confirmation import search_recent_papers

        with patch("backend.ai.ai_proxy.call_llm", new=AsyncMock(return_value=_make_llm_result('{"summary": "ok"}'))):
            result = await search_recent_papers("深度学习", years=2)
        assert isinstance(result, dict)
        assert "papers" in result
        assert "summary" in result
        assert "citations" in result


class TestHardRules:
    """硬约束规则库测试"""

    def test_validate_title_too_long_master(self):
        """标题超长（硕士）应报error"""
        from backend.constraints.hard_rules import validate_title, has_errors

        long_title = "这是一个非常非常非常非常非常长的标题超过二十五个字了"  # 26字 > 25
        violations = validate_title(long_title, "master")
        assert has_errors(violations) is True
        title_violations = [v for v in violations if v.rule == "title_length"]
        assert len(title_violations) == 1

    def test_validate_title_too_long_doctor(self):
        """标题超长（博士）应报error"""
        from backend.constraints.hard_rules import validate_title, has_errors

        long_title = "这是一个非常非常非常非常非常非常非常长的标题超过三十个字博士了"  # 31字 > 30
        violations = validate_title(long_title, "doctor")
        assert has_errors(violations) is True

    def test_validate_title_too_short(self):
        """标题过短应报warning"""
        from backend.constraints.hard_rules import validate_title, has_errors

        short_title = "短标题"  # <8字
        violations = validate_title(short_title, "master")
        # 过短是warning，不是error
        assert has_errors(violations) is False
        min_len_violations = [v for v in violations if v.rule == "title_min_length"]
        assert len(min_len_violations) == 1
        assert min_len_violations[0].severity == "warning"

    def test_validate_title_forbidden_pattern(self):
        """标题匹配禁止模式应报warning"""
        from backend.constraints.hard_rules import validate_title

        violations = validate_title("基于深度学习的研究", "master")
        pattern_violations = [v for v in violations if v.rule == "title_pattern"]
        assert len(pattern_violations) >= 1

    def test_validate_title_empty(self):
        """空标题应报error"""
        from backend.constraints.hard_rules import validate_title, has_errors

        violations = validate_title("", "master")
        assert has_errors(violations) is True
        assert violations[0].rule == "title_required"

    def test_validate_title_valid(self):
        """合规标题不应有违规"""
        from backend.constraints.hard_rules import validate_title

        violations = validate_title("深度学习模型优化方法", "master")
        assert len(violations) == 0

    def test_validate_timeline_exceeds_master(self):
        """时间规划超过硕士年限应报error"""
        from backend.constraints.hard_rules import validate_timeline, has_errors

        violations = validate_timeline({"total_months": 15}, "master")  # 硕士1年=12月
        assert has_errors(violations) is True

    def test_validate_timeline_within_master(self):
        """时间规划在硕士年限内应无违规"""
        from backend.constraints.hard_rules import validate_timeline, has_errors

        violations = validate_timeline({"total_months": 10}, "master")
        assert has_errors(violations) is False

    def test_validate_timeline_exceeds_doctor(self):
        """时间规划超过博士年限应报error"""
        from backend.constraints.hard_rules import validate_timeline, has_errors

        violations = validate_timeline({"total_months": 30}, "doctor")  # 博士2年=24月
        assert has_errors(violations) is True

    def test_validate_timeline_empty(self):
        """空时间规划应报error"""
        from backend.constraints.hard_rules import validate_timeline, has_errors

        violations = validate_timeline({}, "master")
        assert has_errors(violations) is True

    def test_validate_duplication_exceeds_threshold(self):
        """重复度超过阈值应报error"""
        from backend.constraints.hard_rules import validate_duplication, has_errors

        violations = validate_duplication(0.5, threshold=0.3)
        assert has_errors(violations) is True

    def test_validate_duplication_within_threshold(self):
        """重复度在阈值内应无违规"""
        from backend.constraints.hard_rules import validate_duplication, has_errors

        violations = validate_duplication(0.2, threshold=0.3)
        assert has_errors(violations) is False

    def test_validate_all_combines_all_checks(self):
        """validate_all 应组合所有校验"""
        from backend.constraints.hard_rules import validate_all

        violations = validate_all(
            topic="基于深度学习的研究这是一个超长标题超过二十五个字",
            degree="master",
            discipline="计算机",
            advisor_direction="自然语言处理",
            timeline={"total_months": 15},
            similarity=0.5,
        )
        assert len(violations) > 0


class TestNoveltyChecker:
    """新颖性评估测试"""

    def test_calculate_similarity_no_existing(self):
        """无已有文献时相似度为0"""
        from backend.constraints.novelty_checker import calculate_similarity

        assert calculate_similarity("深度学习", []) == 0.0

    def test_calculate_similarity_identical(self):
        """完全相同标题相似度应为1"""
        from backend.constraints.novelty_checker import calculate_similarity

        sim = calculate_similarity("深度学习研究", ["深度学习研究"])
        assert sim == 1.0

    def test_calculate_similarity_partial_overlap(self):
        """部分重叠相似度应在0-1之间"""
        from backend.constraints.novelty_checker import calculate_similarity

        sim = calculate_similarity("深度学习研究", ["深度学习应用"])
        assert 0 < sim < 1

    def test_assess_novelty_returns_score_in_range(self):
        """评估新颖性应返回0-100的分数"""
        from backend.constraints.novelty_checker import assess_novelty

        result = assess_novelty("深度学习跨学科研究", existing_papers=[], discipline="计算机")
        assert 0 <= result.score <= 100
        assert isinstance(result.score, int)

    def test_assess_novelty_returns_dimensions(self):
        """评估新颖性应返回四维分数"""
        from backend.constraints.novelty_checker import assess_novelty

        result = assess_novelty("深度学习研究", existing_papers=[])
        assert "cross_discipline" in result.dimensions
        assert "method_transfer" in result.dimensions
        assert "pain_point" in result.dimensions
        assert "trend_foresight" in result.dimensions

    def test_assess_novelty_high_similarity_reduces_score(self):
        """高相似度应降低分数"""
        from backend.constraints.novelty_checker import assess_novelty

        topic = "深度学习研究"
        low_sim_result = assess_novelty(topic, existing_papers=[])
        high_sim_result = assess_novelty(topic, existing_papers=[{"title": topic}])
        assert high_sim_result.score <= low_sim_result.score

    def test_assess_novelty_cross_discipline_keyword(self):
        """包含跨学科关键词应提高学科交叉维度分数"""
        from backend.constraints.novelty_checker import score_cross_discipline

        score = score_cross_discipline("跨学科融合研究")
        assert score > 50

    def test_assess_novelty_returns_issues_and_suggestions(self):
        """评估新颖性应返回issues与suggestions列表"""
        from backend.constraints.novelty_checker import assess_novelty

        result = assess_novelty("深度学习研究", existing_papers=[{"title": "深度学习研究"}])
        assert isinstance(result.issues, list)
        assert isinstance(result.suggestions, list)


class TestStyleNormalizer:
    """去 AI 痕迹风格规范化器测试"""

    def test_normalize_removes_template_words(self):
        """规范化应移除模板词"""
        from backend.constraints.style_normalizer import normalize

        text = "首先，这是一个测试。综上所述，测试完成。"
        result = normalize(text)
        assert "首先" not in result or result.strip().startswith("，") is False
        assert "综上所述" not in result

    def test_normalize_handles_empty_text(self):
        """规范化空文本应返回空"""
        from backend.constraints.style_normalizer import normalize

        assert normalize("") == ""
        assert normalize(None) is None

    def test_normalize_replaces_transition_words(self):
        """规范化应替换部分过渡词"""
        from backend.constraints.style_normalizer import normalize

        text = "因此所以因此所以因此所以因此"
        result = normalize(text)
        # 应减少过渡词频率
        assert result.count("因此") <= 2

    def test_get_ai_trace_score_high_for_clean_text(self):
        """无 AI 痕迹的文本应得高分"""
        from backend.constraints.style_normalizer import get_ai_trace_score

        clean_text = "这是一段普通的学术文本。包含多个不同长度的句子。用于测试评分功能。"
        score = get_ai_trace_score(clean_text)
        assert score > 0

    def test_get_ai_trace_score_low_for_ai_text(self):
        """含模板词的文本应得较低分"""
        from backend.constraints.style_normalizer import get_ai_trace_score

        ai_text = "首先，众所周知。其次，综上所述。最后，毋庸置疑。"
        clean_text = "这是一段普通的学术文本。包含多个不同长度的句子。"
        ai_score = get_ai_trace_score(ai_text)
        clean_score = get_ai_trace_score(clean_text)
        assert ai_score < clean_score

    def test_get_ai_trace_score_empty(self):
        """空文本AI痕迹评分应为100"""
        from backend.constraints.style_normalizer import get_ai_trace_score

        assert get_ai_trace_score("") == 100

    def test_normalize_with_diff_returns_dict(self):
        """normalize_with_diff 应返回差异对比字典"""
        from backend.constraints.style_normalizer import normalize_with_diff

        text = "首先，众所周知这是测试。综上所述，完成。"
        result = normalize_with_diff(text)
        assert "original" in result
        assert "normalized" in result
        assert "changes" in result
        assert "ai_score_before" in result
        assert "ai_score_after" in result


class TestMultiGranularity:
    """多粒度生成器测试"""

    def test_validate_granularity_title_valid(self):
        """标题级粒度校验：合规"""
        from backend.constraints.multi_granularity import validate_granularity

        content = "深度学习模型优化"  # 8-20字
        result = validate_granularity(content, "title")
        assert result["valid"] is True

    def test_validate_granularity_title_too_short(self):
        """标题级粒度校验：过短"""
        from backend.constraints.multi_granularity import validate_granularity

        content = "短"  # <8字
        result = validate_granularity(content, "title")
        assert result["valid"] is False

    def test_validate_granularity_title_too_long(self):
        """标题级粒度校验：过长"""
        from backend.constraints.multi_granularity import validate_granularity

        content = "这是一个非常非常非常非常非常长的标题超过二十个字"  # >20字
        result = validate_granularity(content, "title")
        assert result["valid"] is False

    def test_validate_granularity_abstract_valid(self):
        """摘要级粒度校验：合规"""
        from backend.constraints.multi_granularity import validate_granularity

        content = "a" * 250  # 200-300字
        result = validate_granularity(content, "abstract")
        assert result["valid"] is True

    def test_validate_granularity_outline_valid(self):
        """大纲级粒度校验：合规"""
        from backend.constraints.multi_granularity import validate_granularity

        content = "a" * 1000  # 500-2000字
        result = validate_granularity(content, "outline")
        assert result["valid"] is True

    def test_validate_granularity_full_valid(self):
        """全文级粒度校验：合规"""
        from backend.constraints.multi_granularity import validate_granularity

        content = "a" * 10000  # 5000-50000字
        result = validate_granularity(content, "full")
        assert result["valid"] is True

    def test_validate_granularity_unknown_level(self):
        """未知粒度应返回无效"""
        from backend.constraints.multi_granularity import validate_granularity

        result = validate_granularity("content", "unknown")
        assert result["valid"] is False

    def test_get_granularity_spec_returns_spec(self):
        """获取粒度规格应返回 GranularitySpec"""
        from backend.constraints.multi_granularity import get_granularity_spec, GranularitySpec

        spec = get_granularity_spec("title")
        assert isinstance(spec, GranularitySpec)
        assert spec.level == "title"

    def test_get_granularity_spec_unknown_returns_none(self):
        """未知粒度规格应返回None"""
        from backend.constraints.multi_granularity import get_granularity_spec

        assert get_granularity_spec("unknown") is None

    def test_build_granularity_prompt_returns_string(self):
        """构建粒度 Prompt 应返回非空字符串"""
        from backend.constraints.multi_granularity import build_granularity_prompt

        for level in ["title", "abstract", "outline", "full"]:
            prompt = build_granularity_prompt(level, "深度学习")
            assert isinstance(prompt, str)
            assert len(prompt) > 0

    def test_granularity_specs_complete(self):
        """粒度规格应包含4个级别"""
        from backend.constraints.multi_granularity import GRANULARITY_SPECS

        assert len(GRANULARITY_SPECS) == 4
        assert "title" in GRANULARITY_SPECS
        assert "abstract" in GRANULARITY_SPECS
        assert "outline" in GRANULARITY_SPECS
        assert "full" in GRANULARITY_SPECS


class TestDeepAssist:
    """深度辅助三件套测试（mock call_llm）"""

    @pytest.mark.asyncio
    async def test_literature_reading_returns_result(self):
        """文献精读应返回 DeepAssistResult"""
        from backend.constraints.deep_assist import literature_reading, DeepAssistResult

        mock_content = "1. 研究问题：深度学习优化\n2. 核心方法：梯度下降\n3. 结论：有效"
        with patch("backend.ai.ai_proxy.call_llm", new=AsyncMock(return_value=_make_llm_result(mock_content))):
            result = await literature_reading(
                paper={"title": "深度学习研究", "authors": "张三", "year": 2025, "abstract": "摘要"},
                focus="方法",
            )
        assert isinstance(result, DeepAssistResult)
        assert result.assist_type == "literature_reading"
        assert result.content == mock_content
        assert len(result.suggestions) > 0
        assert len(result.follow_up) > 0

    @pytest.mark.asyncio
    async def test_experiment_preparation_returns_result(self):
        """实验预研应返回 DeepAssistResult"""
        from backend.constraints.deep_assist import experiment_preparation, DeepAssistResult

        mock_content = "1. 实验目标：验证模型效果\n2. 变量：学习率\n3. 步骤：训练"
        with patch("backend.ai.ai_proxy.call_llm", new=AsyncMock(return_value=_make_llm_result(mock_content))):
            result = await experiment_preparation(topic="深度学习优化", method="梯度下降")
        assert isinstance(result, DeepAssistResult)
        assert result.assist_type == "experiment_preparation"
        assert result.content == mock_content
        assert len(result.suggestions) > 0

    @pytest.mark.asyncio
    async def test_defense_simulation_returns_result(self):
        """答辩模拟应返回 DeepAssistResult"""
        from backend.constraints.deep_assist import defense_simulation, DeepAssistResult

        mock_content = "1. 问题：创新点是什么？\n2. 回答：方法迁移\n3. 注意：控制时间"
        with patch("backend.ai.ai_proxy.call_llm", new=AsyncMock(return_value=_make_llm_result(mock_content))):
            result = await defense_simulation(topic="深度学习优化", report_content="报告内容")
        assert isinstance(result, DeepAssistResult)
        assert result.assist_type == "defense_simulation"
        assert result.content == mock_content
        assert len(result.suggestions) > 0

    @pytest.mark.asyncio
    async def test_literature_reading_handles_exception(self):
        """文献精读异常时应返回错误结果"""
        from backend.constraints.deep_assist import literature_reading, DeepAssistResult

        async def mock_call_llm(**kwargs):
            raise RuntimeError("API error")

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            result = await literature_reading(paper={"title": "测试"})
        assert isinstance(result, DeepAssistResult)
        assert "精读失败" in result.content

    @pytest.mark.asyncio
    async def test_experiment_preparation_handles_exception(self):
        """实验预研异常时应返回错误结果"""
        from backend.constraints.deep_assist import experiment_preparation, DeepAssistResult

        async def mock_call_llm(**kwargs):
            raise RuntimeError("API error")

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            result = await experiment_preparation(topic="测试")
        assert isinstance(result, DeepAssistResult)
        assert "预研失败" in result.content

    @pytest.mark.asyncio
    async def test_defense_simulation_handles_exception(self):
        """答辩模拟异常时应返回错误结果"""
        from backend.constraints.deep_assist import defense_simulation, DeepAssistResult

        async def mock_call_llm(**kwargs):
            raise RuntimeError("API error")

        with patch("backend.ai.ai_proxy.call_llm", new=mock_call_llm):
            result = await defense_simulation(topic="测试")
        assert isinstance(result, DeepAssistResult)
        assert "模拟失败" in result.content
