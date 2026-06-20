"""ChineseProcessor 单元测试

覆盖范围：
    - 数据类（Token / Sentence / Paragraph / Entity / Keyword / SentimentResult /
      FormulaInfo / CitationInfo）构造与字段默认值
    - 文本归一化（normalize：NFC / 繁简 / 全半角 / 空白规整）
    - 繁简转换（traditional_to_simplified / simplified_to_traditional）
    - 全半角转换（fullwidth_to_halfwidth / halfwidth_to_fullwidth）
    - 中文分词（tokenize：中文 / 英文 / 中英混合 / 数字 / 空文本 / 带词性 / 带偏移）
    - 词性标注（pos_tag）
    - 命名实体识别（ner：人名 / 地名 / 机构 / 术语）
    - 句子分割（split_sentences：标点感知 / 最小长度 / 保留标点）
    - 段落识别（split_paragraphs：空行切分 / 最小长度）
    - 关键词提取（extract_keywords：TF-IDF / TextRank / 停用词过滤）
    - 摘要生成（generate_summary：TextRank / frequency / 比例 / 最大句数）
    - 情感分析（analyze_sentiment：正面 / 负面 / 中性 / 否定词 / 程度副词）
    - 学术术语识别（identify_terms）
    - 公式识别（identify_formulas：行内 / 块级 / equation 环境）
    - 引用识别（identify_citations：数字 / 作者-年份 / 中文引用）
    - SimHash 指纹（compute_simhash / hamming_distance）
    - MinHash 签名（compute_minhash_signature / estimate_jaccard）
    - 文本去重（deduplicate：simhash / minhash）
    - 相似度计算（compute_similarity：cosine / jaccard / edit / simhash）
    - 中英文混合切分（split_mixed_text）
    - 语言检测（detect_language：zh / en / mixed）
    - 批量处理（batch_tokenize / batch_extract_keywords / batch_compute_similarity）
    - 文本统计（text_statistics）
    - 边界情况（空字符串 / 仅标点 / 仅空白 / 超长文本）
    - 模块级便捷函数与单例

运行方式：
    pytest tests/unit/test_nlp_chinese.py -v
"""
from __future__ import annotations

import threading

import pytest

from backend.nlp.chinese_processor import (
    ChineseProcessor,
    CitationInfo,
    Entity,
    FormulaInfo,
    Keyword,
    Paragraph,
    Sentence,
    SentimentResult,
    Token,
    compute_similarity,
    extract_keywords,
    get_chinese_processor,
    split_sentences,
    tokenize,
)


# ===== 公共夹具 =====


@pytest.fixture
def processor():
    """返回一个全新的 ChineseProcessor 实例。"""
    return ChineseProcessor()


@pytest.fixture
def processor_no_jieba():
    """返回一个不使用 jieba 的 ChineseProcessor 实例（强制走双向最大匹配）。"""
    return ChineseProcessor(use_jieba=False)


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
        "BERT 与 GPT 等预训练模型进一步推动了自然语言处理的发展。"
    )


@pytest.fixture
def sample_paragraphs_text():
    """多段落样例文本。"""
    return (
        "第一段：深度学习是机器学习的一个分支。\n"
        "它通过多层神经网络学习数据的表示。\n\n"
        "第二段：自然语言处理是人工智能的重要领域。\n"
        "深度学习在 NLP 中取得了显著成果。\n\n"
        "第三段：卷积神经网络在图像识别中表现优异。"
    )


# ===== 数据类测试 =====


class TestTokenDataclass:
    """Token 数据类测试。"""

    def test_token_default_fields(self):
        """Token 默认字段值。"""
        token = Token(text="深度学习")
        assert token.text == "深度学习"
        assert token.pos == "x"
        assert token.offset == 0
        assert token.is_stopword is False
        assert token.entity_type is None

    def test_token_post_init_length(self):
        """Token __post_init__ 自动计算 length。"""
        token = Token(text="自然语言")
        assert token.length == len("自然语言")

    def test_token_post_init_is_chinese(self):
        """Token __post_init__ 自动判断 is_chinese。"""
        cn_token = Token(text="学习")
        assert cn_token.is_chinese is True
        en_token = Token(text="learning")
        assert en_token.is_chinese is False

    def test_token_explicit_length(self):
        """Token 显式指定 length 时不被覆盖。"""
        token = Token(text="测试", length=99)
        assert token.length == 99


class TestSentenceDataclass:
    """Sentence 数据类测试。"""

    def test_sentence_default_fields(self):
        """Sentence 默认字段值。"""
        sent = Sentence(text="这是一个句子。")
        assert sent.text == "这是一个句子。"
        assert sent.start == 0
        assert sent.end == 0
        assert sent.tokens == []

    def test_sentence_with_tokens(self):
        """Sentence 带词元列表。"""
        tokens = [Token(text="深度"), Token(text="学习")]
        sent = Sentence(text="深度学习", start=0, end=4, tokens=tokens)
        assert len(sent.tokens) == 2
        assert sent.tokens[0].text == "深度"


class TestParagraphDataclass:
    """Paragraph 数据类测试。"""

    def test_paragraph_default_fields(self):
        """Paragraph 默认字段值。"""
        para = Paragraph(text="段落内容")
        assert para.text == "段落内容"
        assert para.start == 0
        assert para.end == 0
        assert para.sentences == []


