# -*- coding: utf-8 -*-
"""
test_plagiarism_checker.py - 抄袭检测模块单元测试

本测试文件覆盖 backend/constraints/plagiarism_checker.py 中的所有组件：
- SimilarityResult / PlagiarismMatch / OriginalityReport 数据类
- preprocess_text / tokenize 文本预处理函数
- TextSimilarity 相似度计算器（cosine/jaccard/levenshtein/lcs/ngram/combined/calculate）
- _generate_ngrams n-gram 生成函数
- NGramAnalyzer n-gram 分析器（analyze/find_repeated_ngrams/compare_texts/detect_suspicious_patterns）
- CitationVerifier 引用验证器（extract_citations/verify_citation_coverage）
- OriginalityScorer 原创性评分器（score/_find_similar_segments/_generate_recommendations）
- PlagiarismChecker 抄袭检测器（check/quick_check/batch_check/find_similar_sources/get_text_fingerprint/compare_fingerprints）
- 便捷函数（check_plagiarism/calculate_similarity/analyze_ngrams/get_text_fingerprint）

作者：ThesisMiner 团队
版本：v8.0
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.constraints.plagiarism_checker import (
    # 数据类
    SimilarityResult,
    PlagiarismMatch,
    OriginalityReport,
    # 预处理函数
    preprocess_text,
    tokenize,
    # 相似度计算
    TextSimilarity,
    _generate_ngrams,
    # n-gram 分析
    NGramAnalyzer,
    # 引用验证
    CitationVerifier,
    # 原创性评分
    OriginalityScorer,
    # 抄袭检测器
    PlagiarismChecker,
    # 便捷函数
    check_plagiarism,
    calculate_similarity,
    analyze_ngrams,
    get_text_fingerprint as get_fp_func,
)


# ===== SimilarityResult 测试 =====


class TestSimilarityResult:
    """测试 SimilarityResult 数据类。"""

    def test_create(self):
        """测试创建相似度结果。"""
        result = SimilarityResult(score=0.5)
        assert result.score == 0.5
        assert result.algorithm == ""
        assert result.details == {}

    def test_create_with_all_fields(self):
        """测试带所有字段创建。"""
        result = SimilarityResult(
            score=0.8,
            algorithm="cosine",
            details={"tokens": 10},
        )
        assert result.score == 0.8
        assert result.algorithm == "cosine"
        assert result.details == {"tokens": 10}

    def test_to_dict(self):
        """测试转换为字典。"""
        result = SimilarityResult(score=0.5, algorithm="jaccard", details={"a": 1})
        d = result.to_dict()
        assert d["score"] == 0.5
        assert d["algorithm"] == "jaccard"
        assert d["details"] == {"a": 1}

    def test_zero_score(self):
        """测试零分。"""
        result = SimilarityResult(score=0.0)
        assert result.score == 0.0

    def test_full_score(self):
        """测试满分。"""
        result = SimilarityResult(score=1.0)
        assert result.score == 1.0


# ===== PlagiarismMatch 测试 =====


class TestPlagiarismMatch:
    """测试 PlagiarismMatch 数据类。"""

    def test_create(self):
        """测试创建匹配片段。"""
        match = PlagiarismMatch(
            source_text="源文本",
            target_text="目标文本",
            similarity=0.8,
        )
        assert match.source_text == "源文本"
        assert match.target_text == "目标文本"
        assert match.similarity == 0.8

    def test_default_values(self):
        """测试默认值。"""
        match = PlagiarismMatch(source_text="a", target_text="b", similarity=0.5)
        assert match.source_start == 0
        assert match.source_end == 0
        assert match.target_start == 0
        assert match.target_end == 0
        assert match.source_reference == ""

    def test_to_dict(self):
        """测试转换为字典。"""
        match = PlagiarismMatch(
            source_text="源",
            target_text="目标",
            similarity=0.9,
            source_start=0,
            source_end=10,
            source_reference="ref_1",
        )
        d = match.to_dict()
        assert d["source_text"] == "源"
        assert d["target_text"] == "目标"
        assert d["similarity"] == 0.9
        assert d["source_reference"] == "ref_1"

    def test_with_reference(self):
        """测试带来源引用的匹配。"""
        match = PlagiarismMatch(
            source_text="文本",
            target_text="文本",
            similarity=1.0,
            source_reference="论文A",
        )
        assert match.source_reference == "论文A"


# ===== OriginalityReport 测试 =====


class TestOriginalityReport:
    """测试 OriginalityReport 数据类。"""

    def test_create(self):
        """测试创建原创性报告。"""
        report = OriginalityReport(overall_score=0.9, similarity_score=0.1)
        assert report.overall_score == 0.9
        assert report.similarity_score == 0.1
        assert report.matches == []
        assert report.is_plagiarized is False

    def test_default_values(self):
        """测试默认值。"""
        report = OriginalityReport(overall_score=1.0, similarity_score=0.0)
        assert report.citation_coverage == 0.0
        assert report.ngram_analysis == {}
        assert report.recommendations == []
        assert report.severity == "none"

    def test_to_dict(self):
        """测试转换为字典。"""
        report = OriginalityReport(
            overall_score=0.5,
            similarity_score=0.5,
            is_plagiarized=True,
            severity="high",
        )
        d = report.to_dict()
        assert d["overall_score"] == 0.5
        assert d["similarity_score"] == 0.5
        assert d["is_plagiarized"] is True
        assert d["severity"] == "high"

    def test_to_dict_with_matches(self):
        """测试带匹配片段的字典转换。"""
        match = PlagiarismMatch(source_text="a", target_text="b", similarity=0.8)
        report = OriginalityReport(
            overall_score=0.2,
            similarity_score=0.8,
            matches=[match],
        )
        d = report.to_dict()
        assert len(d["matches"]) == 1
        assert d["matches"][0]["source_text"] == "a"

    def test_severity_levels(self):
        """测试严重级别。"""
        for severity in ["none", "low", "medium", "high", "critical"]:
            report = OriginalityReport(
                overall_score=0.5,
                similarity_score=0.5,
                severity=severity,
            )
            assert report.severity == severity


# ===== preprocess_text 测试 =====


class TestPreprocessText:
    """测试 preprocess_text 函数。"""

    def test_empty_text(self):
        """测试空文本。"""
        assert preprocess_text("") == ""

    def test_none_text(self):
        """测试 None 文本。"""
        assert preprocess_text(None) == ""

    def test_lowercase(self):
        """测试小写转换。"""
        result = preprocess_text("Hello World", lowercase=True)
        assert result == "hello world"

    def test_no_lowercase(self):
        """测试不转小写。"""
        result = preprocess_text("Hello World", lowercase=False)
        assert "H" in result

    def test_remove_punctuation(self):
        """测试移除标点。"""
        result = preprocess_text("Hello, World!", remove_punctuation=True)
        assert "," not in result
        assert "!" not in result

    def test_keep_chinese(self):
        """测试保留中文。"""
        result = preprocess_text("深度学习模型")
        assert "深" in result

    def test_whitespace_normalization(self):
        """测试空白规范化。"""
        result = preprocess_text("hello   world")
        assert "  " not in result

    def test_strip(self):
        """测试去除首尾空白。"""
        result = preprocess_text("  hello  ")
        assert result == "hello"


# ===== tokenize 测试 =====


class TestTokenize:
    """测试 tokenize 函数。"""

    def test_empty_text(self):
        """测试空文本分词。"""
        assert tokenize("") == []

    def test_english_tokenize(self):
        """测试英文分词。"""
        tokens = tokenize("hello world", language="english")
        assert "hello" in tokens
        assert "world" in tokens

    def test_chinese_tokenize(self):
        """测试中文分词。"""
        tokens = tokenize("深度学习", language="chinese")
        assert "深" in tokens
        assert "度" in tokens
        assert "学" in tokens
        assert "习" in tokens

    def test_auto_tokenize_mixed(self):
        """测试自动分词（中英混合）。"""
        tokens = tokenize("深度学习 deep learning", language="auto")
        assert "深" in tokens
        assert "deep" in tokens

    def test_auto_tokenize_english(self):
        """测试自动分词（纯英文）。"""
        tokens = tokenize("hello world test", language="auto")
        assert "hello" in tokens

    def test_auto_tokenize_chinese(self):
        """测试自动分词（纯中文）。"""
        tokens = tokenize("深度学习模型", language="auto")
        assert "深" in tokens

    def test_tokenize_with_punctuation(self):
        """测试带标点的分词。"""
        tokens = tokenize("hello, world!", language="english")
        assert len(tokens) >= 2


# ===== TextSimilarity 测试 =====


class TestTextSimilarity:
    """测试 TextSimilarity 类。"""

    def test_cosine_identical(self):
        """测试余弦相似度-相同文本。"""
        result = TextSimilarity.cosine_similarity("hello world", "hello world")
        assert result.score == pytest.approx(1.0, abs=0.01)
        assert result.algorithm == "cosine"

    def test_cosine_different(self):
        """测试余弦相似度-不同文本。"""
        result = TextSimilarity.cosine_similarity("hello world", "foo bar")
        assert result.score < 1.0

    def test_cosine_empty(self):
        """测试余弦相似度-空文本。"""
        result = TextSimilarity.cosine_similarity("", "hello")
        assert result.score == 0.0

    def test_cosine_both_empty(self):
        """测试余弦相似度-双空文本。"""
        result = TextSimilarity.cosine_similarity("", "")
        assert result.score == 0.0

    def test_cosine_partial_overlap(self):
        """测试余弦相似度-部分重叠。"""
        result = TextSimilarity.cosine_similarity("hello world foo", "hello world bar")
        assert 0.0 < result.score < 1.0

    def test_cosine_chinese(self):
        """测试余弦相似度-中文。"""
        result = TextSimilarity.cosine_similarity("深度学习模型", "深度学习算法")
        assert result.score > 0.0

    def test_cosine_details(self):
        """测试余弦相似度详情。"""
        result = TextSimilarity.cosine_similarity("a b c", "a b d")
        assert "tokens1_count" in result.details
        assert "tokens2_count" in result.details

    def test_jaccard_identical(self):
        """测试 Jaccard 相似度-相同文本。"""
        result = TextSimilarity.jaccard_similarity("hello world", "hello world")
        assert result.score == pytest.approx(1.0, abs=0.01)
        assert result.algorithm == "jaccard"

    def test_jaccard_different(self):
        """测试 Jaccard 相似度-不同文本。"""
        result = TextSimilarity.jaccard_similarity("hello world", "foo bar")
        assert result.score < 1.0

    def test_jaccard_empty(self):
        """测试 Jaccard 相似度-空文本。"""
        result = TextSimilarity.jaccard_similarity("", "hello")
        assert result.score == 0.0

    def test_jaccard_partial(self):
        """测试 Jaccard 相似度-部分重叠。"""
        result = TextSimilarity.jaccard_similarity("a b c", "a b d")
        assert 0.0 < result.score < 1.0

    def test_jaccard_details(self):
        """测试 Jaccard 详情。"""
        result = TextSimilarity.jaccard_similarity("a b", "a b")
        assert "intersection_size" in result.details
        assert "union_size" in result.details

    def test_levenshtein_identical(self):
        """测试编辑距离-相同文本。"""
        result = TextSimilarity.levenshtein_distance("hello", "hello")
        assert result.score == pytest.approx(1.0)
        assert result.algorithm == "levenshtein"

    def test_levenshtein_different(self):
        """测试编辑距离-不同文本。"""
        result = TextSimilarity.levenshtein_distance("hello", "world")
        assert result.score < 1.0

    def test_levenshtein_empty(self):
        """测试编辑距离-空文本。"""
        result = TextSimilarity.levenshtein_distance("", "hello")
        assert result.score == 0.0

    def test_levenshtein_both_empty(self):
        """测试编辑距离-双空文本。"""
        result = TextSimilarity.levenshtein_distance("", "")
        assert result.score == 1.0

    def test_levenshtein_one_char_diff(self):
        """测试编辑距离-一字之差。"""
        result = TextSimilarity.levenshtein_distance("hello", "hallo")
        assert result.score >= 0.8

    def test_levenshtein_details(self):
        """测试编辑距离详情。"""
        result = TextSimilarity.levenshtein_distance("abc", "abd")
        assert "distance" in result.details
        assert "max_length" in result.details

    def test_lcs_identical(self):
        """测试 LCS-相同文本。"""
        result = TextSimilarity.lcs_similarity("hello", "hello")
        assert result.score == pytest.approx(1.0)
        assert result.algorithm == "lcs"

    def test_lcs_different(self):
        """测试 LCS-不同文本。"""
        result = TextSimilarity.lcs_similarity("abc", "xyz")
        assert result.score < 1.0

    def test_lcs_empty(self):
        """测试 LCS-空文本。"""
        result = TextSimilarity.lcs_similarity("", "hello")
        assert result.score == 0.0

    def test_lcs_partial(self):
        """测试 LCS-部分匹配。"""
        result = TextSimilarity.lcs_similarity("abcdef", "abcxyz")
        assert 0.0 < result.score < 1.0

    def test_lcs_details(self):
        """测试 LCS 详情。"""
        result = TextSimilarity.lcs_similarity("abc", "abc")
        assert "lcs_length" in result.details

    def test_ngram_identical(self):
        """测试 n-gram 相似度-相同文本。"""
        result = TextSimilarity.ngram_similarity("hello world", "hello world", n=3)
        assert result.score == pytest.approx(1.0)

    def test_ngram_different(self):
        """测试 n-gram 相似度-不同文本。"""
        result = TextSimilarity.ngram_similarity("hello world", "foo bar", n=3)
        assert result.score < 1.0

    def test_ngram_empty(self):
        """测试 n-gram 相似度-空文本。"""
        result = TextSimilarity.ngram_similarity("", "hello", n=3)
        assert result.score == 0.0

    def test_ngram_different_n(self):
        """测试不同 n 值。"""
        result2 = TextSimilarity.ngram_similarity("hello", "hello", n=2)
        result3 = TextSimilarity.ngram_similarity("hello", "hello", n=3)
        assert result2.score == pytest.approx(1.0)
        assert result3.score == pytest.approx(1.0)

    def test_ngram_details(self):
        """测试 n-gram 详情。"""
        result = TextSimilarity.ngram_similarity("hello", "hello", n=3)
        assert "n" in result.details
        assert result.details["n"] == 3

    def test_combined_identical(self):
        """测试组合相似度-相同文本。"""
        result = TextSimilarity.combined_similarity("hello world", "hello world")
        assert result.score == pytest.approx(1.0, abs=0.05)
        assert result.algorithm == "combined"

    def test_combined_different(self):
        """测试组合相似度-不同文本。"""
        result = TextSimilarity.combined_similarity("hello world", "foo bar")
        assert result.score < 1.0

    def test_combined_details(self):
        """测试组合相似度详情。"""
        result = TextSimilarity.combined_similarity("a b", "a b")
        assert "cosine" in result.details
        assert "jaccard" in result.details
        assert "ngram" in result.details

    def test_calculate_cosine(self):
        """测试 calculate 方法-cosine。"""
        result = TextSimilarity.calculate("hello", "hello", algorithm="cosine")
        assert result.algorithm == "cosine"

    def test_calculate_jaccard(self):
        """测试 calculate 方法-jaccard。"""
        result = TextSimilarity.calculate("hello", "hello", algorithm="jaccard")
        assert result.algorithm == "jaccard"

    def test_calculate_levenshtein(self):
        """测试 calculate 方法-levenshtein。"""
        result = TextSimilarity.calculate("hello", "hello", algorithm="levenshtein")
        assert result.algorithm == "levenshtein"

    def test_calculate_lcs(self):
        """测试 calculate 方法-lcs。"""
        result = TextSimilarity.calculate("hello", "hello", algorithm="lcs")
        assert result.algorithm == "lcs"

    def test_calculate_ngram(self):
        """测试 calculate 方法-ngram。"""
        result = TextSimilarity.calculate("hello", "hello", algorithm="ngram")
        assert "ngram" in result.algorithm

    def test_calculate_combined(self):
        """测试 calculate 方法-combined。"""
        result = TextSimilarity.calculate("hello", "hello", algorithm="combined")
        assert result.algorithm == "combined"

    def test_calculate_unknown_algorithm(self):
        """测试 calculate 方法-未知算法（默认 combined）。"""
        result = TextSimilarity.calculate("hello", "hello", algorithm="unknown")
        assert result.algorithm == "combined"


# ===== _generate_ngrams 测试 =====


class TestGenerateNgrams:
    """测试 _generate_ngrams 函数。"""

    def test_generate_ngrams(self):
        """测试生成 n-gram。"""
        ngrams = _generate_ngrams("hello", n=3)
        assert len(ngrams) == 3  # "hel", "ell", "llo"
        assert "hel" in ngrams
        assert "llo" in ngrams

    def test_empty_text(self):
        """测试空文本。"""
        ngrams = _generate_ngrams("", n=3)
        assert ngrams == []

    def test_text_shorter_than_n(self):
        """测试文本短于 n。"""
        ngrams = _generate_ngrams("ab", n=3)
        assert len(ngrams) == 1
        assert ngrams[0] == "ab"

    def test_different_n_values(self):
        """测试不同 n 值。"""
        text = "hello"
        ngrams2 = _generate_ngrams(text, n=2)
        ngrams3 = _generate_ngrams(text, n=3)
        assert len(ngrams2) > len(ngrams3)

    def test_chinese_text(self):
        """测试中文文本。"""
        ngrams = _generate_ngrams("深度学习", n=2)
        assert len(ngrams) > 0


# ===== NGramAnalyzer 测试 =====


class TestNGramAnalyzer:
    """测试 NGramAnalyzer 类。"""

    def test_create_analyzer(self):
        """测试创建分析器。"""
        analyzer = NGramAnalyzer(n=3)
        assert analyzer.n == 3

    def test_analyze(self):
        """测试分析文本。"""
        analyzer = NGramAnalyzer(n=3)
        result = analyzer.analyze("hello world hello")
        assert "total_ngrams" in result
        assert "unique_ngrams" in result
        assert "repetition_rate" in result
        assert "top_ngrams" in result
        assert result["total_ngrams"] > 0

    def test_analyze_empty(self):
        """测试分析空文本。"""
        analyzer = NGramAnalyzer(n=3)
        result = analyzer.analyze("")
        assert result["total_ngrams"] == 0
        assert result["unique_ngrams"] == 0

    def test_analyze_repetition(self):
        """测试重复率计算。"""
        analyzer = NGramAnalyzer(n=3)
        # 高重复文本
        result = analyzer.analyze("abc abc abc abc")
        assert result["repetition_rate"] > 0

    def test_analyze_no_repetition(self):
        """测试无重复文本。"""
        analyzer = NGramAnalyzer(n=3)
        result = analyzer.analyze("abcdefg")
        assert result["repetition_rate"] == 0.0

    def test_find_repeated_ngrams(self):
        """测试查找重复 n-gram。"""
        analyzer = NGramAnalyzer(n=3)
        repeated = analyzer.find_repeated_ngrams("abc abc abc", min_count=2)
        assert len(repeated) > 0

    def test_find_repeated_ngrams_none(self):
        """测试无重复 n-gram。"""
        analyzer = NGramAnalyzer(n=3)
        repeated = analyzer.find_repeated_ngrams("abcdefg", min_count=2)
        assert len(repeated) == 0

    def test_compare_texts(self):
        """测试比较文本。"""
        analyzer = NGramAnalyzer(n=3)
        result = analyzer.compare_texts("hello world", "hello there")
        assert "ngrams1_count" in result
        assert "ngrams2_count" in result
        assert "common_count" in result
        assert "overlap_rate" in result

    def test_compare_identical_texts(self):
        """测试比较相同文本。"""
        analyzer = NGramAnalyzer(n=3)
        result = analyzer.compare_texts("hello world", "hello world")
        assert result["overlap_rate"] == pytest.approx(1.0)

    def test_compare_different_texts(self):
        """测试比较不同文本。"""
        analyzer = NGramAnalyzer(n=3)
        result = analyzer.compare_texts("hello world", "foo bar baz")
        assert result["overlap_rate"] < 1.0

    def test_detect_suspicious_patterns(self):
        """测试检测可疑模式。"""
        analyzer = NGramAnalyzer(n=3)
        # 高重复文本应有可疑模式
        patterns = analyzer.detect_suspicious_patterns("abc abc abc abc abc")
        assert isinstance(patterns, list)

    def test_detect_suspicious_patterns_none(self):
        """测试无可疑模式。"""
        analyzer = NGramAnalyzer(n=3)
        patterns = analyzer.detect_suspicious_patterns("abcdefghijklmnopqrstuvwxyz")
        assert isinstance(patterns, list)

    def test_different_n_values(self):
        """测试不同 n 值的分析器。"""
        analyzer3 = NGramAnalyzer(n=3)
        analyzer5 = NGramAnalyzer(n=5)
        text = "hello world hello world"
        result3 = analyzer3.analyze(text)
        result5 = analyzer5.analyze(text)
        assert result3["total_ngrams"] != result5["total_ngrams"]


# ===== CitationVerifier 测试 =====


class TestCitationVerifier:
    """测试 CitationVerifier 类。"""

    def test_create_verifier(self):
        """测试创建验证器。"""
        verifier = CitationVerifier()
        assert verifier is not None

    def test_extract_numeric_citations(self):
        """测试提取数字引用。"""
        verifier = CitationVerifier()
        citations = verifier.extract_citations("研究显示[1]该方法有效[2]")
        assert len(citations) >= 2

    def test_extract_year_citations(self):
        """测试提取年份引用。"""
        verifier = CitationVerifier()
        citations = verifier.extract_citations("研究(2020)表明")
        assert len(citations) >= 1

    def test_extract_no_citations(self):
        """测试无引用文本。"""
        verifier = CitationVerifier()
        citations = verifier.extract_citations("这是一段没有引用的文本")
        assert len(citations) == 0

    def test_verify_citation_coverage(self):
        """测试验证引用覆盖率。"""
        verifier = CitationVerifier()
        text = "这是原创文本内容[1]"
        references = ["完全不同的参考文献内容"]
        result = verifier.verify_citation_coverage(text, references)
        assert "coverage" in result
        assert "uncovered_segments" in result
        assert "total_similar" in result

    def test_verify_citation_coverage_no_references(self):
        """测试无参考文献的覆盖率。"""
        verifier = CitationVerifier()
        result = verifier.verify_citation_coverage("文本", [])
        assert result["coverage"] >= 0.0


# ===== OriginalityScorer 测试 =====


class TestOriginalityScorer:
    """测试 OriginalityScorer 类。"""

    def test_create_scorer(self):
        """测试创建评分器。"""
        scorer = OriginalityScorer()
        assert scorer is not None

    def test_score_original_text(self):
        """测试原创文本评分。"""
        scorer = OriginalityScorer()
        report = scorer.score("这是一段完全原创的文本内容，没有抄袭任何参考文献")
        assert report.overall_score > 0.5
        assert report.is_plagiarized is False
        assert report.severity == "none"

    def test_score_plagiarized_text(self):
        """测试抄袭文本评分。"""
        scorer = OriginalityScorer()
        original = "深度学习是机器学习的一个分支，使用多层神经网络"
        report = scorer.score(original, reference_texts=[original])
        assert report.similarity_score > 0.5
        assert report.is_plagiarized is True

    def test_score_no_references(self):
        """测试无参考文献评分。"""
        scorer = OriginalityScorer()
        report = scorer.score("原创文本")
        assert report.citation_coverage == 1.0

    def test_score_with_recommendations(self):
        """测试带建议的评分。"""
        scorer = OriginalityScorer()
        report = scorer.score("原创文本")
        assert len(report.recommendations) > 0

    def test_score_severity_levels(self):
        """测试严重级别。"""
        scorer = OriginalityScorer()
        # 高相似度
        text = "深度学习模型研究"
        report = scorer.score(text, reference_texts=[text])
        assert report.severity in ["critical", "high", "medium", "low", "none"]

    def test_score_matches(self):
        """测试匹配片段。"""
        scorer = OriginalityScorer()
        text = "深度学习是机器学习的一个分支" * 5
        ref = "深度学习是机器学习的一个分支" * 5
        report = scorer.score(text, reference_texts=[ref])
        assert isinstance(report.matches, list)


# ===== PlagiarismChecker 测试 =====


class TestPlagiarismChecker:
    """测试 PlagiarismChecker 类。"""

    def test_create_checker(self):
        """测试创建检测器。"""
        checker = PlagiarismChecker()
        assert checker.similarity_threshold == 0.5
        assert checker.ngram_size == 5

    def test_create_with_params(self):
        """测试带参数创建。"""
        checker = PlagiarismChecker(similarity_threshold=0.7, ngram_size=3)
        assert checker.similarity_threshold == 0.7
        assert checker.ngram_size == 3

    def test_check(self):
        """测试执行检测。"""
        checker = PlagiarismChecker()
        report = checker.check("原创文本内容")
        assert isinstance(report, OriginalityReport)
        assert report.overall_score >= 0.0

    def test_check_with_references(self):
        """测试带参考文献检测。"""
        checker = PlagiarismChecker()
        text = "深度学习模型研究"
        refs = ["深度学习模型分析"]
        report = checker.check(text, reference_texts=refs)
        assert isinstance(report, OriginalityReport)

    def test_quick_check(self):
        """测试快速检查。"""
        checker = PlagiarismChecker()
        score = checker.quick_check("hello world", "hello world")
        assert score == pytest.approx(1.0, abs=0.05)

    def test_quick_check_different(self):
        """测试快速检查-不同文本。"""
        checker = PlagiarismChecker()
        score = checker.quick_check("hello world", "foo bar")
        assert score < 1.0

    def test_quick_check_algorithm(self):
        """测试快速检查-指定算法。"""
        checker = PlagiarismChecker()
        score = checker.quick_check("hello", "hello", algorithm="cosine")
        assert score == pytest.approx(1.0, abs=0.01)

    def test_batch_check(self):
        """测试批量检查。"""
        checker = PlagiarismChecker()
        text = "深度学习研究"
        refs = ["深度学习分析", "机器学习研究", "完全不同的内容"]
        results = checker.batch_check(text, refs)
        assert len(results) == 3
        # 应按相似度降序排列
        assert results[0]["similarity"] >= results[1]["similarity"]

    def test_batch_check_empty(self):
        """测试批量检查-空列表。"""
        checker = PlagiarismChecker()
        results = checker.batch_check("文本", [])
        assert len(results) == 0

    def test_find_similar_sources(self):
        """测试查找相似来源。"""
        checker = PlagiarismChecker()
        text = "深度学习模型"
        refs = ["深度学习模型", "机器学习", "其他内容", "更多内容", "深度学习"]
        sources = checker.find_similar_sources(text, refs, top_k=3)
        assert len(sources) <= 3

    def test_find_similar_sources_top_k(self):
        """测试 top_k 参数。"""
        checker = PlagiarismChecker()
        text = "test"
        refs = ["test", "test", "test", "test", "test"]
        sources = checker.find_similar_sources(text, refs, top_k=2)
        assert len(sources) == 2

    def test_get_text_fingerprint(self):
        """测试获取文本指纹。"""
        checker = PlagiarismChecker()
        fp = checker.get_text_fingerprint("hello world")
        assert isinstance(fp, str)
        assert len(fp) > 0

    def test_fingerprint_consistency(self):
        """测试指纹一致性。"""
        checker = PlagiarismChecker()
        fp1 = checker.get_text_fingerprint("hello world")
        fp2 = checker.get_text_fingerprint("hello world")
        assert fp1 == fp2

    def test_fingerprint_different_text(self):
        """测试不同文本指纹不同。"""
        checker = PlagiarismChecker()
        fp1 = checker.get_text_fingerprint("hello world")
        fp2 = checker.get_text_fingerprint("foo bar")
        assert fp1 != fp2

    def test_compare_fingerprints_identical(self):
        """测试比较相同指纹。"""
        checker = PlagiarismChecker()
        fp = checker.get_text_fingerprint("hello")
        similarity = checker.compare_fingerprints(fp, fp)
        assert similarity == 1.0

    def test_compare_fingerprints_different(self):
        """测试比较不同指纹。"""
        checker = PlagiarismChecker()
        fp1 = checker.get_text_fingerprint("hello world")
        fp2 = checker.get_text_fingerprint("foo bar baz")
        similarity = checker.compare_fingerprints(fp1, fp2)
        assert similarity < 1.0

    def test_compare_fingerprints_empty(self):
        """测试比较空指纹。"""
        checker = PlagiarismChecker()
        similarity = checker.compare_fingerprints("", "abc")
        assert similarity == 0.0


# ===== 便捷函数测试 =====


class TestConvenienceFunctions:
    """测试便捷函数。"""

    def test_check_plagiarism(self):
        """测试 check_plagiarism 函数。"""
        report = check_plagiarism("原创文本")
        assert isinstance(report, OriginalityReport)

    def test_check_plagiarism_with_refs(self):
        """测试带参考文献的 check_plagiarism。"""
        report = check_plagiarism("深度学习", reference_texts=["深度学习"])
        assert isinstance(report, OriginalityReport)

    def test_calculate_similarity(self):
        """测试 calculate_similarity 函数。"""
        score = calculate_similarity("hello", "hello")
        assert score == pytest.approx(1.0, abs=0.05)

    def test_calculate_similarity_algorithm(self):
        """测试指定算法的 calculate_similarity。"""
        score = calculate_similarity("hello", "hello", algorithm="cosine")
        assert score == pytest.approx(1.0, abs=0.01)

    def test_analyze_ngrams(self):
        """测试 analyze_ngrams 函数。"""
        result = analyze_ngrams("hello world", n=3)
        assert "total_ngrams" in result
        assert result["total_ngrams"] > 0

    def test_get_text_fingerprint_func(self):
        """测试 get_text_fingerprint 函数。"""
        fp = get_fp_func("hello world")
        assert isinstance(fp, str)
        assert len(fp) > 0


# ===== 集成测试 =====


class TestIntegration:
    """集成测试。"""

    def test_full_plagiarism_check_workflow(self):
        """测试完整抄袭检测工作流。"""
        checker = PlagiarismChecker(similarity_threshold=0.4)
        original_text = "深度学习是机器学习的一个分支，使用多层神经网络进行特征学习"
        plagiarized_text = "深度学习是机器学习的一个分支，使用多层神经网络进行特征学习"
        references = [plagiarized_text]

        report = checker.check(original_text, reference_texts=references)
        assert report.similarity_score > 0.5
        assert report.is_plagiarized is True
        assert len(report.recommendations) > 0

    def test_original_text_workflow(self):
        """测试原创文本工作流。"""
        checker = PlagiarismChecker()
        text = "量子计算利用量子力学原理进行计算，与传统计算有本质区别"
        references = ["深度学习是机器学习的一个分支", "区块链是分布式账本技术"]

        report = checker.check(text, reference_texts=references)
        assert report.overall_score > 0.3
        assert report.is_plagiarized is False

    def test_batch_comparison_workflow(self):
        """测试批量比较工作流。"""
        checker = PlagiarismChecker()
        text = "深度学习模型"
        references = [
            "深度学习模型研究",
            "机器学习算法",
            "深度学习应用",
            "自然语言处理",
            "计算机视觉",
        ]
        results = checker.batch_check(text, references)
        assert len(results) == 5
        # 结果应按相似度降序
        for i in range(len(results) - 1):
            assert results[i]["similarity"] >= results[i + 1]["similarity"]

    def test_fingerprint_workflow(self):
        """测试指纹工作流。"""
        checker = PlagiarismChecker()
        text1 = "深度学习模型研究"
        text2 = "深度学习模型研究"
        text3 = "完全不同的内容"

        fp1 = checker.get_text_fingerprint(text1)
        fp2 = checker.get_text_fingerprint(text2)
        fp3 = checker.get_text_fingerprint(text3)

        assert checker.compare_fingerprints(fp1, fp2) == 1.0
        assert checker.compare_fingerprints(fp1, fp3) < 1.0

    def test_ngram_analysis_workflow(self):
        """测试 n-gram 分析工作流。"""
        analyzer = NGramAnalyzer(n=4)
        text = "深度学习模型研究深度学习模型应用深度学习模型分析"
        analysis = analyzer.analyze(text)
        repeated = analyzer.find_repeated_ngrams(text, min_count=2)
        suspicious = analyzer.detect_suspicious_patterns(text)

        assert analysis["repetition_rate"] > 0
        assert len(repeated) > 0
        assert isinstance(suspicious, list)


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_text_similarity(self):
        """测试空文本相似度。"""
        result = TextSimilarity.cosine_similarity("", "")
        assert result.score == 0.0

    def test_single_char_text(self):
        """测试单字符文本。"""
        result = TextSimilarity.cosine_similarity("a", "a")
        assert result.score == pytest.approx(1.0)

    def test_very_long_text(self):
        """测试超长文本。"""
        text1 = "word " * 1000
        text2 = "word " * 1000
        result = TextSimilarity.cosine_similarity(text1, text2)
        assert result.score == pytest.approx(1.0, abs=0.01)

    def test_unicode_text(self):
        """测试 Unicode 文本。"""
        result = TextSimilarity.cosine_similarity("🎉🎊🎈", "🎉🎊🎈")
        assert result.score >= 0.0

    def test_ngram_size_larger_than_text(self):
        """测试 n-gram 大于文本。"""
        ngrams = _generate_ngrams("ab", n=10)
        assert len(ngrams) == 1

    def test_checker_empty_text(self):
        """测试空文本检测。"""
        checker = PlagiarismChecker()
        report = checker.check("")
        assert isinstance(report, OriginalityReport)

    def test_checker_none_references(self):
        """测试 None 参考文献。"""
        checker = PlagiarismChecker()
        report = checker.check("文本", reference_texts=None)
        assert isinstance(report, OriginalityReport)

    def test_fingerprint_empty_text(self):
        """测试空文本指纹。"""
        checker = PlagiarismChecker()
        fp = checker.get_text_fingerprint("")
        assert isinstance(fp, str)

    def test_similarity_score_range(self):
        """测试相似度分数范围。"""
        texts = [
            ("hello", "hello"),
            ("hello", "world"),
            ("hello world", "hello there"),
            ("", "hello"),
        ]
        for t1, t2 in texts:
            result = TextSimilarity.combined_similarity(t1, t2)
            assert 0.0 <= result.score <= 1.0

    def test_originality_score_range(self):
        """测试原创性分数范围。"""
        scorer = OriginalityScorer()
        report = scorer.score("测试文本", reference_texts=["不同文本"])
        assert 0.0 <= report.overall_score <= 1.0

    def test_multiple_references(self):
        """测试多篇参考文献。"""
        checker = PlagiarismChecker()
        text = "深度学习研究"
        refs = [f"参考文本_{i}" for i in range(20)]
        report = checker.check(text, reference_texts=refs)
        assert isinstance(report, OriginalityReport)

    def test_mixed_language_text(self):
        """测试混合语言文本。"""
        result = TextSimilarity.cosine_similarity("深度学习deep learning", "深度学习deep learning")
        assert result.score == pytest.approx(1.0, abs=0.01)
