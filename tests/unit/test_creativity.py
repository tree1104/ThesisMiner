"""创意引擎模块单元测试

测试 backend/creativity/ 下的三个模块：
  - academic_lineage.py: 学术谱系链接器
  - cross_domain.py: 跨域联想与趋势嫁接
  - problem_awareness.py: 问题意识激发器

覆盖以下功能：
  - extend_mentor_project: 基于导师项目生成子课题
  - inherit_senior_work: 继承同门论文
  - generate_lineage_candidates: 生成谱系候选列表
  - cross_domain_association: 跨域联想
  - trend_grafting: 趋势嫁接
  - inspire_humanities_social: 人文社科问题意识
  - inspire_science_engineering: 理工科问题意识
  - inspire: 问题意识路由

测试策略：
  - 纯逻辑测试，不依赖数据库
  - 覆盖各种输入组合
  - 验证返回字典的结构与内容
"""
import os
import sys

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.creativity.academic_lineage import (
    extend_mentor_project,
    inherit_senior_work,
    generate_lineage_candidates,
)
from backend.creativity.cross_domain import (
    cross_domain_association,
    trend_grafting,
)
from backend.creativity.problem_awareness import (
    inspire_humanities_social,
    inspire_science_engineering,
    inspire,
)


# ===== 测试类：extend_mentor_project =====

class TestExtendMentorProject:
    """测试 extend_mentor_project 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        result = extend_mentor_project("导师项目")
        assert isinstance(result, dict)

    def test_contains_required_fields(self):
        """应包含所有必需字段。"""
        result = extend_mentor_project("导师项目")
        assert "inspiration_source" in result
        assert "direction" in result
        assert "suggestion" in result
        assert "prompt" in result

    def test_inspiration_source_is_mentor_project(self):
        """inspiration_source 应为 mentor_project。"""
        result = extend_mentor_project("项目")
        assert result["inspiration_source"] == "mentor_project"

    def test_direction_contains_project_name(self):
        """direction 应包含项目名。"""
        result = extend_mentor_project("深度学习项目")
        assert "深度学习项目" in result["direction"]

    def test_default_timeframe_one_year(self):
        """默认时间框架应为 1 年。"""
        result = extend_mentor_project("项目")
        assert "1" in result["suggestion"]

    def test_custom_timeframe(self):
        """自定义时间框架。"""
        result = extend_mentor_project("项目", timeframe_years=2)
        assert "2" in result["suggestion"]

    def test_prompt_contains_project_name(self):
        """prompt 应包含项目名。"""
        result = extend_mentor_project("AI研究项目")
        assert "AI研究项目" in result["prompt"]

    def test_empty_project(self):
        """空项目名应仍能执行。"""
        result = extend_mentor_project("")
        assert isinstance(result, dict)


# ===== 测试类：inherit_senior_work =====

class TestInheritSeniorWork:
    """测试 inherit_senior_work 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        result = inherit_senior_work("同门论文")
        assert isinstance(result, dict)

    def test_contains_required_fields(self):
        """应包含所有必需字段。"""
        result = inherit_senior_work("论文")
        assert "inspiration_source" in result
        assert "direction" in result
        assert "suggestion" in result
        assert "prompt" in result

    def test_inspiration_source_is_senior_inherit(self):
        """inspiration_source 应为 senior_inherit。"""
        result = inherit_senior_work("论文")
        assert result["inspiration_source"] == "senior_inherit"

    def test_direction_contains_thesis_title(self):
        """direction 应包含论文标题。"""
        result = inherit_senior_work("深度学习论文")
        assert "深度学习论文" in result["direction"]

    def test_default_adjacent_scenario(self):
        """默认相邻场景应使用"相邻场景"。"""
        result = inherit_senior_work("论文")
        assert "相邻场景" in result["suggestion"]

    def test_custom_adjacent_scenario(self):
        """自定义相邻场景。"""
        result = inherit_senior_work("论文", adjacent_scenario="医疗领域")
        assert "医疗领域" in result["suggestion"]

    def test_prompt_contains_thesis_title(self):
        """prompt 应包含论文标题。"""
        result = inherit_senior_work("AI论文")
        assert "AI论文" in result["prompt"]

    def test_empty_thesis(self):
        """空论文标题应仍能执行。"""
        result = inherit_senior_work("")
        assert isinstance(result, dict)


# ===== 测试类：generate_lineage_candidates =====