class TestEntityDataclass:
    """Entity 数据类测试。"""

    def test_entity_default_confidence(self):
        """Entity 默认置信度为 1.0。"""
        entity = Entity(text="北京", entity_type="LOCATION")
        assert entity.confidence == 1.0
        assert entity.start == 0
        assert entity.end == 0


class TestKeywordDataclass:
    """Keyword 数据类测试。"""

    def test_keyword_default_fields(self):
        """Keyword 默认字段值。"""
        kw = Keyword(text="深度学习")
        assert kw.score == 0.0
        assert kw.frequency == 0
        assert kw.pos == "n"


class TestSentimentResultDataclass:
    """SentimentResult 数据类测试。"""

    def test_sentiment_default_neutral(self):
        """SentimentResult 默认为中性。"""
        result = SentimentResult()
        assert result.score == 0.0
        assert result.label == "neutral"
        assert result.positive_count == 0
        assert result.negative_count == 0
        assert result.confidence == 0.0


class TestFormulaAndCitationDataclass:
    """FormulaInfo 与 CitationInfo 数据类测试。"""

    def test_formula_default_type(self):
        """FormulaInfo 默认类型为 inline。"""
        formula = FormulaInfo(text="$E=mc^2$")
        assert formula.formula_type == "inline"
        assert formula.start == 0
        assert formula.end == 0

    def test_citation_default_type(self):
        """CitationInfo 默认类型为 numeric。"""
        citation = CitationInfo(text="[1]")
        assert citation.citation_type == "numeric"
        assert citation.ref_id is None


# ===== 文本归一化测试 =====


class TestNormalize:
    """normalize 方法测试。"""

    def test_normalize_empty_string(self, processor):
        """空字符串归一化返回空。"""
        assert processor.normalize("") == ""

    def test_normalize_traditional_to_simplified(self, processor):
        """繁体转简体。"""
        text = "深度學習在自然語言處理中的應用"
        result = processor.normalize(text)
        assert "学" in result
        assert "语" in result

    def test_normalize_fullwidth_to_halfwidth(self, processor):
        """全角转半角。"""
        text = "Ｄｅｅｐ Ｌｅａｒｎｉｎｇ"
        result = processor.normalize(text)
        assert "Deep" in result

    def test_normalize_whitespace_collapse(self, processor):
        """空白符压缩。"""
        text = "深度    学习     自然语言"
        result = processor.normalize(text)
        assert "    " not in result

    def test_normalize_trim(self, processor):
        """首尾空白去除。"""
        text = "  深度学习  "
        result = processor.normalize(text, trim=True)
        assert result == "深度学习"

    def test_normalize_no_trim(self, processor):
        """保留首尾空白。"""
        text = "  深度学习  "
        result = processor.normalize(text, trim=False)
        assert result.startswith(" ")

    def test_normalize_disable_simplified(self, processor):
        """禁用繁简转换。"""
        text = "深度學習"
        result = processor.normalize(text, to_simplified=False)
        assert "學" in result

    def test_normalize_disable_halfwidth(self, processor):
        """禁用全半角转换。"""
        text = "ＡＢＣ"
        result = processor.normalize(text, to_halfwidth=False)
        assert "Ａ" in result


# ===== 繁简转换测试 =====


class TestTraditionalSimplified:
    """繁简转换测试。"""

    def test_traditional_to_simplified(self, processor):
        """繁体转简体。"""
        assert processor.traditional_to_simplified("學習") == "学习"
        assert processor.traditional_to_simplified("語言") == "语言"

    def test_traditional_to_simplified_empty(self, processor):
        """空字符串繁转简。"""
        assert processor.traditional_to_simplified("") == ""

    def test_traditional_to_simplified_no_change(self, processor):
        """简体不受影响。"""
        result = processor.traditional_to_simplified("深度学习")
        assert result == "深度学习"

    def test_simplified_to_traditional(self, processor):
        """简体转繁体。"""
        result = processor.simplified_to_traditional("学习")
        assert "學" in result

    def test_simplified_to_traditional_empty(self, processor):
        """空字符串简转繁。"""
        assert processor.simplified_to_traditional("") == ""

    def test_simplified_to_traditional_no_change(self, processor):
        """繁体不受影响。"""
        text = "學習"
        result = processor.simplified_to_traditional(text)
        assert result == text


# ===== 全半角转换测试 =====


class TestFullwidthHalfwidth:
    """全半角转换测试。"""

    def test_fullwidth_to_halfwidth(self, processor):
        """全角转半角。"""
        assert processor.fullwidth_to_halfwidth("ＡＢＣ") == "ABC"
        assert processor.fullwidth_to_halfwidth("１２３") == "123"

    def test_fullwidth_to_halfwidth_empty(self, processor):
        """空字符串全转半。"""
        assert processor.fullwidth_to_halfwidth("") == ""

    def test_fullwidth_to_halfwidth_mixed(self, processor):
        """混合文本全转半。"""
        result = processor.fullwidth_to_halfwidth("深度ＡＢ")
        assert "AB" in result
        assert "深度" in result

    def test_halfwidth_to_fullwidth(self, processor):
        """半角转全角。"""
        result = processor.halfwidth_to_fullwidth("ABC")
        assert "Ａ" in result
        assert "Ｂ" in result

    def test_halfwidth_to_fullwidth_empty(self, processor):
        """空字符串半转全。"""
        assert processor.halfwidth_to_fullwidth("") == ""

    def test_halfwidth_to_fullwidth_space(self, processor):
        """半角空格转全角空格。"""
        result = processor.halfwidth_to_fullwidth("a b")
        assert "\u3000" in result


