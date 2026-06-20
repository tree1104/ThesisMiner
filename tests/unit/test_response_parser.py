"""response_parser 模块单元测试

覆盖 backend/ai/response_parser.py 中的所有组件：
- ParsedResponse: 解析结果数据类
- JSONExtractor: JSON 提取器（直接解析/代码块提取/裸JSON提取/错误恢复/数组提取）
- MarkdownParser: Markdown 解析器（标题/代码块/链接/图片/列表/引用/表格/纯文本/结构）
- CitationExtractor: 引用提取器（数字/作者年份/DOI/arXiv/URL/去重）
- ResponseValidator: 响应验证器（必填字段/类型/长度/非空/结构）
- ResponseNormalizer: 响应标准化器（提案/候选/评估/检索结果）
- ResponseParser: 解析器主类（自动检测/JSON/Markdown/混合/便捷方法）
- 模块级便捷函数
"""
import json
import pytest

from backend.ai.response_parser import (
    ParsedResponse,
    JSONExtractor,
    MarkdownParser,
    CitationExtractor,
    ResponseValidator,
    ResponseNormalizer,
    ResponseParser,
    get_parser,
    parse_response,
    extract_json,
    extract_citations,
    parse_markdown,
    validate_json_response,
    normalize_proposal,
    RESPONSE_TYPES,
)


# ===== ParsedResponse 测试 =====


class TestParsedResponse:
    """ParsedResponse 数据类测试"""

    def test_default_values(self):
        """默认值"""
        resp = ParsedResponse()
        assert resp.type == "text"
        assert resp.content is None
        assert resp.raw == ""
        assert resp.json_data is None
        assert resp.markdown == ""
        assert resp.text == ""
        assert resp.citations == []
        assert resp.code_blocks == []
        assert resp.metadata == {}
        assert resp.errors == []
        assert resp.is_valid is True

    def test_custom_values(self):
        """自定义值"""
        resp = ParsedResponse(
            type="json",
            content={"key": "value"},
            raw='{"key": "value"}',
            json_data={"key": "value"},
        )
        assert resp.type == "json"
        assert resp.content == {"key": "value"}
        assert resp.json_data == {"key": "value"}

    def test_to_dict(self):
        """转字典"""
        resp = ParsedResponse(type="json", content="test")
        d = resp.to_dict()
        assert d["type"] == "json"
        assert d["content"] == "test"
        assert "json_data" in d
        assert "markdown" in d
        assert "text" in d
        assert "citations" in d
        assert "code_blocks" in d
        assert "metadata" in d
        assert "errors" in d
        assert "is_valid" in d

    def test_with_errors(self):
        """带错误"""
        resp = ParsedResponse(is_valid=False, errors=["错误1", "错误2"])
        assert resp.is_valid is False
        assert len(resp.errors) == 2


# ===== JSONExtractor 测试 =====


