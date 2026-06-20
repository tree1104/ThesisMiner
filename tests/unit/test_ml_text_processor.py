"""TextProcessor 单元测试

覆盖范围：
    - 分词（中文 / 英文 / 中英文混合）
    - 句子分割（中英文标点感知）
    - 段落识别
    - 文本相似度（余弦 / Jaccard / 编辑距离 / N-gram / 混合）
    - 关键词提取（TF-IDF / TextRank）
    - 摘要生成（TextRank / 频率）
    - 文本分类（基于规则）
    - 情感分析（基于词典）
    - 语言检测
    - 引用识别与移除
    - 公式识别与移除
    - 学术文本清理
    - SimHash 与汉明距离
    - 文本去重与重复查找
    - 文本统计
    - 章节识别与分割
    - 缓存管理
    - 模块级便捷函数

运行方式：
    pytest tests/unit/test_ml_text_processor.py -v
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from backend.ml.text_processor import (
    CHINESE_PUNCTUATIONS,
    CHINESE_STOPWORDS,
    CITATION_PATTERNS,
    CJK_PATTERN,
    ENGLISH_STOPWORDS,
    ENGLISH_WORD_PATTERN,
    FORMULA_PATTERNS,
    NUMBER_PATTERN,
    SECTION_HEADERS,
    SENTENCE_ENDINGS,
    Citation,
    Formula,
    Keyword,
    Paragraph,
    Sentence,
    SentimentResult,
    TextClassification,
    TextProcessor,
    TokenizeResult,
    compute_similarity,
    extract_keywords,
    get_text_processor,
    summarize,
    tokenize,
)


# ===== 公共夹具 =====


@pytest.fixture
def processor():
    """返回一个全新的 TextProcessor 实例。"""
    return TextProcessor()


@pytest.fixture
def sample_chinese_text():
    """中文样例文本。"""
    return "深度学习在自然语言处理中的应用研究"


@pytest.fixture
def sample_english_text():
    """英文样例文本。"""
    return "Deep learning has been applied to natural language processing."


@pytest.fixture
def sample_mixed_text():
    """中英文混合样例文本。"""
    return "本文研究 deep learning 在 NLP 中的应用。"


@pytest.fixture
def sample_long_text():
    """长样例文本（用于关键词提取与摘要）。"""
    return (
        "深度学习是机器学习的一个分支，通过多层神经网络学习数据的表示。"
        "深度学习在图像识别、自然语言处理、语音识别等领域取得了显著成果。"
        "卷积神经网络和循环神经网络是深度学习的两种重要模型。"
        "近年来，Transformer 架构在自然语言处理任务中表现优异。"
    )


# ===== 数据类测试 =====


class TestDataclasses:
    """数据类测试。"""

    def test_tokenize_result_defaults(self):
        """TokenizeResult 默认值。"""
        r = TokenizeResult()
        assert r.tokens == []
        assert r.language == "mixed"
        assert r.token_count == 0

    def test_tokenize_result_to_dict(self):
        """TokenizeResult to_dict。"""
        r = TokenizeResult(tokens=["a", "b"], language="en", token_count=2, char_count=10)
        d = r.to_dict()
        assert d["tokens"] == ["a", "b"]
        assert d["language"] == "en"
        assert d["token_count"] == 2

    def test_sentence_to_dict(self):
        """Sentence to_dict。"""
        s = Sentence(text="你好。", start_pos=0, end_pos=3, language="zh")
        d = s.to_dict()
        assert d["text"] == "你好。"
        assert d["start_pos"] == 0
        assert d["end_pos"] == 3

    def test_paragraph_to_dict(self):
        """Paragraph to_dict。"""
        p = Paragraph(text="段落", start_pos=0, end_pos=2)
        d = p.to_dict()
        assert d["text"] == "段落"
        assert d["sentences"] == []

    def test_keyword_to_dict(self):
        """Keyword to_dict。"""
        k = Keyword(word="深度学习", score=0.95, frequency=3)
        d = k.to_dict()
        assert d["word"] == "深度学习"
        assert d["score"] == 0.95
        assert d["frequency"] == 3

    def test_citation_to_dict(self):
        """Citation to_dict。"""
        c = Citation(raw_text="[1]", citation_type="bracket", start_pos=0, end_pos=3)
        d = c.to_dict()
        assert d["raw_text"] == "[1]"
        assert d["citation_type"] == "bracket"

    def test_formula_to_dict(self):
        """Formula to_dict。"""
        f = Formula(raw_text="$x$", formula_type="inline", start_pos=0, end_pos=3)
        d = f.to_dict()
        assert d["raw_text"] == "$x$"
        assert d["formula_type"] == "inline"

    def test_text_classification_to_dict(self):
        """TextClassification to_dict。"""
        c = TextClassification(category="abstract", confidence=0.9, labels=["abstract"])
        d = c.to_dict()
        assert d["category"] == "abstract"
        assert d["confidence"] == 0.9

    def test_sentiment_result_to_dict(self):
        """SentimentResult to_dict。"""
        s = SentimentResult(sentiment="positive", score=0.8, positive_words=["好"])
        d = s.to_dict()
        assert d["sentiment"] == "positive"
        assert d["score"] == 0.8


# ===== 分词测试 =====


class TestTokenize:
    """分词功能测试。"""

    def test_tokenize_chinese(self, processor, sample_chinese_text):
        """中文分词。"""
        result = processor.tokenize(sample_chinese_text)
        assert result.token_count > 0
        assert result.language in ("zh", "mixed")
        assert all(isinstance(t, str) for t in result.tokens)

    def test_tokenize_english(self, processor, sample_english_text):
        """英文分词。"""
        result = processor.tokenize(sample_english_text)
        assert result.token_count > 0
        assert "Deep" in result.tokens or "deep" in [t.lower() for t in result.tokens]

    def test_tokenize_mixed(self, processor, sample_mixed_text):
        """中英文混合分词。"""
        result = processor.tokenize(sample_mixed_text)
        assert result.token_count > 0
        assert result.language == "mixed"

    def test_tokenize_empty(self, processor):
        """空文本分词。"""
        result = processor.tokenize("")
        assert result.tokens == []
        assert result.token_count == 0

    def test_tokenize_with_punctuation(self, processor):
        """保留标点。"""
        text = "你好，世界！"
        result_with = processor.tokenize(text, keep_punctuation=True)
        result_without = processor.tokenize(text, keep_punctuation=False)
        # 保留标点时 token 数应不少于不保留时
        assert len(result_with.tokens) >= len(result_without.tokens)

    def test_tokenize_remove_stopwords(self, processor):
        """移除停用词。"""
        text = "这是一个测试"
        result_with = processor.tokenize(text, remove_stopwords=False)
        result_without = processor.tokenize(text, remove_stopwords=True)
        # 移除停用词后 token 数应不多于之前
        assert len(result_without.tokens) <= len(result_with.tokens)

    def test_tokenize_to_words(self, processor, sample_chinese_text):
        """tokenize_to_words 便捷方法。"""
        words = processor.tokenize_to_words(sample_chinese_text)
        assert isinstance(words, list)
        assert len(words) > 0

    def test_tokenize_cache(self, processor, sample_chinese_text):
        """分词结果应被缓存。"""
        result1 = processor.tokenize(sample_chinese_text)
        result2 = processor.tokenize(sample_chinese_text)
        # 缓存命中应返回同一对象
        assert result1 is result2

    def test_tokenize_numbers(self, processor):
        """数字应整体保留。"""
        text = "准确率达到 95.5%"
        result = processor.tokenize(text, keep_punctuation=True)
        # 应包含数字 token
        assert any("95" in t for t in result.tokens)

    def test_tokenize_normalize_fullwidth(self, processor):
        """全角字符应被规范化为半角。"""
        text = "ＡＢＣ１２３"
        result = processor.tokenize(text)
        # 全角应转为半角
        joined = "".join(result.tokens)
        assert "A" in joined or "1" in joined


# ===== 句子分割测试 =====


class TestSplitSentences:
    """句子分割测试。"""

    def test_split_chinese_sentences(self, processor):
        """中文句子分割。"""
        text = "这是第一句。这是第二句！这是第三句？最后一句。"
        sentences = processor.split_sentences(text)
        assert len(sentences) == 4
        assert all(isinstance(s, Sentence) for s in sentences)

    def test_split_english_sentences(self, processor):
        """英文句子分割。"""
        text = "First sentence. Second sentence! Third sentence?"
        sentences = processor.split_sentences(text)
        assert len(sentences) == 3

    def test_split_mixed_sentences(self, processor):
        """中英文混合句子分割。"""
        text = "这是中文句。This is English. 混合句！"
        sentences = processor.split_sentences(text)
        assert len(sentences) == 3

    def test_split_empty_text(self, processor):
        """空文本分割。"""
        assert processor.split_sentences("") == []

    def test_split_no_ending(self, processor):
        """无结束符的文本。"""
        text = "没有结束符的句子"
        sentences = processor.split_sentences(text)
        assert len(sentences) == 1
        assert sentences[0].text == text

    def test_sentence_positions(self, processor):
        """句子位置信息。"""
        text = "第一句。第二句。"
        sentences = processor.split_sentences(text)
        assert sentences[0].start_pos == 0
        assert sentences[0].end_pos == 4  # "第一句。" 长度 4
        assert sentences[1].start_pos == 4

    def test_split_with_newlines(self, processor):
        """换行符作为句子分隔。"""
        text = "第一行\n第二行"
        sentences = processor.split_sentences(text)
        assert len(sentences) == 2

    def test_sentence_cache(self, processor):
        """句子分割缓存。"""
        text = "测试缓存。"
        result1 = processor.split_sentences(text)
        result2 = processor.split_sentences(text)
        assert result1 is result2


# ===== 段落分割测试 =====


class TestSplitParagraphs:
    """段落分割测试。"""

    def test_split_paragraphs_basic(self, processor):
        """基本段落分割。"""
        text = "第一段第一句。第一段第二句。\n\n第二段第一句。"
        paragraphs = processor.split_paragraphs(text)
        assert len(paragraphs) == 2
        assert all(isinstance(p, Paragraph) for p in paragraphs)

    def test_split_paragraphs_empty(self, processor):
        """空文本段落分割。"""
        assert processor.split_paragraphs("") == []

    def test_split_paragraphs_single(self, processor):
        """单段落。"""
        text = "只有一个段落。"
        paragraphs = processor.split_paragraphs(text)
        assert len(paragraphs) == 1

    def test_split_paragraphs_with_sentences(self, processor):
        """段落应包含句子。"""
        text = "第一段句一。第一段句二。\n\n第二段句一。"
        paragraphs = processor.split_paragraphs(text)
        assert len(paragraphs[0].sentences) == 2
        assert len(paragraphs[1].sentences) == 1

    def test_split_paragraphs_multiple_newlines(self, processor):
        """多个换行符分割段落。"""
        text = "段落一\n\n\n\n段落二"
        paragraphs = processor.split_paragraphs(text)
        assert len(paragraphs) == 2


# ===== 相似度测试 =====


class TestSimilarity:
    """文本相似度测试。"""

    def test_cosine_similarity_identical(self, processor):
        """相同文本余弦相似度应为 1。"""
        text = "深度学习自然语言处理"
        sim = processor.cosine_similarity(text, text)
        assert sim == pytest.approx(1.0, abs=1e-6)

    def test_cosine_similarity_different(self, processor):
        """不同文本相似度应较低。"""
        text1 = "深度学习在自然语言处理中的应用"
        text2 = "区块链技术在金融领域的探索"
        sim = processor.cosine_similarity(text1, text2)
        assert 0 <= sim < 1

    def test_cosine_similarity_similar(self, processor):
        """相似文本相似度应高于不同文本。"""
        text1 = "深度学习在自然语言处理中的应用"
        text2 = "自然语言处理中深度学习的应用"
        text3 = "区块链技术在金融领域的探索"
        sim12 = processor.cosine_similarity(text1, text2)
        sim13 = processor.cosine_similarity(text1, text3)
        assert sim12 > sim13

    def test_cosine_similarity_empty(self, processor):
        """空文本相似度应为 0。"""
        assert processor.cosine_similarity("", "test") == 0.0
        assert processor.cosine_similarity("test", "") == 0.0

    def test_jaccard_similarity(self, processor):
        """Jaccard 相似度。"""
        text1 = "深度学习 自然语言处理"
        text2 = "深度学习 自然语言处理 应用"
        sim = processor.jaccard_similarity(text1, text2)
        assert 0 < sim <= 1

    def test_jaccard_identical(self, processor):
        """相同文本 Jaccard 为 1。"""
        text = "深度学习 自然语言处理"
        assert processor.jaccard_similarity(text, text) == pytest.approx(1.0)

    def test_jaccard_empty(self, processor):
        """空文本 Jaccard 为 0。"""
        assert processor.jaccard_similarity("", "test") == 0.0

    def test_edit_distance(self, processor):
        """编辑距离。"""
        assert processor.edit_distance("kitten", "sitting") == 3
        assert processor.edit_distance("", "abc") == 3
        assert processor.edit_distance("abc", "") == 3
        assert processor.edit_distance("abc", "abc") == 0

    def test_edit_distance_ratio(self, processor):
        """编辑距离相似度。"""
        ratio = processor.edit_distance_ratio("kitten", "sitting")
        assert 0 <= ratio <= 1
        # 相同字符串比率为 1
        assert processor.edit_distance_ratio("abc", "abc") == 1.0
        # 空字符串比率为 1
        assert processor.edit_distance_ratio("", "") == 1.0

    def test_ngram_similarity(self, processor):
        """N-gram 相似度。"""
        text1 = "深度学习"
        text2 = "深度学习应用"
        sim = processor.ngram_similarity(text1, text2, n=2)
        assert 0 < sim <= 1

    def test_ngram_similarity_identical(self, processor):
        """相同文本 N-gram 相似度为 1。"""
        text = "深度学习"
        assert processor.ngram_similarity(text, text, n=2) == pytest.approx(1.0)

    def test_ngram_similarity_empty(self, processor):
        """空文本 N-gram 相似度为 0。"""
        assert processor.ngram_similarity("", "test", n=2) == 0.0

    def test_hybrid_similarity(self, processor):
        """混合相似度。"""
        text1 = "深度学习在自然语言处理中的应用"
        text2 = "自然语言处理中深度学习的应用"
        sim = processor.hybrid_similarity(text1, text2)
        assert 0 <= sim <= 1

    def test_hybrid_similarity_custom_weights(self, processor):
        """自定义权重的混合相似度。"""
        text1 = "深度学习"
        text2 = "深度学习应用"
        sim = processor.hybrid_similarity(
            text1, text2, cosine_weight=0.6, jaccard_weight=0.2, edit_weight=0.2
        )
        assert 0 <= sim <= 1

    def test_hybrid_similarity_zero_weights(self, processor):
        """权重全为 0 时返回 0。"""
        sim = processor.hybrid_similarity("a", "b", cosine_weight=0, jaccard_weight=0, edit_weight=0)
        assert sim == 0.0


# ===== 关键词提取测试 =====


class TestKeywordExtraction:
    """关键词提取测试。"""

    def test_extract_keywords_tfidf(self, processor, sample_long_text):
        """TF-IDF 关键词提取。"""
        keywords = processor.extract_keywords_tfidf(sample_long_text, top_k=5)
        assert len(keywords) <= 5
        assert all(isinstance(k, Keyword) for k in keywords)
        # 分数应降序排列
        scores = [k.score for k in keywords]
        assert scores == sorted(scores, reverse=True)

    def test_extract_keywords_tfidf_empty(self, processor):
        """空文本 TF-IDF。"""
        assert processor.extract_keywords_tfidf("") == []

    def test_extract_keywords_tfidf_with_doc_freq(self, processor, sample_long_text):
        """带文档频率的 TF-IDF。"""
        doc_freq = {"深度学习": 5, "自然语言处理": 3}
        keywords = processor.extract_keywords_tfidf(
            sample_long_text, top_k=5, document_freq=doc_freq, total_docs=100
        )
        assert len(keywords) > 0

    def test_extract_keywords_textrank(self, processor, sample_long_text):
        """TextRank 关键词提取。"""
        keywords = processor.extract_keywords_textrank(sample_long_text, top_k=5)
        assert len(keywords) <= 5
        assert all(isinstance(k, Keyword) for k in keywords)

    def test_extract_keywords_textrank_short_text(self, processor):
        """短文本 TextRank。"""
        keywords = processor.extract_keywords_textrank("短文本", top_k=5)
        assert len(keywords) >= 1

    def test_extract_keywords_textrank_empty(self, processor):
        """空文本 TextRank。"""
        assert processor.extract_keywords_textrank("") == []

    def test_extract_keywords_unified_tfidf(self, processor, sample_long_text):
        """统一入口 tfidf 方法。"""
        keywords = processor.extract_keywords(sample_long_text, top_k=3, method="tfidf")
        assert len(keywords) <= 3

    def test_extract_keywords_unified_textrank(self, processor, sample_long_text):
        """统一入口 textrank 方法。"""
        keywords = processor.extract_keywords(sample_long_text, top_k=3, method="textrank")
        assert len(keywords) <= 3

    def test_extract_keywords_invalid_method(self, processor, sample_long_text):
        """无效方法应抛异常。"""
        with pytest.raises(ValueError):
            processor.extract_keywords(sample_long_text, method="invalid")

    def test_keyword_frequency(self, processor, sample_long_text):
        """关键词频率字段。"""
        keywords = processor.extract_keywords_tfidf(sample_long_text, top_k=5)
        for kw in keywords:
            assert kw.frequency >= 1


# ===== 摘要生成测试 =====


class TestSummary:
    """摘要生成测试。"""

    def test_generate_summary_textrank(self, processor, sample_long_text):
        """TextRank 摘要。"""
        summary = processor.generate_summary(sample_long_text, max_sentences=2, method="textrank")
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_generate_summary_frequency(self, processor, sample_long_text):
        """频率摘要。"""
        summary = processor.generate_summary(sample_long_text, max_sentences=2, method="frequency")
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_generate_summary_short_text(self, processor):
        """短文本摘要返回原文。"""
        text = "只有一句话。"
        summary = processor.generate_summary(text, max_sentences=3)
        assert summary == text.strip()

    def test_generate_summary_invalid_method(self, processor, sample_long_text):
        """无效方法应抛异常。"""
        with pytest.raises(ValueError):
            processor.generate_summary(sample_long_text, method="invalid")

    def test_generate_summary_empty(self, processor):
        """空文本摘要。"""
        summary = processor.generate_summary("", max_sentences=3)
        assert summary == ""


# ===== 文本分类测试 =====


class TestClassification:
    """文本分类测试。"""

    def test_classify_abstract(self, processor):
        """分类为摘要。"""
        text = "摘要：本文研究深度学习在自然语言处理中的应用。关键词：深度学习；NLP"
        result = processor.classify(text)
        assert result.category == "abstract"
        assert 0 <= result.confidence <= 1

    def test_classify_introduction(self, processor):
        """分类为引言。"""
        text = "引言\n深度学习是机器学习的一个重要分支。"
        result = processor.classify(text)
        assert result.category == "introduction"

    def test_classify_method(self, processor):
        """分类为方法。"""
        text = "方法\n我们使用 Transformer 模型进行实验。"
        result = processor.classify(text)
        assert result.category == "method"

    def test_classify_conclusion(self, processor):
        """分类为结论。"""
        text = "结论\n本文研究表明深度学习有效。"
        result = processor.classify(text)
        assert result.category == "conclusion"

    def test_classify_empty(self, processor):
        """空文本分类。"""
        result = processor.classify("")
        assert result.category == "unknown"
        assert result.confidence == 0.0

    def test_classify_other(self, processor):
        """无明确特征的文本分类为 other。"""
        text = "这是一段普通的文本内容。"
        result = processor.classify(text)
        assert result.category in ("other", "unknown")

    def test_classify_returns_labels(self, processor):
        """分类结果包含标签。"""
        text = "摘要\n本文研究深度学习。"
        result = processor.classify(text)
        assert isinstance(result.labels, list)
        assert isinstance(result.scores, dict)


# ===== 情感分析测试 =====


class TestSentiment:
    """情感分析测试。"""

    def test_sentiment_positive(self, processor):
        """正面情感。"""
        text = "这种方法取得了显著的成功，效果优秀。"
        result = processor.analyze_sentiment(text)
        assert result.sentiment == "positive"
        assert result.score > 0
        assert len(result.positive_words) > 0

    def test_sentiment_negative(self, processor):
        """负面情感。"""
        text = "这种方法存在严重缺陷，效果差，问题很多。"
        result = processor.analyze_sentiment(text)
        assert result.sentiment == "negative"
        assert result.score < 0
        assert len(result.negative_words) > 0

    def test_sentiment_neutral(self, processor):
        """中性情感。"""
        text = "本文介绍了一种方法。"
        result = processor.analyze_sentiment(text)
        assert result.sentiment == "neutral"
        assert result.score == 0.0

    def test_sentiment_empty(self, processor):
        """空文本情感。"""
        result = processor.analyze_sentiment("")
        assert result.sentiment == "neutral"
        assert result.score == 0.0

    def test_sentiment_score_range(self, processor, sample_long_text):
        """情感分数在 [-1, 1] 范围内。"""
        result = processor.analyze_sentiment(sample_long_text)
        assert -1 <= result.score <= 1


# ===== 语言检测测试 =====


class TestLanguageDetection:
    """语言检测测试。"""

    def test_detect_chinese(self, processor):
        """检测中文。"""
        assert processor.detect_language("你好世界，深度学习") == "zh"

    def test_detect_english(self, processor):
        """检测英文。"""
        assert processor.detect_language("Hello world deep learning") == "en"

    def test_detect_mixed(self, processor):
        """检测混合。"""
        assert processor.detect_language("你好 hello 世界 world") == "mixed"

    def test_detect_empty(self, processor):
        """空文本检测。"""
        assert processor.detect_language("") == "mixed"

    def test_detect_numbers_only(self, processor):
        """纯数字检测。"""
        assert processor.detect_language("12345") == "mixed"


# ===== 引用识别测试 =====


class TestCitationExtraction:
    """引用识别测试。"""

    def test_extract_bracket_citation(self, processor):
        """方括号引用。"""
        text = "深度学习[1]在 NLP 中应用。"
        citations = processor.extract_citations(text)
        assert len(citations) >= 1
        bracket_citations = [c for c in citations if c.citation_type == "bracket"]
        assert len(bracket_citations) >= 1
        assert bracket_citations[0].raw_text == "[1]"

    def test_extract_multiple_brackets(self, processor):
        """多方括号引用。"""
        text = "参见[1,2,3]和[4-6]的研究。"
        citations = processor.extract_citations(text)
        assert len(citations) >= 2

    def test_extract_parenthetical_citation(self, processor):
        """圆括号引用。"""
        text = "参见 (Smith, 2020) 的研究。"
        citations = processor.extract_citations(text)
        assert len(citations) >= 1

    def test_extract_chinese_citation(self, processor):
        """中文引用。"""
        text = "张三（2020）提出了该方法。"
        citations = processor.extract_citations(text)
        assert len(citations) >= 1
        chinese_citations = [c for c in citations if c.citation_type == "chinese"]
        assert len(chinese_citations) >= 1

    def test_extract_no_citation(self, processor):
        """无引用文本。"""
        text = "这是一段普通文本，没有引用。"
        citations = processor.extract_citations(text)
        assert len(citations) == 0

    def test_citations_sorted_by_position(self, processor):
        """引用按位置排序。"""
        text = "前[1]中[2]后[3]。"
        citations = processor.extract_citations(text)
        positions = [c.start_pos for c in citations]
        assert positions == sorted(positions)

    def test_remove_citations(self, processor):
        """移除引用。"""
        text = "深度学习[1]在 NLP[2]中应用。"
        cleaned = processor.remove_citations(text)
        assert "[1]" not in cleaned
        assert "[2]" not in cleaned

    def test_classify_citation_types(self, processor):
        """引用类型分类。"""
        assert processor._classify_citation("[1]") == "bracket"
        assert processor._classify_citation("(Smith, 2020)") == "parenthetical"
        assert processor._classify_citation("张三（2020）") == "chinese"


# ===== 公式识别测试 =====


class TestFormulaExtraction:
    """公式识别测试。"""

    def test_extract_inline_formula(self, processor):
        """行内公式。"""
        text = "公式 $x^2 + y^2 = r^2$ 表示圆。"
        formulas = processor.extract_formulas(text)
        assert len(formulas) >= 1
        assert any(f.formula_type == "inline" for f in formulas)

    def test_extract_block_formula(self, processor):
        """块级公式。"""
        text = "块级公式：$$\\int_0^1 x dx$$"
        formulas = processor.extract_formulas(text)
        assert len(formulas) >= 1
        assert any(f.formula_type == "block" for f in formulas)

    def test_extract_math_function(self, processor):
        """数学函数。"""
        text = "使用 sin(x) 和 cos(x) 计算。"
        formulas = processor.extract_formulas(text)
        assert len(formulas) >= 1

    def test_extract_no_formula(self, processor):
        """无公式文本。"""
        text = "这是一段普通文本。"
        formulas = processor.extract_formulas(text)
        assert len(formulas) == 0

    def test_remove_formulas(self, processor):
        """移除公式。"""
        text = "公式 $x^2$ 与 $$y^2$$。"
        cleaned = processor.remove_formulas(text)
        assert "$x^2$" not in cleaned
        assert "$$y^2$$" not in cleaned

    def test_clean_academic_text(self, processor):
        """清理学术文本。"""
        text = "深度学习[1]在 NLP 中应用。公式 $x$ 表示变量。"
        cleaned = processor.clean_academic_text(text)
        assert "[1]" not in cleaned
        assert "$x$" not in cleaned


# ===== SimHash 与去重测试 =====


class TestSimHashAndDedup:
    """SimHash 与去重测试。"""

    def test_compute_text_hash(self, processor):
        """文本哈希。"""
        hash1 = processor.compute_text_hash("测试文本")
        hash2 = processor.compute_text_hash("测试文本")
        hash3 = processor.compute_text_hash("不同文本")
        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 32  # MD5 长度

    def test_compute_simhash(self, processor):
        """SimHash 计算。"""
        h = processor.compute_simhash("深度学习自然语言处理")
        assert isinstance(h, str)
        assert len(h) > 0

    def test_compute_simhash_empty(self, processor):
        """空文本 SimHash。"""
        h = processor.compute_simhash("")
        assert h == "0" * 16  # 64 位默认

    def test_compute_simhash_custom_bits(self, processor):
        """自定义位数 SimHash。"""
        h = processor.compute_simhash("测试", hash_bits=128)
        assert len(h) == 32  # 128 / 4

    def test_hamming_distance_identical(self, processor):
        """相同哈希汉明距离为 0。"""
        h = processor.compute_simhash("测试文本")
        assert processor.hamming_distance(h, h) == 0

    def test_hamming_distance_different(self, processor):
        """不同哈希汉明距离 > 0。"""
        h1 = processor.compute_simhash("深度学习")
        h2 = processor.compute_simhash("区块链技术")
        dist = processor.hamming_distance(h1, h2)
        assert dist > 0

    def test_hamming_distance_invalid(self, processor):
        """无效哈希返回 -1。"""
        assert processor.hamming_distance("invalid", "test") == -1

    def test_is_duplicate_true(self, processor):
        """重复文本检测。"""
        text1 = "深度学习在自然语言处理中的应用研究"
        text2 = "深度学习在自然语言处理中的应用研究（扩展版）"
        assert processor.is_duplicate(text1, text2, threshold=0.5) is True

    def test_is_duplicate_false(self, processor):
        """非重复文本检测。"""
        text1 = "深度学习在自然语言处理中的应用"
        text2 = "区块链技术在金融领域的探索"
        assert processor.is_duplicate(text1, text2, threshold=0.8) is False

    def test_is_duplicate_methods(self, processor):
        """不同方法的重复检测。"""
        text1 = "深度学习自然语言处理"
        text2 = "深度学习自然语言处理应用"
        for method in ("cosine", "jaccard", "edit", "ngram", "hybrid"):
            result = processor.is_duplicate(text1, text2, threshold=0.3, method=method)
            assert isinstance(result, bool)

    def test_find_duplicates(self, processor):
        """查找重复对。"""
        texts = [
            "深度学习在自然语言处理中的应用",
            "深度学习在自然语言处理中的应用研究",
            "区块链技术在金融领域的探索",
            "区块链技术在金融领域的应用",
        ]
        duplicates = processor.find_duplicates(texts, threshold=0.5)
        assert isinstance(duplicates, list)
        # 应找到至少一对重复
        assert len(duplicates) >= 1
        for dup in duplicates:
            assert len(dup) == 3  # (i, j, similarity)
            assert dup[0] < dup[1]


# ===== 文本统计测试 =====


class TestTextStats:
    """文本统计测试。"""

    def test_get_text_stats_basic(self, processor, sample_long_text):
        """基本文本统计。"""
        stats = processor.get_text_stats(sample_long_text)
        assert stats["char_count"] > 0
        assert stats["word_count"] > 0
        assert stats["sentence_count"] > 0
        assert stats["chinese_char_count"] > 0

    def test_get_text_stats_empty(self, processor):
        """空文本统计。"""
        stats = processor.get_text_stats("")
        assert stats["char_count"] == 0
        assert stats["word_count"] == 0
        assert stats["sentence_count"] == 0

    def test_get_text_stats_with_citations(self, processor):
        """带引用的文本统计。"""
        text = "深度学习[1]在 NLP[2]中应用。"
        stats = processor.get_text_stats(text)
        assert stats["citation_count"] >= 2

    def test_get_text_stats_with_formulas(self, processor):
        """带公式的文本统计。"""
        text = "公式 $x^2$ 与 $y^2$。"
        stats = processor.get_text_stats(text)
        assert stats["formula_count"] >= 2

    def test_get_text_stats_paragraphs(self, processor):
        """段落统计。"""
        text = "第一段。\n\n第二段。\n\n第三段。"
        stats = processor.get_text_stats(text)
        assert stats["paragraph_count"] == 3


# ===== 章节识别测试 =====


class TestSectionExtraction:
    """章节识别测试。"""

    def test_extract_section_headers(self, processor):
        """识别章节标题。"""
        text = "摘要\n本文研究。\n\n引言\n背景介绍。"
        headers = processor.extract_section_headers(text)
        assert "摘要" in headers
        assert "引言" in headers

    def test_extract_section_headers_english(self, processor):
        """识别英文章节标题。"""
        text = "Introduction\nBackground.\n\nMethods\nWe use CNN."
        headers = processor.extract_section_headers(text)
        assert "Introduction" in headers
        assert "Methods" in headers

    def test_extract_section_headers_none(self, processor):
        """无章节标题。"""
        text = "这是一段普通文本，没有章节标题。"
        headers = processor.extract_section_headers(text)
        assert len(headers) == 0

    def test_split_by_sections(self, processor):
        """按章节分割文本。"""
        text = (
            "摘要\n本文研究深度学习。\n\n"
            "引言\n深度学习是机器学习分支。\n\n"
            "方法\n我们使用 Transformer 模型。"
        )
        sections = processor.split_by_sections(text)
        assert "摘要" in sections
        assert "引言" in sections
        assert "方法" in sections
        assert "深度学习" in sections["摘要"]
        assert "Transformer" in sections["方法"]

    def test_split_by_sections_with_preamble(self, processor):
        """带前言的章节分割。"""
        text = "前言内容。\n\n摘要\n正文。"
        sections = processor.split_by_sections(text)
        assert "preamble" in sections
        assert "摘要" in sections


# ===== 缓存管理测试 =====


class TestCache:
    """缓存管理测试。"""

    def test_clear_cache(self, processor, sample_chinese_text):
        """清空缓存。"""
        processor.tokenize(sample_chinese_text)
        assert len(processor._token_cache) > 0
        processor.clear_cache()
        assert len(processor._token_cache) == 0
        assert len(processor._sentence_cache) == 0

    def test_cache_lru_eviction(self, processor):
        """缓存 LRU 淘汰。"""
        processor._max_cache_size = 5
        for i in range(10):
            processor.tokenize(f"测试文本{i}")
        # 缓存大小不应超过 max_size
        assert len(processor._token_cache) <= processor._max_cache_size


# ===== 模块级便捷函数测试 =====


class TestModuleLevelFunctions:
    """模块级便捷函数测试。"""

    def test_get_text_processor_singleton(self):
        """get_text_processor 单例。"""
        p1 = get_text_processor()
        p2 = get_text_processor()
        assert p1 is p2

    def test_tokenize_function(self):
        """tokenize 便捷函数。"""
        words = tokenize("深度学习 测试")
        assert isinstance(words, list)

    def test_extract_keywords_function(self, sample_long_text):
        """extract_keywords 便捷函数。"""
        keywords = extract_keywords(sample_long_text, top_k=3)
        assert isinstance(keywords, list)
        assert len(keywords) <= 3

    def test_compute_similarity_function(self):
        """compute_similarity 便捷函数。"""
        sim = compute_similarity("深度学习", "深度学习", method="cosine")
        assert sim == pytest.approx(1.0)

    def test_summarize_function(self, sample_long_text):
        """summarize 便捷函数。"""
        summary = summarize(sample_long_text, max_sentences=2)
        assert isinstance(summary, str)
        assert len(summary) > 0


# ===== 工具方法测试 =====


class TestUtilityMethods:
    """工具方法测试。"""

    def test_normalize(self, processor):
        """文本规范化。"""
        result = processor._normalize("ＡＢＣ")
        assert result == "ABC"

    def test_normalize_empty(self, processor):
        """空文本规范化。"""
        assert processor._normalize("") == ""

    def test_is_punctuation_chinese(self, processor):
        """中文标点判断。"""
        for p in "，。！？；：":
            assert processor._is_punctuation(p) is True

    def test_is_punctuation_english(self, processor):
        """英文标点判断。"""
        for p in ",.!?;:":
            assert processor._is_punctuation(p) is True

    def test_is_punctuation_non_punctuation(self, processor):
        """非标点判断。"""
        assert processor._is_punctuation("a") is False
        assert processor._is_punctuation("中") is False
        assert processor._is_punctuation("1") is False

    def test_is_punctuation_empty(self, processor):
        """空字符串标点判断。"""
        assert processor._is_punctuation("") is False

    def test_get_ngrams(self, processor):
        """N-gram 生成。"""
        ngrams = processor._get_ngrams("abcd", 2)
        assert "ab" in ngrams
        assert "bc" in ngrams
        assert "cd" in ngrams

    def test_get_ngrams_short_text(self, processor):
        """短文本 N-gram。"""
        ngrams = processor._get_ngrams("a", 2)
        assert len(ngrams) == 0

    def test_header_to_category(self, processor):
        """标题到分类映射。"""
        assert processor._header_to_category("摘要") == "abstract"
        assert processor._header_to_category("引言") == "introduction"
        assert processor._header_to_category("方法") == "method"
        assert processor._header_to_category("结论") == "conclusion"
        assert processor._header_to_category("参考文献") == "reference"


# ===== 自定义停用词测试 =====


class TestCustomStopwords:
    """自定义停用词测试。"""

    def test_custom_stopwords_added(self):
        """自定义停用词被添加。"""
        custom = {"自定义词", "customword"}
        p = TextProcessor(custom_stopwords=custom)
        assert "自定义词" in p._stopwords
        assert "customword" in p._stopwords
        # 默认停用词仍存在
        assert "的" in p._stopwords
        assert "the" in p._stopwords

    def test_custom_stopwords_filtering(self):
        """自定义停用词过滤。"""
        custom = {"过滤词"}
        p = TextProcessor(custom_stopwords=custom)
        result = p.tokenize("过滤词 深度学习", remove_stopwords=True)
        assert "过滤词" not in result.tokens


# ===== 综合场景测试 =====


class TestIntegrationScenarios:
    """综合场景测试。"""

    def test_full_processing_pipeline(self, processor, sample_long_text):
        """完整处理流水线。"""
        # 1. 清理文本
        cleaned = processor.clean_academic_text(sample_long_text)
        assert len(cleaned) > 0
        # 2. 分词
        tokens = processor.tokenize(cleaned)
        assert tokens.token_count > 0
        # 3. 关键词提取
        keywords = processor.extract_keywords_tfidf(cleaned, top_k=5)
        assert len(keywords) > 0
        # 4. 摘要
        summary = processor.generate_summary(cleaned, max_sentences=2)
        assert len(summary) > 0
        # 5. 统计
        stats = processor.get_text_stats(cleaned)
        assert stats["char_count"] > 0

    def test_similarity_comparison(self, processor):
        """相似度比较场景。"""
        base = "深度学习在自然语言处理中的应用研究"
        similar = "深度学习在自然语言处理中的应用研究（扩展版）"
        different = "区块链技术在金融领域的探索"
        sim_similar = processor.hybrid_similarity(base, similar)
        sim_different = processor.hybrid_similarity(base, different)
        assert sim_similar > sim_different

    def test_dedup_workflow(self, processor):
        """去重工作流。"""
        texts = [
            "深度学习在自然语言处理中的应用",
            "深度学习在自然语言处理中的应用研究",
            "区块链技术在金融领域的探索",
        ]
        # 计算所有两两相似度
        duplicates = processor.find_duplicates(texts, threshold=0.3)
        # 前两个文本应被判为重复
        assert any(d[0] == 0 and d[1] == 1 for d in duplicates)

    def test_academic_text_processing(self, processor):
        """学术文本处理。"""
        text = (
            "摘要\n"
            "本文研究深度学习[1]在自然语言处理中的应用。"
            "Smith 等（2020）提出了 Transformer 架构。"
            "公式 $E=mc^2$ 表示质能方程。"
        )
        # 提取引用
        citations = processor.extract_citations(text)
        assert len(citations) >= 2
        # 提取公式
        formulas = processor.extract_formulas(text)
        assert len(formulas) >= 1
        # 清理
        cleaned = processor.clean_academic_text(text)
        assert "[1]" not in cleaned
        assert "$E=mc^2$" not in cleaned
        # 章节分割
        sections = processor.split_by_sections(text)
        assert "摘要" in sections


# ===== 线程安全测试 =====


class TestThreadSafety:
    """线程安全测试。"""

    def test_concurrent_tokenize(self, processor):
        """多线程并发分词。"""
        texts = [f"测试文本{i}深度学习" for i in range(20)]
        results = [None] * len(texts)

        def worker(idx):
            results[idx] = processor.tokenize(texts[idx])

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(texts))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 所有结果应非空
        assert all(r is not None for r in results)
        assert all(r.token_count > 0 for r in results)

    def test_concurrent_similarity(self, processor):
        """多线程并发相似度计算。"""
        text1 = "深度学习自然语言处理"
        text2 = "深度学习自然语言处理应用"
        results = []

        def worker():
            results.append(processor.cosine_similarity(text1, text2))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 所有结果应一致
        assert all(r == results[0] for r in results)