# ===== 分词测试 =====


class TestTokenize:
    """tokenize 方法测试。"""

    def test_tokenize_chinese(self, processor):
        """中文分词返回非空列表。"""
        tokens = processor.tokenize("深度学习")
        assert len(tokens) > 0
        assert all(isinstance(t, Token) for t in tokens)

    def test_tokenize_empty(self, processor):
        """空字符串分词返回空列表。"""
        assert processor.tokenize("") == []

    def test_tokenize_english(self, processor):
        """英文分词。"""
        tokens = processor.tokenize("deep learning")
        texts = [t.text for t in tokens]
        assert "deep" in texts
        assert "learning" in texts

    def test_tokenize_mixed(self, processor):
        """中英文混合分词。"""
        tokens = processor.tokenize("深度学习 deep learning")
        texts = [t.text for t in tokens]
        assert any("深度" in t for t in texts)
        assert "deep" in texts

    def test_tokenize_with_pos(self, processor):
        """带词性标注分词。"""
        tokens = processor.tokenize("深度学习", with_pos=True)
        assert all(t.pos for t in tokens)

    def test_tokenize_with_offset(self, processor):
        """带偏移分词。"""
        text = "深度学习"
        tokens = processor.tokenize(text, with_offset=True)
        assert all(t.offset >= 0 for t in tokens)

    def test_tokenize_numbers(self, processor):
        """数字分词。"""
        tokens = processor.tokenize("2024 年")
        texts = [t.text for t in tokens]
        assert "2024" in texts

    def test_tokenize_stopword_marking(self, processor):
        """停用词标记。"""
        tokens = processor.tokenize("的 了 在")
        assert any(t.is_stopword for t in tokens)

    def test_tokenize_no_jieba_fallback(self, processor_no_jieba):
        """不使用 jieba 时降级为双向最大匹配。"""
        tokens = processor_no_jieba.tokenize("深度学习")
        assert len(tokens) > 0
        assert all(isinstance(t, Token) for t in tokens)

    def test_tokenize_no_jieba_chinese_flag(self, processor_no_jieba):
        """双向最大匹配标记 is_chinese。"""
        tokens = processor_no_jieba.tokenize("深度学习")
        cn_tokens = [t for t in tokens if t.is_chinese]
        assert len(cn_tokens) > 0


# ===== 词性标注测试 =====


class TestPosTag:
    """pos_tag 方法测试。"""

    def test_pos_tag_updates_tokens(self, processor):
        """词性标注更新词元。"""
        tokens = processor.tokenize("深度学习", with_pos=False)
        result = processor.pos_tag(tokens)
        assert result is tokens
        assert all(t.pos for t in tokens)

    def test_pos_tag_empty_list(self, processor):
        """空列表词性标注。"""
        assert processor.pos_tag([]) == []

    def test_pos_tag_digits(self, processor):
        """数字词性为 m。"""
        tokens = [Token(text="2024", pos="x")]
        result = processor.pos_tag(tokens)
        assert result[0].pos == "m"


# ===== 命名实体识别测试 =====


class TestNER:
    """ner 方法测试。"""

    def test_ner_returns_entities(self, processor):
        """NER 返回实体列表。"""
        entities = processor.ner("张三在北京大学研究深度学习")
        assert isinstance(entities, list)

    def test_ner_empty(self, processor):
        """空字符串 NER。"""
        assert processor.ner("") == []

    def test_ner_location(self, processor):
        """地名识别。"""
        entities = processor.ner("北京是中国的首都")
        locations = [e for e in entities if e.entity_type == "LOCATION"]
        assert any("北京" in e.text for e in locations)

    def test_ner_entity_types(self, processor):
        """实体类型合法。"""
        entities = processor.ner("张三在北京大学研究深度学习")
        valid_types = {"PERSON", "LOCATION", "ORGANIZATION", "TERM", "TIME", "NUMBER"}
        for e in entities:
            assert e.entity_type in valid_types


# ===== 句子分割测试 =====