class TestJSONExtractor:
    """JSONExtractor JSON 提取器测试"""

    def test_extract_direct_json(self):
        """直接解析 JSON"""
        text = '{"key": "value"}'
        result = JSONExtractor.extract(text)
        assert result == {"key": "value"}

    def test_extract_from_code_block(self):
        """从代码块提取"""
        text = '```json\n{"key": "value"}\n```'
        result = JSONExtractor.extract(text)
        assert result == {"key": "value"}

    def test_extract_from_code_block_no_language(self):
        """无语言标记代码块"""
        text = '```\n{"key": "value"}\n```'
        result = JSONExtractor.extract(text)
        assert result == {"key": "value"}

    def test_extract_bare_json_in_text(self):
        """从文本中提取裸 JSON"""
        text = 'Here is the result: {"key": "value"} and more text'
        result = JSONExtractor.extract(text)
        assert result == {"key": "value"}

    def test_extract_nested_json(self):
        """嵌套 JSON"""
        text = '{"outer": {"inner": "value"}}'
        result = JSONExtractor.extract(text)
        assert result == {"outer": {"inner": "value"}}

    def test_extract_empty_text(self):
        """空文本"""
        assert JSONExtractor.extract("") is None
        assert JSONExtractor.extract(None) is None

    def test_extract_no_json(self):
        """无 JSON 文本"""
        assert JSONExtractor.extract("just plain text") is None

    def test_extract_invalid_json(self):
        """无效 JSON"""
        assert JSONExtractor.extract("{invalid json}") is None

    def test_extract_with_trailing_comma(self):
        """尾部多余逗号（错误恢复）"""
        text = '{"key": "value",}'
        result = JSONExtractor.extract(text)
        assert result == {"key": "value"}

    def test_extract_with_single_quotes(self):
        """单引号 JSON（错误恢复）"""
        text = "{'key': 'value'}"
        result = JSONExtractor.extract(text)
        assert result == {"key": "value"}

    def test_extract_with_comments(self):
        """带注释 JSON（错误恢复）"""
        text = '{\n  // comment\n  "key": "value"\n}'
        result = JSONExtractor.extract(text)
        assert result == {"key": "value"}

    def test_extract_list_direct(self):
        """直接解析数组"""
        text = '[1, 2, 3]'
        result = JSONExtractor.extract_list(text)
        assert result == [1, 2, 3]

    def test_extract_list_from_code_block(self):
        """从代码块提取数组"""
        text = '```json\n[1, 2, 3]\n```'
        result = JSONExtractor.extract_list(text)
        assert result == [1, 2, 3]

    def test_extract_list_in_text(self):
        """从文本提取数组"""
        text = 'Results: [1, 2, 3] done'
        result = JSONExtractor.extract_list(text)
        assert result == [1, 2, 3]

    def test_extract_list_empty(self):
        """空文本"""
        assert JSONExtractor.extract_list("") is None

    def test_extract_list_no_array(self):
        """无数组"""
        assert JSONExtractor.extract_list('{"key": "value"}') is None

    def test_extract_all_json_blocks(self):
        """提取所有 JSON 代码块"""
        text = '```json\n{"a": 1}\n```\nText\n```json\n{"b": 2}\n```'
        results = JSONExtractor.extract_all_json_blocks(text)
        assert len(results) == 2
        assert results[0] == {"a": 1}
        assert results[1] == {"b": 2}

    def test_extract_all_json_blocks_empty(self):
        """无代码块"""
        assert JSONExtractor.extract_all_json_blocks("plain text") == []

    def test_fix_json_trailing_comma(self):
        """修复尾部逗号"""
        fixed = JSONExtractor._fix_json('{"key": "value",}')
        assert fixed is not None

    def test_fix_json_single_quotes(self):
        """修复单引号"""
        fixed = JSONExtractor._fix_json("{'key': 'value'}")
        assert fixed is not None

    def test_fix_json_empty(self):
        """空文本"""
        assert JSONExtractor._fix_json("") is None
        assert JSONExtractor._fix_json(None) is None

    def test_extract_priority(self):
        """提取优先级（直接解析优先）"""
        text = '{"direct": true}'
        result = JSONExtractor.extract(text)
        assert result == {"direct": True}

    def test_extract_complex_nested(self):
        """复杂嵌套结构"""
        data = {
            "level1": {
                "level2": {
                    "level3": [1, 2, {"deep": True}]
                }
            }
        }
        text = json.dumps(data)
        result = JSONExtractor.extract(text)
        assert result == data


# ===== MarkdownParser 测试 =====