class TestGenerateLineageCandidates:
    """测试 generate_lineage_candidates 函数。"""

    def test_empty_inputs(self):
        """空输入应返回空列表。"""
        result = generate_lineage_candidates([], [])
        assert result == []

    def test_only_mentor_projects(self):
        """只有导师项目时应生成对应候选。"""
        result = generate_lineage_candidates(["项目1", "项目2"], [])
        assert len(result) == 2
        assert all(r["inspiration_source"] == "mentor_project" for r in result)

    def test_only_senior_theses(self):
        """只有同门论文时应生成对应候选。"""
        result = generate_lineage_candidates([], ["论文1", "论文2"])
        assert len(result) == 2
        assert all(r["inspiration_source"] == "senior_inherit" for r in result)

    def test_both_inputs(self):
        """同时有导师项目与同门论文。"""
        result = generate_lineage_candidates(["项目1"], ["论文1", "论文2"])
        assert len(result) == 3

    def test_order_mentor_first(self):
        """导师项目候选应在同门论文候选之前。"""
        result = generate_lineage_candidates(["项目1"], ["论文1"])
        assert result[0]["inspiration_source"] == "mentor_project"
        assert result[1]["inspiration_source"] == "senior_inherit"

    def test_multiple_projects_and_theses(self):
        """多个项目与论文。"""
        result = generate_lineage_candidates(
            ["项目1", "项目2", "项目3"],
            ["论文1", "论文2"],
        )
        assert len(result) == 5


# ===== 测试类：cross_domain_association =====

class TestCrossDomainAssociation:
    """测试 cross_domain_association 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        result = cross_domain_association("领域A", "领域B")
        assert isinstance(result, dict)

    def test_contains_required_fields(self):
        """应包含所有必需字段。"""
        result = cross_domain_association("A", "B")
        assert "inspiration_source" in result
        assert "direction" in result
        assert "suggestion" in result
        assert "prompt" in result

    def test_inspiration_source_is_cross_domain(self):
        """inspiration_source 应为 cross_domain。"""
        result = cross_domain_association("A", "B")
        assert result["inspiration_source"] == "cross_domain"

    def test_direction_contains_both_domains(self):
        """direction 应包含两个领域。"""
        result = cross_domain_association("深度学习", "教育")
        assert "深度学习" in result["direction"]
        assert "教育" in result["direction"]

    def test_suggestion_mentions_grafting(self):
        """suggestion 应提及嫁接。"""
        result = cross_domain_association("A", "B")
        assert "嫁接" in result["suggestion"]

    def test_prompt_contains_both_domains(self):
        """prompt 应包含两个领域。"""
        result = cross_domain_association("AI", "医疗")
        assert "AI" in result["prompt"]
        assert "医疗" in result["prompt"]


# ===== 测试类：trend_grafting =====

class TestTrendGrafting:
    """测试 trend_grafting 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        result = trend_grafting(["关键词1"])
        assert isinstance(result, dict)

    def test_contains_required_fields(self):
        """应包含所有必需字段。"""
        result = trend_grafting(["关键词"])
        assert "inspiration_source" in result
        assert "direction" in result
        assert "suggestion" in result
        assert "prompt" in result

    def test_inspiration_source_is_trend_graft(self):
        """inspiration_source 应为 trend_graft。"""
        result = trend_grafting(["关键词"])
        assert result["inspiration_source"] == "trend_graft"

    def test_direction_joins_keywords(self):
        """direction 应连接关键词。"""
        result = trend_grafting(["AI", "教育", "深度学习"])
        assert "AI" in result["direction"]
        assert "教育" in result["direction"]
        assert "深度学习" in result["direction"]

    def test_single_keyword(self):
        """单个关键词应正常工作。"""
        result = trend_grafting(["AI"])
        assert "AI" in result["direction"]

    def test_empty_keywords_list(self):
        """空关键词列表应仍能执行。"""
        result = trend_grafting([])
        assert isinstance(result, dict)


# ===== 测试类：inspire_humanities_social =====