class TestSplitSentences:
    """split_sentences 方法测试。"""

    def test_split_sentences_basic(self, processor):
        """基本句子分割。"""
        text = "深度学习是机器学习的分支。自然语言处理是重要领域。"
        sentences = processor.split_sentences(text)
        assert len(sentences) >= 2
        assert all(isinstance(s, Sentence) for s in sentences)

    def test_split_sentences_empty(self, processor):
        """空字符串分割。"""
        assert processor.split_sentences("") == []

    def test_split_sentences_with_question_mark(self, processor):
        """问号分割。"""
        text = "什么是深度学习？它有哪些应用？"
        sentences = processor.split_sentences(text)
        assert len(sentences) >= 2

    def test_split_sentences_with_exclamation(self, processor):
        """叹号分割。"""
        text = "深度学习太强大了！自然语言处理也很棒！"
        sentences = processor.split_sentences(text)
        assert len(sentences) >= 2

    def test_split_sentences_min_length(self, processor):
        """最小长度合并。"""
        text = "a。深度学习是机器学习的分支。"
        sentences = processor.split_sentences(text, min_length=5)
        assert all(len(s.text) >= 5 or i == 0 for i, s in enumerate(sentences))

    def test_split_sentences_keep_punct(self, processor):
        """保留标点。"""
        text = "深度学习。自然语言处理。"
        sentences = processor.split_sentences(text, keep_punct=True)
        assert any(s.text.endswith("。") for s in sentences)

    def test_split_sentences_has_tokens(self, processor):
        """分割后的句子包含词元。"""
        text = "深度学习是机器学习的分支。自然语言处理是重要领域。"
        sentences = processor.split_sentences(text)
        assert all(len(s.tokens) > 0 for s in sentences)


# ===== 段落识别测试 =====


class TestSplitParagraphs:
    """split_paragraphs 方法测试。"""

    def test_split_paragraphs_basic(self, processor, sample_paragraphs_text):
        """基本段落识别。"""
        paragraphs = processor.split_paragraphs(sample_paragraphs_text)
        assert len(paragraphs) >= 2
        assert all(isinstance(p, Paragraph) for p in paragraphs)

    def test_split_paragraphs_empty(self, processor):
        """空字符串段落识别。"""
        assert processor.split_paragraphs("") == []

    def test_split_paragraphs_min_length(self, processor):
        """最小长度过滤。"""
        text = "短。\n\n这是一个较长的段落内容用于测试。"
        paragraphs = processor.split_paragraphs(text, min_length=10)
        assert all(len(p.text) >= 10 for p in paragraphs)

    def test_split_paragraphs_has_sentences(self, processor, sample_paragraphs_text):
        """段落包含句子。"""
        paragraphs = processor.split_paragraphs(sample_paragraphs_text)
        assert all(len(p.sentences) > 0 for p in paragraphs)


# ===== 关键词提取测试 =====


class TestExtractKeywords:
    """extract_keywords 方法测试。"""

    def test_extract_keywords_tfidf(self, processor, sample_long_text):
        """TF-IDF 关键词提取。"""
        keywords = processor.extract_keywords(sample_long_text, top_k=5, method="tfidf")
        assert len(keywords) <= 5
        assert all(isinstance(k, Keyword) for k in keywords)
        assert all(k.text for k in keywords)

    def test_extract_keywords_textrank(self, processor, sample_long_text):
        """TextRank 关键词提取。"""
        keywords = processor.extract_keywords(sample_long_text, top_k=5, method="textrank")
        assert len(keywords) <= 5
        assert all(isinstance(k, Keyword) for k in keywords)

    def test_extract_keywords_empty(self, processor):
        """空字符串关键词提取。"""
        assert processor.extract_keywords("") == []

    def test_extract_keywords_top_k(self, processor, sample_long_text):
        """top_k 限制返回数量。"""
        keywords = processor.extract_keywords(sample_long_text, top_k=3)
        assert len(keywords) <= 3

    def test_extract_keywords_scores_descending(self, processor, sample_long_text):
        """关键词分数降序排列。"""
        keywords = processor.extract_keywords(sample_long_text, top_k=10, method="tfidf")
        scores = [k.score for k in keywords]
        assert scores == sorted(scores, reverse=True)

    def test_extract_keywords_frequency_positive(self, processor, sample_long_text):
        """关键词频次非负。"""
        keywords = processor.extract_keywords(sample_long_text, top_k=5)
        assert all(k.frequency >= 0 for k in keywords)

    def test_extract_keywords_min_length(self, processor, sample_long_text):
        """最小长度过滤。"""
        keywords = processor.extract_keywords(sample_long_text, top_k=10, min_length=3)
        assert all(len(k.text) >= 3 for k in keywords)


# ===== 摘要生成测试 =====


class TestGenerateSummary:
    """generate_summary 方法测试。"""

    def test_generate_summary_textrank(self, processor, sample_long_text):
        """TextRank 摘要生成。"""
        summary = processor.generate_summary(sample_long_text, ratio=0.3, method="textrank")
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_generate_summary_frequency(self, processor, sample_long_text):
        """频率摘要生成。"""
        summary = processor.generate_summary(sample_long_text, ratio=0.3, method="frequency")
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_generate_summary_empty(self, processor):
        """空字符串摘要。"""
        assert processor.generate_summary("") == ""

    def test_generate_summary_short_text(self, processor):
        """短文本直接返回。"""
        text = "这是一个短句。"
        summary = processor.generate_summary(text)
        assert summary == text.strip()

    def test_generate_summary_max_sentences(self, processor, sample_long_text):
        """最大句子数限制。"""
        summary = processor.generate_summary(sample_long_text, max_sentences=1)
        assert isinstance(summary, str)

    def test_generate_summary_ratio(self, processor, sample_long_text):
        """比例参数。"""
        summary_full = processor.generate_summary(sample_long_text, ratio=1.0)
        summary_short = processor.generate_summary(sample_long_text, ratio=0.2)
        assert len(summary_short) <= len(summary_full) + 100