class TestMarkdownParser:
    """MarkdownParser Markdown 解析器测试"""

    def test_extract_headings(self):
        """提取标题"""
        text = "# Title 1\n## Title 2\n### Title 3"
        headings = MarkdownParser.extract_headings(text)
        assert len(headings) == 3
        assert headings[0] == {"level": 1, "text": "Title 1"}
        assert headings[1] == {"level": 2, "text": "Title 2"}
        assert headings[2] == {"level": 3, "text": "Title 3"}

    def test_extract_headings_empty(self):
        """空文本"""
        assert MarkdownParser.extract_headings("") == []

    def test_extract_headings_no_headings(self):
        """无标题"""
        assert MarkdownParser.extract_headings("plain text") == []

    def test_extract_code_blocks(self):
        """提取代码块"""
        text = "```python\nprint('hello')\n```\nText\n```json\n{\"a\": 1}\n```"
        blocks = MarkdownParser.extract_code_blocks(text)
        assert len(blocks) == 2
        assert blocks[0]["language"] == "python"
        assert "print" in blocks[0]["code"]
        assert blocks[1]["language"] == "json"

    def test_extract_code_blocks_no_language(self):
        """无语言代码块"""
        text = "```\ncode\n```"
        blocks = MarkdownParser.extract_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0]["language"] == "text"

    def test_extract_code_blocks_empty(self):
        """空文本"""
        assert MarkdownParser.extract_code_blocks("") == []

    def test_extract_links(self):
        """提取链接"""
        text = "[Google](https://google.com) and [GitHub](https://github.com)"
        links = MarkdownParser.extract_links(text)
        assert len(links) == 2
        assert links[0] == {"text": "Google", "url": "https://google.com"}
        assert links[1] == {"text": "GitHub", "url": "https://github.com"}

    def test_extract_links_excludes_images(self):
        """链接排除图片"""
        text = "![Image](image.png) and [Link](url)"
        links = MarkdownParser.extract_links(text)
        assert len(links) == 1
        assert links[0]["text"] == "Link"

    def test_extract_links_empty(self):
        """空文本"""
        assert MarkdownParser.extract_links("") == []

    def test_extract_images(self):
        """提取图片"""
        text = "![Alt text](image.png) and ![Another](photo.jpg)"
        images = MarkdownParser.extract_images(text)
        assert len(images) == 2
        assert images[0] == {"alt": "Alt text", "url": "image.png"}
        assert images[1] == {"alt": "Another", "url": "photo.jpg"}

    def test_extract_images_empty(self):
        """空文本"""
        assert MarkdownParser.extract_images("") == []

    def test_extract_lists(self):
        """提取列表"""
        text = "- item 1\n- item 2\n1. first\n2. second"
        lists = MarkdownParser.extract_lists(text)
        assert len(lists["unordered"]) == 2
        assert len(lists["ordered"]) == 2
        assert "item 1" in lists["unordered"]
        assert "first" in lists["ordered"]

    def test_extract_lists_empty(self):
        """空文本"""
        result = MarkdownParser.extract_lists("")
        assert result == {"ordered": [], "unordered": []}

    def test_extract_blockquotes(self):
        """提取引用块"""
        text = "> Quote 1\n> Quote 2\nNormal text"
        quotes = MarkdownParser.extract_blockquotes(text)
        assert len(quotes) == 2
        assert "Quote 1" in quotes[0]

    def test_extract_blockquotes_empty(self):
        """空文本"""
        assert MarkdownParser.extract_blockquotes("") == []

    def test_extract_tables(self):
        """提取表格"""
        text = "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1   | Cell 2   |"
        tables = MarkdownParser.extract_tables(text)
        assert len(tables) == 1
        assert "Header 1" in tables[0]["headers"]
        assert len(tables[0]["rows"]) == 1

    def test_extract_tables_empty(self):
        """空文本"""
        assert MarkdownParser.extract_tables("") == []

    def test_to_plain_text(self):
        """转纯文本"""
        text = "# Title\n**bold** and *italic*\n[link](url)"
        plain = MarkdownParser.to_plain_text(text)
        assert "#" not in plain
        assert "**" not in plain
        assert "*" not in plain
        assert "Title" in plain
        assert "bold" in plain
        assert "link" in plain

    def test_to_plain_text_empty(self):
        """空文本"""
        assert MarkdownParser.to_plain_text("") == ""

    def test_to_plain_text_code_block(self):
        """代码块转纯文本"""
        text = "```python\nprint('hello')\n```"
        plain = MarkdownParser.to_plain_text(text)
        assert "print" in plain
        assert "```" not in plain

    def test_get_structure(self):
        """获取结构"""
        text = "# Title\n- item\n[link](url)\n![img](pic.png)"
        structure = MarkdownParser.get_structure(text)
        assert "headings" in structure
        assert "code_blocks" in structure
        assert "links" in structure
        assert "images" in structure
        assert "lists" in structure
        assert "blockquotes" in structure
        assert "tables" in structure
        assert len(structure["headings"]) == 1
        assert len(structure["links"]) == 1
        assert len(structure["images"]) == 1


# ===== CitationExtractor 测试 =====


class TestCitationExtractor:
    """CitationExtractor 引用提取器测试"""

    def test_extract_numeric(self):
        """提取数字引用"""
        text = "This is cited [1] and also [2] and [10]"
        citations = CitationExtractor.extract_numeric(text)
        assert citations == [1, 2, 10]

    def test_extract_numeric_empty(self):
        """空文本"""
        assert CitationExtractor.extract_numeric("") == []

    def test_extract_numeric_none(self):
        """无数字引用"""
        assert CitationExtractor.extract_numeric("no citations") == []

    def test_extract_author_year(self):
        """提取作者-年份引用"""
        text = "As shown (Smith, 2020) and (Johnson et al., 2021)"
        results = CitationExtractor.extract_author_year(text)
        assert len(results) == 2
        assert results[0]["author"] == "Smith"
        assert results[0]["year"] == "2020"

    def test_extract_author_year_empty(self):
        """空文本"""
        assert CitationExtractor.extract_author_year("") == []

    def test_extract_dois(self):
        """提取 DOI"""
        text = "See https://doi.org/10.1234/test.5678 for details"
        dois = CitationExtractor.extract_dois(text)
        assert len(dois) == 1
        assert "10.1234/test.5678" in dois[0]

    def test_extract_dois_empty(self):
        """空文本"""
        assert CitationExtractor.extract_dois("") == []

    def test_extract_arxiv_ids(self):
        """提取 arXiv ID"""
        text = "Refer to arXiv: 2023.12345 for the paper"
        ids = CitationExtractor.extract_arxiv_ids(text)
        assert len(ids) == 1
        assert "2023.12345" in ids[0]

    def test_extract_arxiv_ids_with_version(self):
        """带版本号 arXiv"""
        text = "arXiv: 2023.12345v2"
        ids = CitationExtractor.extract_arxiv_ids(text)
        assert len(ids) == 1

    def test_extract_arxiv_ids_empty(self):
        """空文本"""
        assert CitationExtractor.extract_arxiv_ids("") == []

    def test_extract_urls(self):
        """提取 URL"""
        text = "Visit https://example.com and http://test.org/path"
        urls = CitationExtractor.extract_urls(text)
        assert len(urls) == 2

    def test_extract_urls_empty(self):
        """空文本"""
        assert CitationExtractor.extract_urls("") == []

    def test_extract_all(self):
        """提取所有引用"""
        text = "Cited [1] and (Smith, 2020) and arXiv: 2023.12345"
        citations = CitationExtractor.extract_all(text)
        assert len(citations) >= 3
        types = [c["type"] for c in citations]
        assert "numeric" in types
        assert "author_year" in types
        assert "arxiv" in types

    def test_extract_all_with_position(self):
        """带位置信息"""
        text = "Cited [1] here"
        citations = CitationExtractor.extract_all(text)
        assert "position" in citations[0]
        assert citations[0]["position"] >= 0

    def test_extract_all_empty(self):
        """空文本"""
        assert CitationExtractor.extract_all("") == []

    def test_deduplicate(self):
        """去重"""
        citations = [
            {"type": "numeric", "value": "1", "position": 0},
            {"type": "numeric", "value": "1", "position": 10},
            {"type": "numeric", "value": "2", "position": 20},
        ]
        unique = CitationExtractor.deduplicate(citations)
        assert len(unique) == 2

    def test_deduplicate_different_types(self):
        """不同类型不去重"""
        citations = [
            {"type": "numeric", "value": "1", "position": 0},
            {"type": "doi", "value": "1", "position": 10},
        ]
        unique = CitationExtractor.deduplicate(citations)
        assert len(unique) == 2