class TestInspireHumanitiesSocial:
    """测试 inspire_humanities_social 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        result = inspire_humanities_social("教育公平")
        assert isinstance(result, dict)

    def test_contains_required_fields(self):
        """应包含所有必需字段。"""
        result = inspire_humanities_social("主题")
        assert "discipline_type" in result
        assert "problem" in result
        assert "angle" in result
        assert "prompt" in result

    def test_discipline_type_is_humanities(self):
        """discipline_type 应为 humanities_social。"""
        result = inspire_humanities_social("主题")
        assert result["discipline_type"] == "humanities_social"

    def test_problem_contains_topic(self):
        """problem 应包含主题。"""
        result = inspire_humanities_social("教育公平")
        assert "教育公平" in result["problem"]

    def test_prompt_contains_topic(self):
        """prompt 应包含主题。"""
        result = inspire_humanities_social("社会问题")
        assert "社会问题" in result["prompt"]

    def test_with_context(self):
        """带 context 参数应正常工作。"""
        result = inspire_humanities_social("主题", context="背景信息")
        assert isinstance(result, dict)

    def test_empty_topic(self):
        """空主题应仍能执行。"""
        result = inspire_humanities_social("")
        assert isinstance(result, dict)


# ===== 测试类：inspire_science_engineering =====

class TestInspireScienceEngineering:
    """测试 inspire_science_engineering 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        result = inspire_science_engineering("算法优化")
        assert isinstance(result, dict)

    def test_contains_required_fields(self):
        """应包含所有必需字段。"""
        result = inspire_science_engineering("主题")
        assert "discipline_type" in result
        assert "problem" in result
        assert "angle" in result
        assert "prompt" in result

    def test_discipline_type_is_science(self):
        """discipline_type 应为 science_engineering。"""
        result = inspire_science_engineering("主题")
        assert result["discipline_type"] == "science_engineering"

    def test_problem_contains_topic(self):
        """problem 应包含主题。"""
        result = inspire_science_engineering("算法优化")
        assert "算法优化" in result["problem"]

    def test_prompt_contains_topic(self):
        """prompt 应包含主题。"""
        result = inspire_science_engineering("系统设计")
        assert "系统设计" in result["prompt"]

    def test_with_context(self):
        """带 context 参数应正常工作。"""
        result = inspire_science_engineering("主题", context="工程背景")
        assert isinstance(result, dict)


# ===== 测试类：inspire 路由函数 =====

class TestInspireRouter:
    """测试 inspire 路由函数。"""

    def test_routes_to_humanities(self):
        """人文社科应路由到 inspire_humanities_social。"""
        result = inspire("humanities_social", "教育公平")
        assert result["discipline_type"] == "humanities_social"

    def test_routes_to_science(self):
        """理工科应路由到 inspire_science_engineering。"""
        result = inspire("science_engineering", "算法优化")
        assert result["discipline_type"] == "science_engineering"

    def test_unsupported_discipline_raises(self):
        """不支持的学科类型应抛出 ValueError。"""
        with pytest.raises(ValueError):
            inspire("unsupported_discipline", "主题")

    def test_with_context_param(self):
        """带 context 参数应正常工作。"""
        result = inspire("humanities_social", "主题", context="背景")
        assert isinstance(result, dict)

    def test_empty_topic(self):
        """空主题应仍能路由。"""
        result = inspire("science_engineering", "")
        assert isinstance(result, dict)


# ===== 集成测试 =====

class TestCreativityIntegration:
    """创意引擎集成测试。"""

    def test_full_creativity_flow(self):
        """测试完整创意生成流程。"""
        # 1. 谱系候选
        lineage = generate_lineage_candidates(
            ["导师项目A"],
            ["同门论文B"],
        )
        assert len(lineage) == 2
        # 2. 跨域联想
        cross = cross_domain_association("深度学习", "教育")
        assert cross["inspiration_source"] == "cross_domain"
        # 3. 趋势嫁接
        trend = trend_grafting(["AI", "教育", "个性化"])
        assert trend["inspiration_source"] == "trend_graft"
        # 4. 问题意识
        humanities = inspire("humanities_social", "教育公平")
        science = inspire("science_engineering", "算法优化")
        assert humanities["discipline_type"] == "humanities_social"
        assert science["discipline_type"] == "science_engineering"

    def test_all_inspiration_sources(self):
        """测试所有灵感来源类型。"""
        sources = set()
        # 谱系来源
        lineage = generate_lineage_candidates(["项目"], ["论文"])
        for c in lineage:
            sources.add(c["inspiration_source"])
        # 跨域来源
        cross = cross_domain_association("A", "B")
        sources.add(cross["inspiration_source"])
        # 趋势来源
        trend = trend_grafting(["关键词"])
        sources.add(trend["inspiration_source"])
        # 验证所有来源类型
        assert "mentor_project" in sources
        assert "senior_inherit" in sources
        assert "cross_domain" in sources
        assert "trend_graft" in sources