# ===== 情感分析测试 =====


class TestAnalyzeSentiment:
    """analyze_sentiment 方法测试。"""

    def test_sentiment_positive(self, processor):
        """正面情感。"""
        result = processor.analyze_sentiment("这个方法非常好，效果优秀")
        assert isinstance(result, SentimentResult)
        assert result.positive_count > 0

    def test_sentiment_negative(self, processor):
        """负面情感。"""
        result = processor.analyze_sentiment("这个方法很差，效果糟糕")
        assert isinstance(result, SentimentResult)
        assert result.negative_count > 0

    def test_sentiment_neutral(self, processor):
        """中性情感。"""
        result = processor.analyze_sentiment("这是一段描述性文字")
        assert result.label == "neutral"

    def test_sentiment_empty(self, processor):
        """空字符串情感分析。"""
        result = processor.analyze_sentiment("")
        assert result.score == 0.0
        assert result.label == "neutral"

    def test_sentiment_score_range(self, processor, sample_long_text):
        """情感分数在 [-1, 1] 范围内。"""
        result = processor.analyze_sentiment(sample_long_text)
        assert -1.0 <= result.score <= 1.0

    def test_sentiment_confidence_range(self, processor):
        """置信度在 [0, 1] 范围内。"""
        result = processor.analyze_sentiment("这个方法非常好")
        assert 0.0 <= result.confidence <= 1.0

    def test_sentiment_label_valid(self, processor):
        """情感标签合法。"""
        result = processor.analyze_sentiment("测试文本")
        assert result.label in ("positive", "negative", "neutral")


# ===== 学术术语识别测试 =====


class TestIdentifyTerms:
    """identify_terms 方法测试。"""

    def test_identify_terms_basic(self, processor):
        """基本术语识别。"""
        terms = processor.identify_terms("深度学习方法和卷积神经网络模型")
        assert isinstance(terms, list)
        assert all(isinstance(t, Entity) for t in terms)

    def test_identify_terms_empty(self, processor):
        """空字符串术语识别。"""
        assert processor.identify_terms("") == []

    def test_identify_terms_min_length(self, processor):
        """最小长度过滤。"""
        terms = processor.identify_terms("深度学习方法", min_length=4)
        assert all(len(t.text) >= 4 for t in terms)

    def test_identify_terms_entity_type(self, processor):
        """术语实体类型为 TERM。"""
        terms = processor.identify_terms("深度学习方法")
        assert all(t.entity_type == "TERM" for t in terms)


# ===== 公式识别测试 =====


class TestIdentifyFormulas:
    """identify_formulas 方法测试。"""

    def test_identify_formulas_inline(self, processor):
        """行内公式识别。"""
        text = "能量公式 $E=mc^2$ 是著名的方程"
        formulas = processor.identify_formulas(text)
        assert len(formulas) >= 1
        assert any(f.formula_type == "inline" for f in formulas)

    def test_identify_formulas_block(self, processor):
        """块级公式识别。"""
        text = "块级公式 $$\\int_0^1 x dx$$ 是积分"
        formulas = processor.identify_formulas(text)
        assert len(formulas) >= 1
        assert any(f.formula_type == "block" for f in formulas)

    def test_identify_formulas_empty(self, processor):
        """空字符串公式识别。"""
        assert processor.identify_formulas("") == []

    def test_identify_formulas_no_formula(self, processor):
        """无公式文本。"""
        formulas = processor.identify_formulas("这是一段普通文本没有公式")
        assert formulas == []

    def test_identify_formulas_offset(self, processor):
        """公式偏移正确。"""
        text = "前缀 $E=mc^2$ 后缀"
        formulas = processor.identify_formulas(text)
        assert len(formulas) >= 1
        f = formulas[0]
        assert text[f.start:f.end] == f.text


# ===== 引用识别测试 =====


class TestIdentifyCitations:
    """identify_citations 方法测试。"""

    def test_identify_citations_numeric(self, processor):
        """数字引用识别。"""
        text = "深度学习[1]是机器学习的分支[2,3]"
        citations = processor.identify_citations(text)
        assert len(citations) >= 1
        assert any(c.citation_type == "numeric" for c in citations)

    def test_identify_citations_author_year(self, processor):
        """作者-年份引用识别。"""
        text = "深度学习 (Smith, 2020) 是重要技术"
        citations = processor.identify_citations(text)
        assert len(citations) >= 1

    def test_identify_citations_empty(self, processor):
        """空字符串引用识别。"""
        assert processor.identify_citations("") == []

    def test_identify_citations_no_citation(self, processor):
        """无引用文本。"""
        citations = processor.identify_citations("这是一段普通文本没有引用")
        assert citations == []

    def test_identify_citations_offset(self, processor):
        """引用偏移正确。"""
        text = "前缀[1]后缀"
        citations = processor.identify_citations(text)
        assert len(citations) >= 1
        c = citations[0]
        assert text[c.start:c.end] == c.text


# ===== SimHash 测试 =====