# ===== ResponseValidator 测试 =====


class TestResponseValidator:
    """ResponseValidator 响应验证器测试"""

    def test_validate_json_response_valid(self):
        """验证有效响应"""
        data = {"key1": "value1", "key2": "value2"}
        result = ResponseValidator.validate_json_response(data, ["key1", "key2"])
        assert result["valid"] is True
        assert result["missing"] == []

    def test_validate_json_response_missing(self):
        """验证缺失字段"""
        data = {"key1": "value1"}
        result = ResponseValidator.validate_json_response(data, ["key1", "key2"])
        assert result["valid"] is False
        assert "key2" in result["missing"]

    def test_validate_json_response_none_value(self):
        """验证 None 值字段"""
        data = {"key1": None}
        result = ResponseValidator.validate_json_response(data, ["key1"])
        assert result["valid"] is False
        assert "key1" in result["missing"]

    def test_validate_json_response_not_dict(self):
        """非字典响应"""
        result = ResponseValidator.validate_json_response("not a dict", ["key1"])
        assert result["valid"] is False

    def test_validate_field_type_valid(self):
        """验证字段类型有效"""
        data = {"name": "test", "age": 25}
        specs = {"name": str, "age": int}
        result = ResponseValidator.validate_field_type(data, specs)
        assert result["valid"] is True

    def test_validate_field_type_invalid(self):
        """验证字段类型无效"""
        data = {"name": 123, "age": "twenty"}
        specs = {"name": str, "age": int}
        result = ResponseValidator.validate_field_type(data, specs)
        assert result["valid"] is False
        assert len(result["errors"]) == 2

    def test_validate_field_type_none_allowed(self):
        """None 值不验证类型"""
        data = {"name": None}
        specs = {"name": str}
        result = ResponseValidator.validate_field_type(data, specs)
        assert result["valid"] is True

    def test_validate_field_length_valid(self):
        """验证字段长度有效"""
        data = {"name": "test", "items": [1, 2, 3]}
        specs = {"name": (1, 100), "items": (1, 10)}
        result = ResponseValidator.validate_field_length(data, specs)
        assert result["valid"] is True

    def test_validate_field_length_too_short(self):
        """字段太短"""
        data = {"name": "a"}
        specs = {"name": (5, 100)}
        result = ResponseValidator.validate_field_length(data, specs)
        assert result["valid"] is False

    def test_validate_field_length_too_long(self):
        """字段太长"""
        data = {"name": "a" * 200}
        specs = {"name": (1, 100)}
        result = ResponseValidator.validate_field_length(data, specs)
        assert result["valid"] is False

    def test_validate_not_empty(self):
        """验证非空"""
        assert ResponseValidator.validate_not_empty("hello") is True
        assert ResponseValidator.validate_not_empty("") is False
        assert ResponseValidator.validate_not_empty("   ") is False
        assert ResponseValidator.validate_not_empty("a", min_length=2) is False

    def test_validate_json_structure_valid(self):
        """验证 JSON 结构有效"""
        data = {"name": "test", "age": 25}
        schema = {
            "name": {"type": str, "required": True, "min": 1, "max": 100},
            "age": {"type": int, "required": True, "min": 0, "max": 150},
        }
        result = ResponseValidator.validate_json_structure(data, schema)
        assert result["valid"] is True

    def test_validate_json_structure_missing_required(self):
        """缺失必填字段"""
        data = {"name": "test"}
        schema = {
            "name": {"type": str, "required": True},
            "age": {"type": int, "required": True},
        }
        result = ResponseValidator.validate_json_structure(data, schema)
        assert result["valid"] is False

    def test_validate_json_structure_wrong_type(self):
        """类型错误"""
        data = {"age": "not a number"}
        schema = {"age": {"type": int, "required": True}}
        result = ResponseValidator.validate_json_structure(data, schema)
        assert result["valid"] is False

    def test_validate_json_structure_out_of_range(self):
        """值超出范围"""
        data = {"age": 200}
        schema = {"age": {"type": int, "required": True, "min": 0, "max": 150}}
        result = ResponseValidator.validate_json_structure(data, schema)
        assert result["valid"] is False

    def test_validate_json_structure_optional_missing(self):
        """可选字段缺失"""
        data = {"name": "test"}
        schema = {
            "name": {"type": str, "required": True},
            "age": {"type": int, "required": False},
        }
        result = ResponseValidator.validate_json_structure(data, schema)
        assert result["valid"] is True


