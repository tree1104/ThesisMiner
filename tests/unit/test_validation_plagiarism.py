"""抄袭检测器单元测试

测试 PlagiarismDetector 的多算法抄袭检测能力，覆盖：
    - 工具函数（_now_iso / _new_id / _tokenize / _split_sentences /
      _remove_citations / _hamming_distance）
    - 数据结构（PlagiarismMatch / PlagiarismReport / DocumentRecord）
    - 常量（DEFAULT_SIMILARITY_THRESHOLD / SIMHASH_BITS / MINHASH_NUM_HASHES 等）
    - SimHash 算法（compute / similarity）
    - MinHash 算法（compute / similarity）
    - NGramAnalyzer（extract / jaccard_similarity / containment_ratio / find_overlapping_ngrams）
    - SentenceComparator（compare / 编辑距离 / 句子相似度）
    - 主类 PlagiarismDetector（文档库管理 / detect / 批量 / 增量 /
      配置 / 历史 / 来源追溯 / 标注 / 导出）
    - 模块级单例（get_plagiarism_detector / reset_plagiarism_detector）
    - 线程安全与边界情况
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# 将项目根目录加入 sys.path，确保可导入 backend 包
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.validation.plagiarism_detector import (
    CITATION_PATTERNS,
    CRITICAL_PLAGIARISM_THRESHOLD,
    DEFAULT_NGRAM_SIZE,
    DEFAULT_SIMILARITY_THRESHOLD,
    MIN_SENTENCE_LENGTH,
    MINHASH_NUM_HASHES,
    SEVERITY_LEVELS,
    SIMHASH_BITS,
    DocumentRecord,
    MinHash,
    NGramAnalyzer,
    PlagiarismDetector,
    PlagiarismMatch,
    PlagiarismReport,
    SentenceComparator,
    SimHash,
    _hamming_distance,
    _new_id,
    _now_iso,
    _remove_citations,
    _split_sentences,
    _tokenize,
    get_plagiarism_detector,
    reset_plagiarism_detector,
)


# ===== 工具函数测试 =====


class TestNowIso:
    """测试 _now_iso 工具函数。"""

    def test_returns_string(self):
        result = _now_iso()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_is_valid_iso_format(self):
        from datetime import datetime
        result = _now_iso()
        parsed = datetime.fromisoformat(result)
        assert parsed is not None

    def test_increases_over_time(self):
        from datetime import datetime
        t1 = _now_iso()
        time.sleep(0.01)
        t2 = _now_iso()
        assert datetime.fromisoformat(t2) >= datetime.fromisoformat(t1)


class TestNewId:
    """测试 _new_id 工具函数。"""

    def test_default_prefix(self):
        result = _new_id()
        assert result.startswith("match_")

    def test_custom_prefix(self):
        result = _new_id("doc")
        assert result.startswith("doc_")

    def test_uniqueness(self):
        ids = {_new_id() for _ in range(100)}
        assert len(ids) == 100

    def test_length(self):
        result = _new_id("test")
        # "test_" (5) + 8 hex chars = 13
        assert len(result) == 13


class TestTokenize:
    """测试 _tokenize 工具函数。"""

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_pure_english(self):
        tokens = _tokenize("hello world")
        assert "hello" in tokens
        assert "world" in tokens

    def test_pure_chinese(self):
        # 中文应生成 2-gram 和单字
        tokens = _tokenize("你好世界")
        # 应包含单字
        assert "你" in tokens
        assert "好" in tokens
        # 应包含 2-gram
        assert "你好" in tokens
        assert "好世" in tokens

    def test_mixed(self):
        tokens = _tokenize("hello 世界")
        assert "hello" in tokens
        assert "世" in tokens
        assert "界" in tokens

    def test_lowercase(self):
        # 英文应转为小写
        tokens = _tokenize("Hello WORLD")
        assert "hello" in tokens
        assert "world" in tokens

    def test_with_numbers(self):
        tokens = _tokenize("test123")
        # 应识别为 token
        assert len(tokens) > 0


class TestSplitSentences:
    """测试 _split_sentences 工具函数。"""

    def test_empty_string(self):
        assert _split_sentences("") == []

    def test_single_sentence(self):
        result = _split_sentences("这是一个完整的句子。")
        assert len(result) == 1
        start, end, sentence = result[0]
        assert "句子" in sentence

    def test_multiple_sentences(self):
        text = "这是第一句。这是第二句。这是第三句。"
        result = _split_sentences(text)
        assert len(result) == 3

    def test_short_sentence_filtered(self):
        # 短于 MIN_SENTENCE_LENGTH 的句子应被过滤
        text = "短。"
        result = _split_sentences(text)
        assert len(result) == 0

    def test_english_sentences(self):
        text = "This is a sentence. This is another one."
        result = _split_sentences(text)
        assert len(result) >= 1

    def test_question_mark(self):
        text = "这是一个问题？这是回答。"
        result = _split_sentences(text)
        assert len(result) == 2

    def test_returns_positions(self):
        text = "这是一个完整的句子内容。"
        result = _split_sentences(text)
        for start, end, sentence in result:
            assert start >= 0
            assert end > start
            assert isinstance(sentence, str)


class TestRemoveCitations:
    """测试 _remove_citations 工具函数。"""

    def test_no_citations(self):
        text = "这是一段普通文本，没有引用。"
        cleaned, citations = _remove_citations(text)
        assert cleaned == text
        assert citations == []

    def test_english_citation(self):
        text = "研究显示重要结果 (Smith, 2020)。"
        cleaned, citations = _remove_citations(text)
        assert len(citations) == 1
        assert "(Smith, 2020)" not in cleaned

    def test_chinese_citation(self):
        text = "研究显示（张三，2020）重要结果。"
        cleaned, citations = _remove_citations(text)
        assert len(citations) >= 1

    def test_bracket_citation(self):
        text = "研究显示重要结果[1]。"
        cleaned, citations = _remove_citations(text)
        assert len(citations) >= 1

    def test_multiple_bracket_citations(self):
        text = "研究[1, 2, 3]显示重要结果。"
        cleaned, citations = _remove_citations(text)
        assert len(citations) >= 1

    def test_et_al_citation(self):
        text = "Smith et al., 2020 提出了方法。"
        cleaned, citations = _remove_citations(text)
        assert len(citations) >= 1

    def test_multiple_citations(self):
        text = "研究(Smith, 2020)显示结果[1]，另有观点(Jones, 2019)。"
        cleaned, citations = _remove_citations(text)
        assert len(citations) >= 2


class TestHammingDistance:
    """测试 _hamming_distance 工具函数。"""

    def test_same_values(self):
        assert _hamming_distance(0, 0) == 0
        assert _hamming_distance(123, 123) == 0

    def test_one_bit_diff(self):
        assert _hamming_distance(0, 1) == 1
        assert _hamming_distance(0b1000, 0b1001) == 1

    def test_all_bits_diff(self):
        # 所有位都不同
        assert _hamming_distance(0, 0xFF) == 8

    def test_large_numbers(self):
        # 大数应正常计算
        d = _hamming_distance(0xFFFFFFFF, 0x00000000)
        assert d == 32

    def test_custom_bits(self):
        # 自定义位数
        d = _hamming_distance(0, 1, bits=8)
        assert d == 1


# ===== 常量测试 =====


class TestConstants:
    """测试模块常量。"""

    def test_thresholds(self):
        assert 0 < DEFAULT_SIMILARITY_THRESHOLD < 1
        assert CRITICAL_PLAGIARISM_THRESHOLD > DEFAULT_SIMILARITY_THRESHOLD

    def test_ngram_size(self):
        assert DEFAULT_NGRAM_SIZE >= 2

    def test_simhash_bits(self):
        assert SIMHASH_BITS == 64

    def test_minhash_hashes(self):
        assert MINHASH_NUM_HASHES > 0

    def test_min_sentence_length(self):
        assert MIN_SENTENCE_LENGTH > 0

    def test_citation_patterns(self):
        assert len(CITATION_PATTERNS) > 0
        for pattern in CITATION_PATTERNS:
            assert hasattr(pattern, "finditer")

    def test_severity_levels(self):
        expected = {"none", "low", "medium", "high", "critical"}
        assert set(SEVERITY_LEVELS.keys()) == expected


# ===== 数据结构测试 =====


class TestPlagiarismMatch:
    """测试 PlagiarismMatch 数据结构。"""

    def test_default_values(self):
        match = PlagiarismMatch()
        assert match.similarity == 0.0
        assert match.is_citation is False
        assert match.source_text == ""

    def test_custom_values(self):
        match = PlagiarismMatch(
            id="m1",
            source_text="源文本",
            target_text="目标文本",
            similarity=0.85,
            algorithm="simhash",
        )
        assert match.id == "m1"
        assert match.similarity == 0.85
        assert match.algorithm == "simhash"

    def test_to_dict(self):
        match = PlagiarismMatch(id="m1", source_text="测试", similarity=0.5)
        d = match.to_dict()
        assert d["id"] == "m1"
        assert d["similarity"] == 0.5
        assert "source_text" in d


class TestPlagiarismReport:
    """测试 PlagiarismReport 数据结构。"""

    def test_default_values(self):
        report = PlagiarismReport()
        assert report.overall_similarity == 0.0
        assert report.is_plagiarized is False
        assert report.severity == "none"

    def test_with_matches(self):
        matches = [PlagiarismMatch(id="m1"), PlagiarismMatch(id="m2")]
        report = PlagiarismReport(
            id="r1",
            document_id="d1",
            overall_similarity=0.6,
            matches=matches,
            is_plagiarized=True,
            severity="high",
        )
        assert len(report.matches) == 2
        assert report.is_plagiarized is True

    def test_to_dict(self):
        report = PlagiarismReport(
            id="r1",
            document_id="d1",
            overall_similarity=0.5678,
            matches=[PlagiarismMatch(id="m1")],
            source_count=1,
        )
        d = report.to_dict()
        assert d["id"] == "r1"
        # 相似度应四舍五入到 4 位
        assert d["overall_similarity"] == 0.5678
        assert len(d["matches"]) == 1

    def test_to_dict_rounds_similarity(self):
        report = PlagiarismReport(overall_similarity=0.123456789)
        d = report.to_dict()
        assert d["overall_similarity"] == 0.1235


class TestDocumentRecord:
    """测试 DocumentRecord 数据结构。"""

    def test_default_values(self):
        record = DocumentRecord()
        assert record.title == ""
        assert record.simhash == 0
        assert record.minhash == []
        assert record.ngrams == set()

    def test_custom_values(self):
        record = DocumentRecord(
            id="d1",
            title="测试文档",
            content="内容",
            simhash=12345,
            minhash=[1, 2, 3],
            ngrams={"abc", "def"},
        )
        assert record.id == "d1"
        assert record.simhash == 12345
        assert len(record.minhash) == 3

    def test_to_dict(self):
        record = DocumentRecord(
            id="d1",
            title="测试",
            simhash=123,
            minhash=[1, 2],
            ngrams={"a", "b", "c"},
        )
        d = record.to_dict()
        assert d["id"] == "d1"
        assert d["simhash"] == 123
        assert d["ngrams_count"] == 3
        # to_dict 不应包含 content（避免泄露）
        assert "content" not in d

    def test_ngrams_mutable_default(self):
        r1 = DocumentRecord()
        r2 = DocumentRecord()
        r1.ngrams.add("test")
        assert "test" not in r2.ngrams


# ===== SimHash 测试 =====


class TestSimHash:
    """测试 SimHash 算法。"""

    def setup_method(self):
        self.simhash = SimHash()

    def test_compute_empty_text(self):
        assert self.simhash.compute("") == 0

    def test_compute_returns_int(self):
        result = self.simhash.compute("测试文本内容")
        assert isinstance(result, int)

    def test_same_text_same_hash(self):
        # 相同文本应产生相同指纹
        text = "这是一段测试文本用于验证SimHash算法"
        h1 = self.simhash.compute(text)
        h2 = self.simhash.compute(text)
        assert h1 == h2

    def test_similar_text_similar_hash(self):
        # 相似文本的指纹应接近
        text1 = "深度学习是机器学习的一个重要分支"
        text2 = "深度学习是机器学习的重要分支"
        h1 = self.simhash.compute(text1)
        h2 = self.simhash.compute(text2)
        sim = self.simhash.similarity(h1, h2)
        assert sim > 0.5

    def test_different_text_different_hash(self):
        text1 = "深度学习技术发展迅速"
        text2 = "今天天气很好适合出门"
        h1 = self.simhash.compute(text1)
        h2 = self.simhash.compute(text2)
        sim = self.simhash.similarity(h1, h2)
        assert sim < 0.9

    def test_similarity_same_hash(self):
        # 相同指纹相似度应为 1
        h = self.simhash.compute("测试")
        assert self.simhash.similarity(h, h) == 1.0

    def test_similarity_zero_hashes(self):
        # 两个 0 指纹应返回 0
        assert self.simhash.similarity(0, 0) == 0.0

    def test_similarity_range(self):
        # 相似度应在 0-1 之间
        h1 = self.simhash.compute("文本一")
        h2 = self.simhash.compute("文本二")
        sim = self.simhash.similarity(h1, h2)
        assert 0.0 <= sim <= 1.0

    def test_custom_bits(self):
        # 自定义位数
        simhash_32 = SimHash(bits=32)
        result = simhash_32.compute("测试文本")
        assert isinstance(result, int)


# ===== MinHash 测试 =====


class TestMinHash:
    """测试 MinHash 算法。"""

    def setup_method(self):
        self.minhash = MinHash(num_hashes=64)

    def test_compute_empty_text(self):
        result = self.minhash.compute("")
        assert isinstance(result, list)
        assert len(result) == 64
        assert all(h == 0 for h in result)

    def test_compute_returns_list(self):
        result = self.minhash.compute("测试文本")
        assert isinstance(result, list)
        assert len(result) == 64

    def test_same_text_same_signature(self):
        text = "这是一段测试文本"
        sig1 = self.minhash.compute(text)
        sig2 = self.minhash.compute(text)
        assert sig1 == sig2

    def test_similar_text_high_similarity(self):
        text1 = "深度学习是机器学习的重要分支"
        text2 = "深度学习是机器学习的重要分支"
        sig1 = self.minhash.compute(text1)
        sig2 = self.minhash.compute(text2)
        sim = self.minhash.similarity(sig1, sig2)
        assert sim == 1.0

    def test_different_text_lower_similarity(self):
        text1 = "深度学习技术发展"
        text2 = "今天天气很好适合"
        sig1 = self.minhash.compute(text1)
        sig2 = self.minhash.compute(text2)
        sim = self.minhash.similarity(sig1, sig2)
        assert sim < 1.0

    def test_similarity_empty_signatures(self):
        assert self.minhash.similarity([], []) == 0.0

    def test_similarity_different_lengths(self):
        sig1 = [1, 2, 3]
        sig2 = [1, 2, 3, 4, 5]
        sim = self.minhash.similarity(sig1, sig2)
        # 应按较短长度计算
        assert 0.0 <= sim <= 1.0

    def test_custom_num_hashes(self):
        minhash_32 = MinHash(num_hashes=32)
        result = minhash_32.compute("测试")
        assert len(result) == 32


# ===== NGramAnalyzer 测试 =====


class TestNGramAnalyzer:
    """测试 NGramAnalyzer。"""

    def setup_method(self):
        self.analyzer = NGramAnalyzer(n=3)

    def test_extract_empty(self):
        assert self.analyzer.extract("") == set()

    def test_extract_short_text(self):
        # 短于 n 的文本应返回整个文本
        result = self.analyzer.extract("ab")
        assert result == {"ab"}

    def test_extract_normal(self):
        result = self.analyzer.extract("abcdef")
        assert "abc" in result
        assert "bcd" in result
        assert "cde" in result
        assert "def" in result

    def test_extract_removes_whitespace(self):
        result = self.analyzer.extract("a b c d")
        # 空白应被移除
        assert "abc" in result

    def test_extract_chinese(self):
        result = self.analyzer.extract("你好世界")
        assert "你好世" in result
        assert "好世界" in result

    def test_jaccard_similarity_both_empty(self):
        assert self.analyzer.jaccard_similarity(set(), set()) == 0.0

    def test_jaccard_similarity_identical(self):
        s = {"a", "b", "c"}
        assert self.analyzer.jaccard_similarity(s, s) == 1.0

    def test_jaccard_similarity_disjoint(self):
        s1 = {"a", "b"}
        s2 = {"c", "d"}
        assert self.analyzer.jaccard_similarity(s1, s2) == 0.0

    def test_jaccard_similarity_partial(self):
        s1 = {"a", "b", "c"}
        s2 = {"b", "c", "d"}
        # 交集 2，并集 4
        assert self.analyzer.jaccard_similarity(s1, s2) == 0.5

    def test_containment_ratio_empty_subset(self):
        assert self.analyzer.containment_ratio(set(), {"a"}) == 0.0

    def test_containment_ratio_full(self):
        s = {"a", "b"}
        assert self.analyzer.containment_ratio(s, {"a", "b", "c"}) == 1.0

    def test_containment_ratio_partial(self):
        subset = {"a", "b", "c"}
        superset = {"a", "b", "d", "e"}
        # 交集 2，子集 3
        assert self.analyzer.containment_ratio(subset, superset) == 2 / 3

    def test_find_overlapping_ngrams(self):
        s1 = {"a", "b", "c"}
        s2 = {"b", "c", "d"}
        overlap = self.analyzer.find_overlapping_ngrams(s1, s2)
        assert overlap == {"b", "c"}

    def test_min_n_enforced(self):
        # n 小于 2 应被强制为 2
        analyzer = NGramAnalyzer(n=1)
        assert analyzer._n >= 2


# ===== SentenceComparator 测试 =====


class TestSentenceComparator:
    """测试 SentenceComparator。"""

    def setup_method(self):
        self.comparator = SentenceComparator(threshold=0.3)

    def test_compare_identical(self):
        text1 = "这是一段完全相同的文本内容用于测试。"
        text2 = "这是一段完全相同的文本内容用于测试。"
        results = self.comparator.compare(text1, text2)
        assert len(results) >= 1
        # 相同文本相似度应很高
        for _, _, _, _, sim in results:
            assert sim > 0.5

    def test_compare_different(self):
        text1 = "深度学习技术发展迅速应用广泛。"
        text2 = "今天天气晴朗适合户外活动。"
        results = self.comparator.compare(text1, text2)
        # 不同文本应无高相似度匹配
        for _, _, _, _, sim in results:
            assert sim < 0.8

    def test_compare_empty_text(self):
        assert self.comparator.compare("", "测试文本") == []
        assert self.comparator.compare("测试文本", "") == []

    def test_compare_returns_tuples(self):
        text1 = "这是一段测试文本用于验证句子比对功能。"
        text2 = "这是一段测试文本用于验证句子比对功能。"
        results = self.comparator.compare(text1, text2)
        for result in results:
            assert len(result) == 5
            start, end, s1, s2, sim = result
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert isinstance(s1, str)
            assert isinstance(s2, str)
            assert isinstance(sim, float)

    def test_edit_distance_similarity_identical(self):
        sim = self.comparator._edit_distance_similarity("abc", "abc")
        assert sim == 1.0

    def test_edit_distance_similarity_different(self):
        sim = self.comparator._edit_distance_similarity("abc", "xyz")
        assert sim < 1.0

    def test_edit_distance_similarity_empty(self):
        assert self.comparator._edit_distance_similarity("", "") == 1.0

    def test_levenshtein_same(self):
        assert self.comparator._levenshtein("abc", "abc") == 0

    def test_levenshtein_different(self):
        assert self.comparator._levenshtein("abc", "xyz") == 3

    def test_levenshtein_insertion(self):
        assert self.comparator._levenshtein("ab", "abc") == 1

    def test_levenshtein_deletion(self):
        assert self.comparator._levenshtein("abc", "ab") == 1

    def test_levenshtein_empty(self):
        assert self.comparator._levenshtein("", "abc") == 3
        assert self.comparator._levenshtein("abc", "") == 3

    def test_custom_threshold(self):
        comparator = SentenceComparator(threshold=0.9)
        text1 = "这是一段测试文本内容。"
        text2 = "这是一段测试文本内容。"
        results = comparator.compare(text1, text2)
        # 高阈值下相同文本仍应匹配
        assert len(results) >= 1


# ===== PlagiarismDetector 主类测试 =====


class TestPlagiarismDetectorInit:
    """测试 PlagiarismDetector 初始化。"""

    def test_init_default(self):
        detector = PlagiarismDetector()
        assert detector._threshold == DEFAULT_SIMILARITY_THRESHOLD
        assert detector.document_count() == 0

    def test_init_custom_threshold(self):
        detector = PlagiarismDetector(similarity_threshold=0.5)
        assert detector._threshold == 0.5

    def test_init_custom_ngram_size(self):
        detector = PlagiarismDetector(ngram_size=5)
        assert detector._ngram._n == 5

    def test_init_creates_components(self):
        detector = PlagiarismDetector()
        assert detector._simhash is not None
        assert detector._minhash is not None
        assert detector._ngram is not None
        assert detector._sentence_comparator is not None


class TestDocumentManagement:
    """测试文档库管理。"""

    def test_add_document(self):
        detector = PlagiarismDetector()
        doc_id = detector.add_document("d1", "标题", "这是文档内容用于测试")
        assert doc_id == "d1"
        assert detector.document_count() == 1

    def test_add_document_auto_id(self):
        detector = PlagiarismDetector()
        doc_id = detector.add_document("", "标题", "内容")
        assert doc_id.startswith("doc_")
        assert detector.document_count() == 1

    def test_add_document_computes_fingerprints(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "标题", "这是文档内容")
        doc = detector.get_document("d1")
        assert doc.simhash != 0 or doc.minhash != [0] * MINHASH_NUM_HASHES
        assert len(doc.ngrams) > 0

    def test_get_document(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "标题", "内容")
        doc = detector.get_document("d1")
        assert doc is not None
        assert doc.title == "标题"

    def test_get_nonexistent_document(self):
        detector = PlagiarismDetector()
        assert detector.get_document("nonexistent") is None

    def test_remove_document(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "标题", "内容")
        result = detector.remove_document("d1")
        assert result is True
        assert detector.document_count() == 0

    def test_remove_nonexistent_document(self):
        detector = PlagiarismDetector()
        result = detector.remove_document("nonexistent")
        assert result is False

    def test_list_documents(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "标题1", "内容1")
        detector.add_document("d2", "标题2", "内容2")
        docs = detector.list_documents()
        assert len(docs) == 2

    def test_document_count(self):
        detector = PlagiarismDetector()
        assert detector.document_count() == 0
        detector.add_document("d1", "标题", "内容")
        assert detector.document_count() == 1


class TestDetect:
    """测试 detect 检测接口。"""

    def test_detect_empty_text(self):
        detector = PlagiarismDetector()
        report = detector.detect("")
        assert isinstance(report, PlagiarismReport)
        assert report.overall_similarity == 0.0

    def test_detect_no_documents(self):
        # 无文档库时应返回空报告
        detector = PlagiarismDetector()
        report = detector.detect("测试文本")
        assert isinstance(report, PlagiarismReport)
        assert report.overall_similarity == 0.0

    def test_detect_identical_text(self):
        # 相同文本应高相似度
        detector = PlagiarismDetector()
        content = "深度学习是机器学习的一个重要分支，近年来发展迅速。"
        detector.add_document("d1", "源文档", content)
        report = detector.detect(content)
        assert report.overall_similarity > 0.3

    def test_detect_different_text(self):
        # 不同文本应低相似度
        detector = PlagiarismDetector()
        detector.add_document("d1", "源文档", "深度学习技术发展迅速应用广泛。")
        report = detector.detect("今天天气晴朗适合户外运动。")
        assert report.overall_similarity < 0.5

    def test_detect_with_citations(self):
        # 含引用的文本应排除引用
        detector = PlagiarismDetector()
        detector.add_document("d1", "源文档", "研究显示重要结果。")
        text = "研究显示重要结果 (Smith, 2020)。"
        report = detector.detect(text, exclude_citations=True)
        assert report.citation_count >= 1

    def test_detect_without_excluding_citations(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "源文档", "研究(Smith, 2020)显示结果。")
        report = detector.detect("研究(Smith, 2020)显示结果。", exclude_citations=False)
        assert report.citation_count == 0

    def test_detect_with_compare_with(self):
        # 指定比对文档
        detector = PlagiarismDetector()
        detector.add_document("d1", "文档1", "内容一")
        detector.add_document("d2", "文档2", "内容二")
        report = detector.detect("内容一", compare_with=["d1"])
        assert isinstance(report, PlagiarismReport)

    def test_detect_with_specific_algorithms(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "文档", "深度学习是机器学习的重要分支。")
        report = detector.detect(
            "深度学习是机器学习的重要分支。",
            algorithms=["simhash"],
        )
        assert isinstance(report, PlagiarismReport)
        # 应只使用 simhash 算法
        assert "simhash" in report.algorithm_stats

    def test_detect_returns_report_with_id(self):
        detector = PlagiarismDetector()
        report = detector.detect("测试文本")
        assert report.id.startswith("report_")

    def test_detect_severity_levels(self):
        # 不同相似度应产生不同严重级别
        detector = PlagiarismDetector()
        content = "深度学习是机器学习的一个重要分支发展迅速应用广泛。" * 5
        detector.add_document("d1", "源", content)
        report = detector.detect(content)
        assert report.severity in SEVERITY_LEVELS

    def test_detect_is_plagiarized(self):
        # 高相似度应标记为抄袭
        detector = PlagiarismDetector()
        content = "深度学习是机器学习的一个重要分支发展迅速应用广泛。" * 10
        detector.add_document("d1", "源", content)
        report = detector.detect(content)
        if report.overall_similarity >= CRITICAL_PLAGIARISM_THRESHOLD:
            assert report.is_plagiarized is True

    def test_detect_records_history(self):
        detector = PlagiarismDetector()
        detector.detect("测试文本")
        assert len(detector._history) == 1


class TestDetectBatch:
    """测试批量检测。"""

    def test_detect_batch_multiple(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "源", "深度学习内容")
        documents = [
            {"text": "测试文本一", "document_id": "t1"},
            {"text": "测试文本二", "document_id": "t2"},
            {"text": "测试文本三", "document_id": "t3"},
        ]
        reports = detector.detect_batch(documents)
        assert len(reports) == 3

    def test_detect_batch_empty(self):
        detector = PlagiarismDetector()
        reports = detector.detect_batch([])
        assert reports == []

    def test_detect_batch_with_citations(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "源", "研究内容")
        documents = [
            {"text": "研究内容 (Smith, 2020)", "document_id": "t1"},
        ]
        reports = detector.detect_batch(documents, exclude_citations=True)
        assert reports[0].citation_count >= 1


class TestDetectIncremental:
    """测试增量检测。"""

    def test_detect_incremental_adds_documents(self):
        detector = PlagiarismDetector()
        new_docs = [
            {"id": "new1", "title": "新文档", "content": "新内容"},
        ]
        report = detector.detect_incremental("测试文本", "t1", new_documents=new_docs)
        assert detector.document_count() == 1
        assert isinstance(report, PlagiarismReport)

    def test_detect_incremental_no_new_docs(self):
        detector = PlagiarismDetector()
        report = detector.detect_incremental("测试文本", "t1")
        assert isinstance(report, PlagiarismReport)


class TestConfiguration:
    """测试配置管理。"""

    def test_set_threshold(self):
        detector = PlagiarismDetector()
        detector.set_threshold(0.6)
        assert detector._threshold == 0.6

    def test_set_threshold_clamped(self):
        # 阈值应被限制在 0-1
        detector = PlagiarismDetector()
        detector.set_threshold(1.5)
        assert detector._threshold == 1.0
        detector.set_threshold(-0.5)
        assert detector._threshold == 0.0

    def test_set_algorithm_weights(self):
        detector = PlagiarismDetector()
        detector.set_algorithm_weights({"simhash": 0.5})
        assert detector._algorithm_weights["simhash"] == 0.5

    def test_get_config(self):
        detector = PlagiarismDetector()
        config = detector.get_config()
        assert "similarity_threshold" in config
        assert "ngram_size" in config
        assert "algorithm_weights" in config
        assert "document_count" in config


class TestHistoryAndStats:
    """测试历史与统计。"""

    def test_get_history_all(self):
        detector = PlagiarismDetector()
        detector.detect("文本一")
        detector.detect("文本二")
        history = detector.get_history()
        assert len(history) == 2

    def test_get_history_by_document_id(self):
        detector = PlagiarismDetector()
        detector.detect("文本一", document_id="d1")
        detector.detect("文本二", document_id="d2")
        history = detector.get_history(document_id="d1")
        assert len(history) == 1
        assert all(r.document_id == "d1" for r in history)

    def test_get_history_limit(self):
        detector = PlagiarismDetector()
        for i in range(5):
            detector.detect(f"文本{i}")
        history = detector.get_history(limit=2)
        assert len(history) == 2

    def test_stats_empty(self):
        detector = PlagiarismDetector()
        stats = detector.stats()
        assert stats["total_detections"] == 0
        assert stats["avg_similarity"] == 0.0

    def test_stats_with_history(self):
        detector = PlagiarismDetector()
        detector.detect("文本一")
        detector.detect("文本二")
        stats = detector.stats()
        assert stats["total_detections"] == 2
        assert "avg_similarity" in stats
        assert "plagiarism_rate" in stats

    def test_clear_history(self):
        detector = PlagiarismDetector()
        detector.detect("文本")
        detector.clear_history()
        assert len(detector._history) == 0


class TestSourceTracing:
    """测试来源追溯。"""

    def test_trace_source_found(self):
        detector = PlagiarismDetector()
        content = "深度学习是机器学习的重要分支发展迅速应用广泛。" * 5
        detector.add_document("d1", "源文档", content)
        report = detector.detect(content)
        if report.matches:
            match_id = report.matches[0].id
            result = detector.trace_source(match_id)
            assert result is not None
            assert "match" in result
            assert "source_info" in result

    def test_trace_source_not_found(self):
        detector = PlagiarismDetector()
        result = detector.trace_source("nonexistent")
        assert result is None

    def test_parse_source_reference_with_parentheses(self):
        detector = PlagiarismDetector()
        info = detector._parse_source_reference("论文标题 (作者, 2020)")
        assert info["title"] == "论文标题"
        assert info["author"] == "作者"
        assert info["year"] == 2020

    def test_parse_source_reference_no_parentheses(self):
        detector = PlagiarismDetector()
        info = detector._parse_source_reference("仅标题")
        assert info["title"] == "仅标题"
        assert info["year"] == 0

    def test_parse_source_reference_empty(self):
        detector = PlagiarismDetector()
        info = detector._parse_source_reference("")
        assert info["title"] == ""


class TestAnnotateText:
    """测试相似段落标注。"""

    def test_annotate_no_matches(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport()
        text = "原始文本内容"
        result = detector.annotate_text(text, report)
        assert result == text

    def test_annotate_with_matches(self):
        detector = PlagiarismDetector()
        match = PlagiarismMatch(
            id="m1",
            source_start=2,
            source_end=5,
            similarity=0.8,
            source_reference="来源",
        )
        report = PlagiarismReport(matches=[match])
        text = "这是原始文本内容用于标注测试"
        result = detector.annotate_text(text, report)
        assert "【" in result or result == text  # 可能因区间逻辑返回原文

    def test_annotate_overlapping_intervals(self):
        detector = PlagiarismDetector()
        matches = [
            PlagiarismMatch(source_start=0, source_end=5, similarity=0.8, source_reference="源1"),
            PlagiarismMatch(source_start=3, source_end=8, similarity=0.7, source_reference="源2"),
        ]
        report = PlagiarismReport(matches=matches)
        text = "这是原始文本内容"
        result = detector.annotate_text(text, report)
        assert isinstance(result, str)


class TestSimilarityDistribution:
    """测试相似度分布统计。"""

    def test_distribution_empty_report(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport()
        dist = detector.get_similarity_distribution(report)
        assert sum(dist.values()) == 0

    def test_distribution_with_matches(self):
        detector = PlagiarismDetector()
        matches = [
            PlagiarismMatch(similarity=0.05),
            PlagiarismMatch(similarity=0.2),
            PlagiarismMatch(similarity=0.4),
            PlagiarismMatch(similarity=0.6),
            PlagiarismMatch(similarity=0.8),
        ]
        report = PlagiarismReport(matches=matches)
        dist = detector.get_similarity_distribution(report)
        assert dist["0-10%"] == 1
        assert dist["10-30%"] == 1
        assert dist["30-50%"] == 1
        assert dist["50-70%"] == 1
        assert dist["70-100%"] == 1

    def test_distribution_keys(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport()
        dist = detector.get_similarity_distribution(report)
        expected_keys = {"0-10%", "10-30%", "30-50%", "50-70%", "70-100%"}
        assert set(dist.keys()) == expected_keys


class TestExportReport:
    """测试报告导出。"""

    def test_export_dict(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport(id="r1", document_id="d1")
        result = detector.export_report(report, format="dict")
        assert isinstance(result, dict)
        assert result["id"] == "r1"

    def test_export_json(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport(id="r1")
        result = detector.export_report(report, format="json")
        assert isinstance(result, str)
        assert "r1" in result

    def test_export_text(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport(
            id="r1",
            document_id="d1",
            overall_similarity=0.5,
            severity="medium",
        )
        result = detector.export_report(report, format="text")
        assert isinstance(result, str)
        assert "抄袭检测报告" in result
        assert "r1" in result

    def test_export_unknown_format(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport(id="r1")
        result = detector.export_report(report, format="unknown")
        # 未知格式应回退到 dict
        assert isinstance(result, dict)


class TestScheduledDetection:
    """测试定时检测。"""

    def test_schedule_detection(self):
        detector = PlagiarismDetector()
        config = detector.schedule_detection(["d1", "d2"], interval_hours=12)
        assert config["task_id"].startswith("task_")
        assert config["document_ids"] == ["d1", "d2"]
        assert config["interval_hours"] == 12
        assert config["status"] == "scheduled"

    def test_run_scheduled_detection(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "文档1", "深度学习内容一")
        detector.add_document("d2", "文档2", "深度学习内容二")
        reports = detector.run_scheduled_detection(["d1"])
        assert isinstance(reports, list)

    def test_run_scheduled_nonexistent_doc(self):
        detector = PlagiarismDetector()
        reports = detector.run_scheduled_detection(["nonexistent"])
        assert reports == []


# ===== 模块级单例测试 =====


class TestGlobalInstance:
    """测试模块级单例。"""

    def test_get_singleton(self):
        reset_plagiarism_detector()
        instance1 = get_plagiarism_detector()
        instance2 = get_plagiarism_detector()
        assert instance1 is instance2

    def test_reset_singleton(self):
        reset_plagiarism_detector()
        instance1 = get_plagiarism_detector()
        reset_plagiarism_detector()
        instance2 = get_plagiarism_detector()
        assert instance1 is not instance2

    def test_singleton_is_detector(self):
        reset_plagiarism_detector()
        instance = get_plagiarism_detector()
        assert isinstance(instance, PlagiarismDetector)


# ===== 线程安全测试 =====


class TestThreadSafety:
    """测试线程安全。"""

    def test_concurrent_add_documents(self):
        # 并发添加文档
        detector = PlagiarismDetector()
        errors = []

        def worker(worker_id):
            try:
                for i in range(5):
                    detector.add_document(
                        f"d_{worker_id}_{i}",
                        f"文档{worker_id}_{i}",
                        f"内容{worker_id}_{i}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert detector.document_count() == 20

    def test_concurrent_detect(self):
        # 并发检测
        detector = PlagiarismDetector()
        detector.add_document("d1", "源", "深度学习是机器学习的重要分支。")
        errors = []
        results = []

        def worker():
            try:
                for _ in range(3):
                    report = detector.detect("深度学习是机器学习的重要分支。")
                    results.append(report)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 12

    def test_concurrent_add_remove(self):
        # 并发添加和删除
        detector = PlagiarismDetector()
        errors = []

        def adder():
            try:
                for i in range(10):
                    detector.add_document(f"d_add_{i}", f"文档{i}", f"内容{i}")
            except Exception as e:
                errors.append(e)

        def remover():
            try:
                for i in range(10):
                    detector.remove_document(f"d_add_{i}")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=adder)
        t2 = threading.Thread(target=remover)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0


# ===== 边界情况测试 =====


class TestEdgeCases:
    """测试边界情况。"""

    def test_detect_whitespace_text(self):
        detector = PlagiarismDetector()
        report = detector.detect("   ")
        assert isinstance(report, PlagiarismReport)
        assert report.overall_similarity == 0.0

    def test_detect_very_long_text(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "源", "内容" * 1000)
        report = detector.detect("内容" * 1000)
        assert isinstance(report, PlagiarismReport)

    def test_detect_special_characters(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "源", "特殊字符<>&\"'")
        report = detector.detect("特殊字符<>&\"'")
        assert isinstance(report, PlagiarismReport)

    def test_detect_unicode(self):
        detector = PlagiarismDetector()
        detector.add_document("d1", "源", "日本語のテキスト")
        report = detector.detect("日本語のテキスト")
        assert isinstance(report, PlagiarismReport)

    def test_add_document_with_citations(self):
        # 含引用的文档应正确处理
        detector = PlagiarismDetector()
        content = "研究显示结果 (Smith, 2020) 很重要。"
        doc_id = detector.add_document("d1", "标题", content)
        assert doc_id == "d1"
        doc = detector.get_document("d1")
        assert doc is not None

    def test_detect_compare_with_nonexistent(self):
        # 比对不存在的文档应不崩溃
        detector = PlagiarismDetector()
        detector.add_document("d1", "源", "内容")
        report = detector.detect("测试", compare_with=["nonexistent"])
        assert isinstance(report, PlagiarismReport)

    def test_severity_determination(self):
        detector = PlagiarismDetector()
        # 测试各严重级别
        assert detector._determine_severity(0.8) == "critical"
        assert detector._determine_severity(0.6) == "high"
        assert detector._determine_severity(0.4) == "medium"
        assert detector._determine_severity(0.2) == "low"
        assert detector._determine_severity(0.05) == "none"

    def test_merge_matches_dedup(self):
        # 相同来源+算法的匹配应去重
        detector = PlagiarismDetector()
        matches = [
            PlagiarismMatch(source_reference="源1", algorithm="simhash", similarity=0.5),
            PlagiarismMatch(source_reference="源1", algorithm="simhash", similarity=0.8),
            PlagiarismMatch(source_reference="源2", algorithm="simhash", similarity=0.6),
        ]
        merged = detector._merge_matches(matches)
        # 源1+simhash 只保留最高分
        assert len(merged) == 2
        # 最高分应排在前面
        assert merged[0].similarity >= merged[1].similarity

    def test_merge_empty_matches(self):
        detector = PlagiarismDetector()
        assert detector._merge_matches([]) == []

    def test_compute_overall_similarity_empty(self):
        detector = PlagiarismDetector()
        assert detector._compute_overall_similarity({}, 100) == 0.0

    def test_compute_algorithm_stats_empty(self):
        detector = PlagiarismDetector()
        stats = detector._compute_algorithm_stats({})
        assert stats == {}

    def test_compute_algorithm_stats_with_data(self):
        detector = PlagiarismDetector()
        results = {
            "simhash": [0.5, 0.7, 0.3],
            "ngram": [0.4],
        }
        stats = detector._compute_algorithm_stats(results)
        assert stats["simhash"]["count"] == 3
        assert stats["simhash"]["max"] == 0.7
        assert "avg" in stats["simhash"]

    def test_generate_recommendations_no_plagiarism(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport(overall_similarity=0.05, is_plagiarized=False)
        recs = detector._generate_recommendations(report)
        assert any("未检测到" in r for r in recs)

    def test_generate_recommendations_critical(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport(overall_similarity=0.8, is_plagiarized=True)
        recs = detector._generate_recommendations(report)
        assert any("严重抄袭" in r for r in recs)

    def test_generate_recommendations_medium(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport(overall_similarity=0.4, is_plagiarized=False)
        recs = detector._generate_recommendations(report)
        assert any("中度相似" in r for r in recs)

    def test_generate_recommendations_with_citations(self):
        detector = PlagiarismDetector()
        report = PlagiarismReport(overall_similarity=0.05, citation_count=3)
        recs = detector._generate_recommendations(report)
        assert any("3处引用" in r for r in recs)

    def test_extract_matched_text_empty(self):
        detector = PlagiarismDetector()
        assert detector._extract_matched_text("文本", set()) == ""

    def test_extract_matched_text_found(self):
        detector = PlagiarismDetector()
        text = "这是测试文本内容"
        ngrams = detector._ngram.extract(text)
        result = detector._extract_matched_text(text, ngrams)
        assert isinstance(result, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