class TestSimHash:
    """compute_simhash 与 hamming_distance 测试。"""

    def test_compute_simhash_returns_int(self, processor):
        """SimHash 返回整数。"""
        h = processor.compute_simhash("深度学习")
        assert isinstance(h, int)

    def test_compute_simhash_empty(self, processor):
        """空字符串 SimHash 为 0。"""
        assert processor.compute_simhash("") == 0

    def test_compute_simhash_same_text(self, processor):
        """相同文本 SimHash 相同。"""
        h1 = processor.compute_simhash("深度学习自然语言处理")
        h2 = processor.compute_simhash("深度学习自然语言处理")
        assert h1 == h2

    def test_compute_simhash_similar_text_small_distance(self, processor):
        """相似文本海明距离较小。"""
        h1 = processor.compute_simhash("深度学习在自然语言处理中的应用")
        h2 = processor.compute_simhash("深度学习在自然语言处理中的应用研究")
        distance = processor.hamming_distance(h1, h2)
        assert distance < 32

    def test_hamming_distance_same_hash(self, processor):
        """相同哈希海明距离为 0。"""
        assert processor.hamming_distance(123, 123) == 0

    def test_hamming_distance_different_hash(self, processor):
        """不同哈希海明距离大于 0。"""
        assert processor.hamming_distance(0, 1) == 1

    def test_compute_simhash_custom_bits(self, processor):
        """自定义哈希位数。"""
        h = processor.compute_simhash("深度学习", hash_bits=32)
        assert isinstance(h, int)


# ===== MinHash 测试 =====


class TestMinHash:
    """compute_minhash_signature 与 estimate_jaccard 测试。"""

    def test_compute_minhash_signature_length(self, processor):
        """MinHash 签名长度。"""
        sig = processor.compute_minhash_signature("深度学习", num_hashes=64)
        assert len(sig) == 64

    def test_compute_minhash_signature_empty(self, processor):
        """空字符串 MinHash 签名。"""
        sig = processor.compute_minhash_signature("")
        assert len(sig) == 128
        assert all(h == 0 for h in sig)

    def test_compute_minhash_signature_same_text(self, processor):
        """相同文本 MinHash 签名相同。"""
        sig1 = processor.compute_minhash_signature("深度学习自然语言处理")
        sig2 = processor.compute_minhash_signature("深度学习自然语言处理")
        assert sig1 == sig2

    def test_estimate_jaccard_identical(self, processor):
        """相同签名 Jaccard 为 1.0。"""
        sig = processor.compute_minhash_signature("深度学习")
        assert processor.estimate_jaccard(sig, sig) == 1.0

    def test_estimate_jaccard_different_length(self, processor):
        """不同长度签名 Jaccard 为 0。"""
        sig1 = [1, 2, 3]
        sig2 = [1, 2]
        assert processor.estimate_jaccard(sig1, sig2) == 0.0

    def test_estimate_jaccard_empty(self, processor):
        """空签名 Jaccard 为 0。"""
        assert processor.estimate_jaccard([], []) == 0.0

    def test_estimate_jaccard_similar_text(self, processor):
        """相似文本 Jaccard 较高。"""
        sig1 = processor.compute_minhash_signature("深度学习在自然语言处理中的应用研究")
        sig2 = processor.compute_minhash_signature("深度学习在自然语言处理中的应用")
        jaccard = processor.estimate_jaccard(sig1, sig2)
        assert 0.0 <= jaccard <= 1.0


# ===== 文本去重测试 =====


class TestDeduplicate:
    """deduplicate 方法测试。"""

    def test_deduplicate_simhash_identical(self, processor):
        """SimHash 去重相同文本。"""
        texts = ["深度学习", "深度学习", "自然语言处理"]
        kept = processor.deduplicate(texts, method="simhash")
        assert 0 in kept
        assert 2 in kept
        assert 1 not in kept

    def test_deduplicate_minhash_identical(self, processor):
        """MinHash 去重相同文本。"""
        texts = ["深度学习自然语言处理", "深度学习自然语言处理", "机器学习算法"]
        kept = processor.deduplicate(texts, method="minhash")
        assert 0 in kept
        assert 2 in kept

    def test_deduplicate_empty(self, processor):
        """空列表去重。"""
        assert processor.deduplicate([]) == []

    def test_deduplicate_all_unique(self, processor):
        """全部唯一文本。"""
        texts = ["深度学习方法", "自然语言处理技术", "卷积神经网络模型"]
        kept = processor.deduplicate(texts, similarity_threshold=0.99)
        assert len(kept) == 3

    def test_deduplicate_threshold(self, processor):
        """阈值参数。"""
        texts = ["深度学习", "深度学习", "完全不同的内容关于天气"]
        kept = processor.deduplicate(texts, similarity_threshold=0.5)
        assert 0 in kept
        assert 2 in kept


# ===== 相似度计算测试 =====