# ===== ResponseNormalizer 测试 =====


class TestResponseNormalizer:
    """ResponseNormalizer 响应标准化器测试"""

    def test_normalize_proposal_complete(self):
        """标准化完整提案"""
        data = {
            "title": "Test Title",
            "problem_awareness": "Problem description",
            "research_significance": {"theoretical": "sig1", "practical": "sig2"},
            "literature_review": "Literature",
            "differentiation": "Innovation",
            "research_content": ["content1", "content2"],
            "feasibility": {"time": "6 months", "resources": "lab", "methodology": "ML"},
            "confidence_score": 0.85,
            "inspiration_source": "paper",
        }
        result = ResponseNormalizer.normalize_proposal(data)
        assert result["title"] == "Test Title"
        assert result["confidence_score"] == 0.85
        assert isinstance(result["research_content"], list)

    def test_normalize_proposal_minimal(self):
        """标准化最小提案"""
        data = {"title": "Test"}
        result = ResponseNormalizer.normalize_proposal(data)
        assert result["title"] == "Test"
        assert result["confidence_score"] == 0.5
        assert isinstance(result["research_content"], list)
        assert isinstance(result["feasibility"], dict)

    def test_normalize_proposal_string_research_content(self):
        """字符串研究内容转列表"""
        data = {"title": "Test", "research_content": "single content"}
        result = ResponseNormalizer.normalize_proposal(data)
        assert isinstance(result["research_content"], list)
        assert result["research_content"] == ["single content"]

    def test_normalize_proposal_string_significance(self):
        """字符串研究意义转字典"""
        data = {"title": "Test", "research_significance": "just a string"}
        result = ResponseNormalizer.normalize_proposal(data)
        assert isinstance(result["research_significance"], dict)
        assert "theoretical" in result["research_significance"]

    def test_normalize_proposal_confidence_over_100(self):
        """置信度超过 100"""
        data = {"title": "Test", "confidence_score": 150}
        result = ResponseNormalizer.normalize_proposal(data)
        assert result["confidence_score"] == 1.0

    def test_normalize_proposal_confidence_negative(self):
        """负置信度"""
        data = {"title": "Test", "confidence_score": -0.5}
        result = ResponseNormalizer.normalize_proposal(data)
        assert result["confidence_score"] == 0.0

    def test_normalize_proposal_alternative_keys(self):
        """替代键名"""
        data = {
            "title": "Test",
            "problem": "Problem",
            "significance": "Significance",
            "literature": "Literature",
            "innovation": "Innovation",
            "content": ["content"],
            "confidence": 0.7,
            "source": "src",
        }
        result = ResponseNormalizer.normalize_proposal(data)
        assert result["problem_awareness"] == "Problem"
        assert result["confidence_score"] == 0.7

    def test_normalize_candidates_valid(self):
        """标准化候选列表"""
        data = {
            "candidates": [
                {"title": "Topic 1", "direction": "AI", "suggestion": "Good topic"},
                {"title": "Topic 2", "direction": "ML", "description": "Another topic"},
            ]
        }
        result = ResponseNormalizer.normalize_candidates(data)
        assert len(result) == 2
        assert result[0]["title"] == "Topic 1"
        assert result[1]["suggestion"] == "Another topic"

    def test_normalize_candidates_topics_key(self):
        """topics 键"""
        data = {"topics": [{"title": "Topic"}]}
        result = ResponseNormalizer.normalize_candidates(data)
        assert len(result) == 1

    def test_normalize_candidates_empty(self):
        """空候选列表"""
        result = ResponseNormalizer.normalize_candidates({})
        assert result == []

    def test_normalize_candidates_non_list(self):
        """非列表候选"""
        data = {"candidates": "not a list"}
        result = ResponseNormalizer.normalize_candidates(data)
        assert result == []

    def test_normalize_candidates_non_dict_item(self):
        """非字典项"""
        data = {"candidates": ["not a dict", {"title": "valid"}]}
        result = ResponseNormalizer.normalize_candidates(data)
        assert len(result) == 1

    def test_normalize_evaluation_complete(self):
        """标准化完整评估"""
        data = {
            "score": 8.5,
            "novelty": 7.0,
            "feasibility": 9.0,
            "significance": 8.0,
            "strengths": ["good", "innovative"],
            "weaknesses": ["limited data"],
            "suggestions": ["add more experiments"],
            "overall_comment": "Good work",
        }
        result = ResponseNormalizer.normalize_evaluation(data)
        assert result["score"] == 8.5
        assert result["novelty"] == 7.0
        assert len(result["strengths"]) == 2
        assert result["overall_comment"] == "Good work"

    def test_normalize_evaluation_minimal(self):
        """标准化最小评估"""
        result = ResponseNormalizer.normalize_evaluation({})
        assert result["score"] == 0.0
        assert result["strengths"] == []
        assert result["overall_comment"] == ""

    def test_normalize_evaluation_non_list_fields(self):
        """非列表字段"""
        data = {"strengths": "not a list", "weaknesses": "also not"}
        result = ResponseNormalizer.normalize_evaluation(data)
        assert result["strengths"] == []
        assert result["weaknesses"] == []

    def test_normalize_search_results_complete(self):
        """标准化完整检索结果"""
        data = {
            "papers": [
                {
                    "title": "Paper 1",
                    "authors": ["Author A", "Author B"],
                    "year": 2023,
                    "abstract": "Abstract",
                    "url": "https://example.com",
                    "doi": "10.1234/test",
                    "source": "arxiv",
                    "citations": 42,
                }
            ],
            "query": "machine learning",
            "degraded": False,
        }
        result = ResponseNormalizer.normalize_search_results(data)
        assert len(result["papers"]) == 1
        assert result["papers"][0]["title"] == "Paper 1"
        assert result["total"] == 1
        assert result["query"] == "machine learning"

    def test_normalize_search_results_results_key(self):
        """results 键"""
        data = {"results": [{"title": "Paper"}]}
        result = ResponseNormalizer.normalize_search_results(data)
        assert len(result["papers"]) == 1

    def test_normalize_search_results_empty(self):
        """空结果"""
        result = ResponseNormalizer.normalize_search_results({})
        assert result["papers"] == []
        assert result["total"] == 0

    def test_normalize_search_results_non_dict_paper(self):
        """非字典论文"""
        data = {"papers": ["not a dict", {"title": "valid"}]}
        result = ResponseNormalizer.normalize_search_results(data)
        assert len(result["papers"]) == 1