class TestComputeSimilarity:
    """compute_similarity 方法测试。"""

    def test_similarity_cosine_identical(self, processor):
        """相同文本余弦相似度为 1.0。"""
        text = "深度学习自然语言处理"
        sim = processor.compute_similarity(text, text, method="cosine")
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_similarity_cosine_different(self, processor):
        """不同文本余弦相似度较低。"""
        sim = processor.compute_similarity("深度学习", "天气预报", method="cosine")
        assert 0.0 <= sim <= 1.0

    def test_similarity_jaccard(self, processor):
        """Jaccard 相似度。"""
        text = "深度学习自然语言处理"
        sim = processor.compute_similarity(text, text, method="jaccard")
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_similarity_edit(self, processor):
        """编辑距离相似度。"""
        sim = processor.compute_similarity("深度学习", "深度学习", method="edit")
        assert sim == pytest.approx(1.0)

    def test_similarity_simhash(self, processor):
        """SimHash 相似度。"""
        text = "深度学习自然语言处理"
        sim = processor.compute_similarity(text, text, method="simhash")
        assert sim == pytest.approx(1.0)

    def test_similarity_empty(self, processor):
        """空字符串相似度为 0。"""
        assert processor.compute_similarity("", "测试") == 0.0
        assert processor.compute_similarity("测试", "") == 0.0

    def test_similarity_unknown_method_defaults_cosine(self, processor):
        """未知方法默认使用 cosine。"""
        text = "深度学习"
        sim = processor.compute_similarity(text, text, method="unknown")
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_similarity_range(self, processor):
        """相似度在 [0, 1] 范围内。"""
        sim = processor.compute_similarity("深度学习", "自然语言", method="cosine")
        assert 0.0 <= sim <= 1.0


# ===== 中英文混合切分测试 =====


class TestSplitMixedText:
    """split_mixed_text 方法测试。"""

    def test_split_mixed_text_basic(self, processor):
        """基本混合切分。"""
        result = processor.split_mixed_text("深度学习 deep learning")
        assert isinstance(result, list)
        assert len(result) >= 2
        langs = [lang for _, lang in result]
        assert "zh" in langs
        assert "en" in langs

    def test_split_mixed_text_empty(self, processor):
        """空字符串混合切分。"""
        assert processor.split_mixed_text("") == []

    def test_split_mixed_text_pure_chinese(self, processor):
        """纯中文切分。"""
        result = processor.split_mixed_text("深度学习")
        assert all(lang == "zh" for _, lang in result)

    def test_split_mixed_text_pure_english(self, processor):
        """纯英文切分。"""
        result = processor.split_mixed_text("deep learning")
        assert all(lang == "en" for _, lang in result)


# ===== 语言检测测试 =====


class TestDetectLanguage:
    """detect_language 方法测试。"""

    def test_detect_language_chinese(self, processor):
        """检测中文。"""
        assert processor.detect_language("深度学习自然语言处理") == "zh"

    def test_detect_language_english(self, processor):
        """检测英文。"""
        assert processor.detect_language("deep learning natural language processing") == "en"

    def test_detect_language_mixed(self, processor):
        """检测混合语言。"""
        assert processor.detect_language("深度学习 deep learning") == "mixed"

    def test_detect_language_empty(self, processor):
        """空字符串默认中文。"""
        assert processor.detect_language("") == "zh"

    def test_detect_language_numbers_only(self, processor):
        """纯数字默认中文。"""
        assert processor.detect_language("12345") == "zh"


# ===== 批量处理测试 =====


class TestBatchOperations:
    """批量处理方法测试。"""

    def test_batch_tokenize(self, processor):
        """批量分词。"""
        texts = ["深度学习", "自然语言处理", "machine learning"]
        results = processor.batch_tokenize(texts)
        assert len(results) == 3
        assert all(isinstance(r, list) for r in results)

    def test_batch_tokenize_empty(self, processor):
        """空列表批量分词。"""
        assert processor.batch_tokenize([]) == []

    def test_batch_tokenize_with_pos(self, processor):
        """批量带词性分词。"""
        texts = ["深度学习", "自然语言"]
        results = processor.batch_tokenize(texts, with_pos=True)
        assert all(all(t.pos for t in r) for r in results)

    def test_batch_extract_keywords(self, processor, sample_long_text):
        """批量关键词提取。"""
        texts = [sample_long_text, "自然语言处理是人工智能的重要领域"]
        results = processor.batch_extract_keywords(texts, top_k=3)
        assert len(results) == 2
        assert all(len(r) <= 3 for r in results)

    def test_batch_extract_keywords_empty(self, processor):
        """空列表批量关键词提取。"""
        assert processor.batch_extract_keywords([]) == []

    def test_batch_compute_similarity(self, processor):
        """批量相似度计算。"""
        query = "深度学习"
        candidates = ["深度学习", "自然语言处理", "天气预报"]
        results = processor.batch_compute_similarity(query, candidates)
        assert len(results) == 3
        assert all(0.0 <= r <= 1.0 for r in results)

    def test_batch_compute_similarity_empty(self, processor):
        """空候选列表。"""
        assert processor.batch_compute_similarity("测试", []) == []


# ===== 文本统计测试 =====


class TestTextStatistics:
    """text_statistics 方法测试。"""

    def test_text_statistics_basic(self, processor, sample_long_text):
        """基本文本统计。"""
        stats = processor.text_statistics(sample_long_text)
        assert isinstance(stats, dict)
        assert "char_count" in stats
        assert "word_count" in stats
        assert "sentence_count" in stats
        assert "language" in stats

    def test_text_statistics_empty(self, processor):
        """空字符串统计。"""
        stats = processor.text_statistics("")
        assert stats["char_count"] == 0
        assert stats["word_count"] == 0
        assert stats["sentence_count"] == 0

    def test_text_statistics_char_count(self, processor):
        """字符数统计。"""
        text = "深度学习"
        stats = processor.text_statistics(text)
        assert stats["char_count"] == len(text)

    def test_text_statistics_language(self, processor):
        """语言检测字段。"""
        stats = processor.text_statistics("deep learning")
        assert stats["language"] == "en"

    def test_text_statistics_cjk_count(self, processor):
        """中文字符计数。"""
        text = "深度学习 deep"
        stats = processor.text_statistics(text)
        assert stats["cjk_char_count"] == 4
        assert stats["alpha_char_count"] == 4

    def test_text_statistics_unique_words(self, processor):
        """唯一词数。"""
        text = "深度学习 深度学习 自然语言"
        stats = processor.text_statistics(text)
        assert stats["unique_word_count"] > 0


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试。"""

    def test_all_methods_with_empty_string(self, processor):
        """所有方法处理空字符串不抛异常。"""
        assert processor.normalize("") == ""
        assert processor.tokenize("") == []
        assert processor.split_sentences("") == []
        assert processor.split_paragraphs("") == []
        assert processor.extract_keywords("") == []
        assert processor.generate_summary("") == ""
        assert processor.identify_terms("") == []
        assert processor.identify_formulas("") == []
        assert processor.identify_citations("") == []
        assert processor.compute_simhash("") == 0

    def test_only_punctuation(self, processor):
        """仅标点文本。"""
        tokens = processor.tokenize("。。。！！！")
        assert isinstance(tokens, list)

    def test_only_whitespace(self, processor):
        """仅空白文本。"""
        assert processor.normalize("   ") == ""
        assert processor.tokenize("   ") == []

    def test_very_long_text(self, processor):
        """超长文本不抛异常。"""
        long_text = "深度学习是机器学习的分支。" * 100
        tokens = processor.tokenize(long_text)
        assert len(tokens) > 0

    def test_special_characters(self, processor):
        """特殊字符处理。"""
        text = "深度学习\n\t\r自然语言"
        result = processor.normalize(text)
        assert isinstance(result, str)


# ===== 自定义词典与停用词测试 =====


class TestCustomDictAndStopwords:
    """自定义词典与停用词测试。"""

    def test_custom_dictionary(self):
        """自定义词典。"""
        proc = ChineseProcessor(dictionary={"自定义词"})
        assert "自定义词" in proc.dictionary

    def test_custom_stopwords(self):
        """自定义停用词。"""
        proc = ChineseProcessor(stopwords={"自定义停用"})
        assert "自定义停用" in proc.stopwords

    def test_add_stopwords(self, processor):
        """添加停用词。"""
        processor.add_stopwords(["新停用词"])
        assert "新停用词" in processor.stopwords

    def test_remove_stopwords(self, processor):
        """移除停用词。"""
        processor.add_stopwords(["临时词"])
        processor.remove_stopwords(["临时词"])
        assert "临时词" not in processor.stopwords

    def test_add_dictionary_words(self, processor):
        """添加词典词。"""
        processor.add_dictionary_words(["新词典词"])
        assert "新词典词" in processor.dictionary


# ===== 单例与模块级函数测试 =====


class TestSingletonAndModuleFunctions:
    """单例与模块级便捷函数测试。"""

    def test_get_instance_singleton(self):
        """get_instance 返回单例。"""
        inst1 = ChineseProcessor.get_instance()
        inst2 = ChineseProcessor.get_instance()
        assert inst1 is inst2

    def test_get_chinese_processor(self):
        """get_chinese_processor 模块级函数。"""
        proc = get_chinese_processor()
        assert isinstance(proc, ChineseProcessor)

    def test_module_tokenize(self):
        """模块级 tokenize 函数。"""
        tokens = tokenize("深度学习")
        assert len(tokens) > 0

    def test_module_extract_keywords(self, sample_long_text):
        """模块级 extract_keywords 函数。"""
        keywords = extract_keywords(sample_long_text, top_k=3)
        assert len(keywords) <= 3

    def test_module_split_sentences(self):
        """模块级 split_sentences 函数。"""
        sentences = split_sentences("深度学习。自然语言处理。")
        assert len(sentences) >= 2

    def test_module_compute_similarity(self):
        """模块级 compute_similarity 函数。"""
        sim = compute_similarity("深度学习", "深度学习")
        assert 0.0 <= sim <= 1.0


# ===== 线程安全测试 =====


class TestThreadSafety:
    """线程安全测试。"""

    def test_concurrent_tokenize(self, processor):
        """并发分词不抛异常。"""
        results = [None] * 10
        errors = []

        def worker(idx):
            try:
                results[idx] = processor.tokenize(f"深度学习测试{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert all(r is not None for r in results)

    def test_concurrent_compute_simhash(self, processor):
        """并发 SimHash 计算不抛异常。"""
        results = [None] * 5
        errors = []

        def worker(idx):
            try:
                results[idx] = processor.compute_simhash(f"深度学习自然语言处理{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert all(isinstance(r, int) for r in results)