# ===== ResponseParser 测试 =====


class TestResponseParser:
    """ResponseParser 解析器主类测试"""

    def test_parse_json(self):
        """解析 JSON"""
        parser = ResponseParser()
        text = '{"key": "value"}'
        result = parser.parse(text)
        assert result.type == "json"
        assert result.json_data == {"key": "value"}
        assert result.is_valid is True

    def test_parse_json_code_block(self):
        """解析代码块 JSON"""
        parser = ResponseParser()
        text = '```json\n{"key": "value"}\n```'
        result = parser.parse(text)
        assert result.type == "json"
        assert result.json_data == {"key": "value"}

    def test_parse_markdown(self):
        """解析 Markdown"""
        parser = ResponseParser()
        text = "# Title\n\nSome **bold** text"
        result = parser.parse(text)
        assert result.type == "markdown"
        assert "Title" in result.text

    def test_parse_text(self):
        """解析纯文本"""
        parser = ResponseParser()
        text = "Just plain text"
        result = parser.parse(text)
        assert result.type == "text"
        assert result.text == "Just plain text"

    def test_parse_empty(self):
        """解析空文本"""
        parser = ResponseParser()
        result = parser.parse("")
        assert result.type == "empty"
        assert result.is_valid is False

    def test_parse_whitespace_only(self):
        """解析仅空白"""
        parser = ResponseParser()
        result = parser.parse("   \n  ")
        assert result.type == "empty"
        assert result.is_valid is False

    def test_parse_mixed(self):
        """解析混合格式"""
        parser = ResponseParser()
        text = '# Title\n\n```json\n{"key": "value"}\n```\n\nMore text'
        result = parser.parse(text)
        assert result.type in ("mixed", "markdown")
        assert result.json_data is not None or result.markdown

    def test_parse_with_citations(self):
        """解析带引用"""
        parser = ResponseParser()
        text = 'Some text [1] and (Smith, 2020)'
        result = parser.parse(text)
        assert len(result.citations) >= 2

    def test_parse_with_code_blocks(self):
        """解析带代码块"""
        parser = ResponseParser()
        text = '```python\nprint("hello")\n```'
        result = parser.parse(text)
        assert len(result.code_blocks) >= 1

    def test_parse_expected_type_json(self):
        """指定 JSON 类型"""
        parser = ResponseParser()
        text = '{"key": "value"}'
        result = parser.parse(text, expected_type="json")
        assert result.type == "json"

    def test_parse_expected_type_markdown(self):
        """指定 Markdown 类型"""
        parser = ResponseParser()
        text = "# Title"
        result = parser.parse(text, expected_type="markdown")
        assert result.type == "markdown"

    def test_parse_json_method(self):
        """parse_json 方法"""
        parser = ResponseParser()
        result = parser.parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_method_failed(self):
        """parse_json 失败"""
        parser = ResponseParser()
        assert parser.parse_json("not json") is None

    def test_parse_json_list_method(self):
        """parse_json_list 方法"""
        parser = ResponseParser()
        result = parser.parse_json_list('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_parse_markdown_method(self):
        """parse_markdown 方法"""
        parser = ResponseParser()
        result = parser.parse_markdown("# Title\n- item")
        assert "headings" in result
        assert len(result["headings"]) == 1

    def test_parse_proposal_method(self):
        """parse_proposal 方法"""
        parser = ResponseParser()
        text = '{"title": "Test", "confidence_score": 0.8}'
        result = parser.parse_proposal(text)
        assert result["title"] == "Test"
        assert result["confidence_score"] == 0.8

    def test_parse_proposal_failed(self):
        """parse_proposal 失败"""
        parser = ResponseParser()
        assert parser.parse_proposal("not json") == {}

    def test_parse_candidates_method(self):
        """parse_candidates 方法"""
        parser = ResponseParser()
        text = '{"candidates": [{"title": "Topic 1"}]}'
        result = parser.parse_candidates(text)
        assert len(result) == 1
        assert result[0]["title"] == "Topic 1"

    def test_parse_evaluation_method(self):
        """parse_evaluation 方法"""
        parser = ResponseParser()
        text = '{"score": 8.5, "novelty": 7.0}'
        result = parser.parse_evaluation(text)
        assert result["score"] == 8.5

    def test_parse_search_results_method(self):
        """parse_search_results 方法"""
        parser = ResponseParser()
        text = '{"papers": [{"title": "Paper"}], "query": "test"}'
        result = parser.parse_search_results(text)
        assert len(result["papers"]) == 1
        assert result["query"] == "test"

    def test_extract_citations_method(self):
        """extract_citations 方法"""
        parser = ResponseParser()
        result = parser.extract_citations("Cited [1] and [2]")
        assert len(result) == 2

    def test_validate_response_method(self):
        """validate_response 方法"""
        parser = ResponseParser()
        text = '{"key": "value"}'
        result = parser.validate_response(text, ["key"])
        assert result["valid"] is True

    def test_validate_response_failed(self):
        """validate_response 失败"""
        parser = ResponseParser()
        result = parser.validate_response("not json", ["key"])
        assert result["valid"] is False

    def test_detect_type_json(self):
        """检测 JSON 类型"""
        parser = ResponseParser()
        assert parser._detect_type('{"key": "value"}') == "json"

    def test_detect_type_markdown(self):
        """检测 Markdown 类型"""
        parser = ResponseParser()
        assert parser._detect_type("# Title") == "markdown"

    def test_detect_type_text(self):
        """检测文本类型"""
        parser = ResponseParser()
        assert parser._detect_type("plain text") == "text"


# ===== 模块级函数测试 =====


class TestModuleFunctions:
    """模块级便捷函数测试"""

    def test_get_parser(self):
        """获取解析器"""
        parser = get_parser()
        assert isinstance(parser, ResponseParser)

    def test_get_parser_singleton(self):
        """解析器单例"""
        assert get_parser() is get_parser()

    def test_parse_response(self):
        """parse_response 函数"""
        result = parse_response('{"key": "value"}')
        assert isinstance(result, ParsedResponse)
        assert result.type == "json"

    def test_parse_response_with_type(self):
        """带类型 parse_response"""
        result = parse_response("# Title", expected_type="markdown")
        assert result.type == "markdown"

    def test_extract_json_function(self):
        """extract_json 函数"""
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extract_citations_function(self):
        """extract_citations 函数"""
        result = extract_citations("Cited [1]")
        assert len(result) == 1

    def test_parse_markdown_function(self):
        """parse_markdown 函数"""
        result = parse_markdown("# Title")
        assert "headings" in result

    def test_validate_json_response_function(self):
        """validate_json_response 函数"""
        result = validate_json_response({"key": "value"}, ["key"])
        assert result["valid"] is True

    def test_normalize_proposal_function(self):
        """normalize_proposal 函数"""
        result = normalize_proposal({"title": "Test"})
        assert result["title"] == "Test"

    def test_response_types(self):
        """RESPONSE_TYPES 常量"""
        assert "json" in RESPONSE_TYPES
        assert "markdown" in RESPONSE_TYPES
        assert "text" in RESPONSE_TYPES
        assert "mixed" in RESPONSE_TYPES
        assert "error" in RESPONSE_TYPES
        assert "empty" in RESPONSE_TYPES


# ===== 集成测试 =====


class TestIntegration:
    """集成测试"""

    def test_full_json_workflow(self):
        """完整 JSON 工作流"""
        parser = ResponseParser()
        # 模拟 AI 返回的 JSON 响应
        text = '```json\n{"title": "深度学习研究", "confidence_score": 0.85}\n```'
        # 解析
        result = parser.parse(text)
        assert result.type == "json"
        assert result.json_data is not None
        # 标准化
        normalized = parser.normalizer.normalize_proposal(result.json_data)
        assert normalized["title"] == "深度学习研究"
        assert normalized["confidence_score"] == 0.85

    def test_markdown_with_citations(self):
        """带引用的 Markdown"""
        parser = ResponseParser()
        text = """# 研究背景

根据 Smith (2020) 的研究 [1]，深度学习在多个领域取得突破。

## 相关工作

参见 arXiv: 2023.12345 了解更多细节。
"""
        result = parser.parse(text)
        assert result.type == "markdown"
        assert len(result.citations) >= 2

    def test_mixed_response_parsing(self):
        """混合响应解析"""
        parser = ResponseParser()
        text = """# 分析结果

根据分析，结果如下：

```json
{
    "score": 8.5,
    "strengths": ["创新性强", "方法合理"],
    "weaknesses": ["数据量不足"]
}
```

详细说明见 [1]。
"""
        result = parser.parse(text)
        assert result.json_data is not None or result.markdown
        assert len(result.citations) >= 1

    def test_error_recovery(self):
        """错误恢复"""
        parser = ResponseParser()
        # 带尾部逗号的 JSON
        text = '{"title": "Test", "score": 8.5,}'
        result = parser.parse(text)
        assert result.json_data is not None
        assert result.json_data["title"] == "Test"

    def test_validation_workflow(self):
        """验证工作流"""
        parser = ResponseParser()
        text = '{"title": "Test", "score": 8.5}'
        # 验证必填字段
        validation = parser.validate_response(text, ["title", "score"])
        assert validation["valid"] is True
        # 验证缺失字段
        validation = parser.validate_response(text, ["title", "missing_field"])
        assert validation["valid"] is False


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试"""

    def test_extract_json_none(self):
        """None 输入"""
        assert JSONExtractor.extract(None) is None

    def test_extract_json_empty_dict(self):
        """空字典"""
        assert JSONExtractor.extract("{}") == {}

    def test_markdown_parser_none(self):
        """None 输入"""
        assert MarkdownParser.extract_headings(None) == []
        assert MarkdownParser.extract_code_blocks(None) == []

    def test_citation_extractor_none(self):
        """None 输入"""
        assert CitationExtractor.extract_all(None) == []
        assert CitationExtractor.extract_numeric(None) == []

    def test_parse_none(self):
        """None 输入解析"""
        parser = ResponseParser()
        result = parser.parse(None)
        assert result.type == "empty"
        assert result.is_valid is False

    def test_validate_empty_dict(self):
        """空字典验证"""
        result = ResponseValidator.validate_json_response({}, ["key"])
        assert result["valid"] is False

    def test_normalize_empty_proposal(self):
        """空提案标准化"""
        result = ResponseNormalizer.normalize_proposal({})
        assert result["title"] == ""
        assert result["confidence_score"] == 0.5

    def test_json_with_unicode(self):
        """Unicode JSON"""
        text = '{"title": "中文标题", "content": "日本語"}'
        result = JSONExtractor.extract(text)
        assert result["title"] == "中文标题"
        assert result["content"] == "日本語"

    def test_deeply_nested_json(self):
        """深度嵌套 JSON"""
        data = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        text = json.dumps(data)
        result = JSONExtractor.extract(text)
        assert result == data

    def test_large_json(self):
        """大型 JSON"""
        data = {f"key_{i}": f"value_{i}" for i in range(100)}
        text = json.dumps(data)
        result = JSONExtractor.extract(text)
        assert len(result) == 100

    def test_markdown_with_special_chars(self):
        """特殊字符 Markdown"""
        text = "# Title with 特殊字符 !@#$%"
        headings = MarkdownParser.extract_headings(text)
        assert len(headings) == 1
        assert "特殊字符" in headings[0]["text"]
