"""文本处理器模块

提供中英文混合文本处理能力，包括：
    - 分词（中文按字符 + 英文按词）
    - 句子分割（中英文标点感知）
    - 段落识别
    - 文本相似度计算（余弦/Jaccard/编辑距离）
    - 关键词提取（TF-IDF/TextRank）
    - 摘要生成（基于 TextRank 与频率）
    - 文本分类（基于规则）
    - 情感分析（基于词典）
    - 语言检测
    - 学术文本去重
    - 引用识别
    - 公式识别

仅使用 Python 标准库实现，可选依赖 jieba（中文分词）与 numpy（向量化），
缺失时自动降级为字符级处理。

典型用法：
    processor = TextProcessor()
    tokens = processor.tokenize("深度学习在自然语言处理中的应用研究")
    keywords = processor.extract_keywords_tfidf(text, top_k=10)
    similarity = processor.cosine_similarity(text1, text2)
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# 尝试导入可选依赖
try:
    import jieba  # type: ignore

    _HAS_JIEBA = True
except ImportError:  # pragma: no cover - 降级处理
    jieba = None  # type: ignore
    _HAS_JIEBA = False

try:
    import numpy as np  # type: ignore

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    np = None  # type: ignore
    _HAS_NUMPY = False

# 尝试导入日志
try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


# ===== 常量定义 =====

# 中文标点
CHINESE_PUNCTUATIONS = "，。！？；：、""''（）《》【】「」『』…—·"

# 英文标点
ENGLISH_PUNCTUATIONS = ",.!?;:\"'()[]{}<>-"

# 句子结束符
SENTENCE_ENDINGS = "。！？!?；;\n."

# 段落分隔符
PARAGRAPH_SEPARATORS = "\n\r"

# 中文字符范围
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

# 英文单词
ENGLISH_WORD_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z'-]*")

# 数字
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")

# 引用模式（如 [1] / (Smith, 2020) / 张三（2020））
CITATION_PATTERNS = [
    re.compile(r"\[\d+(?:[-,]\s*\d+)*\]"),  # [1] / [1,2,3] / [1-3]
    re.compile(r"\(\s*[A-Z][a-zA-Z]+(?:\s+et\s+al\.?)?\s*,\s*\d{4}\s*\)"),  # (Smith, 2020)
    re.compile(r"\(\s*[A-Z][a-zA-Z]+(?:\s+(?:and|&)\s+[A-Z][a-zA-Z]+)?\s*,\s*\d{4}\s*\)"),
    re.compile(r"[\u4e00-\u9fff]{2,4}（\d{4}）"),  # 张三（2020）
    re.compile(r"[\u4e00-\u9fff]{2,4}等（\d{4}）"),  # 张三等（2020）
    re.compile(r"[A-Z][a-zA-Z]+\s+等（\d{4}）"),  # Smith 等（2020）
]

# 公式模式（简化识别）
FORMULA_PATTERNS = [
    re.compile(r"\$\$[^$]+\$\$"),  # $$...$$ 块级公式
    re.compile(r"\$[^$]+\$"),  # $...$ 行内公式
    re.compile(r"\\\([^)]+\\\)"),  # \(...\)
    re.compile(r"\\\[[^\]]+\\\]"),  # \[...\]
    re.compile(r"\b(?:sin|cos|tan|log|ln|exp|sqrt|sum|prod|int|lim)\s*\(.*?\)"),
]

# 学术文本常见结构词
SECTION_HEADERS = {
    "zh": [
        "摘要", "引言", "绪论", "背景", "相关工作", "文献综述",
        "方法", "研究方法", "实验", "实验设计", "结果", "结果分析",
        "讨论", "结论", "致谢", "参考文献", "附录",
        "研究背景", "研究意义", "研究内容", "研究方法", "技术路线",
        "创新点", "可行性分析", "研究展望",
    ],
    "en": [
        "abstract", "introduction", "background", "related work",
        "literature review", "methods", "methodology", "experiments",
        "experimental design", "results", "analysis", "discussion",
        "conclusion", "acknowledgments", "references", "appendix",
    ],
}

# 停用词（中文常见）
CHINESE_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "那", "与", "或",
    "但", "而", "及", "以", "为", "被", "让", "使", "从", "向",
    "把", "对", "关于", "通过", "进行", "可以", "能够", "应该",
    "需要", "可能", "由于", "因此", "所以", "如果", "虽然", "但是",
    "然而", "此外", "另外", "其中", "其他", "某些", "一些", "许多",
    "大量", "少量", "主要", "重要", "基本", "一般", "通常", "往往",
    "已经", "正在", "将要", "曾经", "现在", "过去", "未来",
}

# 停用词（英文常见）
ENGLISH_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "as", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "could", "should", "may",
    "might", "must", "can", "this", "that", "these", "those",
    "i", "you", "he", "she", "it", "we", "they", "what", "which",
    "who", "whom", "whose", "when", "where", "why", "how", "all",
    "each", "every", "both", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "also", "however", "therefore", "moreover",
    "furthermore", "nevertheless", "thus", "hence", "accordingly",
}


@dataclass
class TokenizeResult:
    """分词结果。"""

    tokens: List[str] = field(default_factory=list)
    pos_tags: List[str] = field(default_factory=list)  # 词性标注（可选）
    language: str = "mixed"  # zh / en / mixed
    token_count: int = 0
    char_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens": self.tokens,
            "pos_tags": self.pos_tags,
            "language": self.language,
            "token_count": self.token_count,
            "char_count": self.char_count,
        }


@dataclass
class Sentence:
    """句子。"""

    text: str
    start_pos: int = 0
    end_pos: int = 0
    language: str = "mixed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "language": self.language,
        }


@dataclass
class Paragraph:
    """段落。"""

    text: str
    sentences: List[Sentence] = field(default_factory=list)
    start_pos: int = 0
    end_pos: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "sentences": [s.to_dict() for s in self.sentences],
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
        }


@dataclass
class Keyword:
    """关键词。"""

    word: str
    score: float
    frequency: int = 0
    pos_tag: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "score": self.score,
            "frequency": self.frequency,
            "pos_tag": self.pos_tag,
        }


@dataclass
class Citation:
    """引用。"""

    raw_text: str
    citation_type: str = ""  # bracket / parenthetical / chinese
    start_pos: int = 0
    end_pos: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "citation_type": self.citation_type,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
        }


@dataclass
class Formula:
    """公式。"""

    raw_text: str
    formula_type: str = ""  # inline / block
    start_pos: int = 0
    end_pos: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "formula_type": self.formula_type,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
        }


@dataclass
class TextClassification:
    """文本分类结果。"""

    category: str
    confidence: float
    labels: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "labels": self.labels,
            "scores": self.scores,
        }


@dataclass
class SentimentResult:
    """情感分析结果。"""

    sentiment: str  # positive / negative / neutral
    score: float  # [-1, 1]
    positive_words: List[str] = field(default_factory=list)
    negative_words: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sentiment": self.sentiment,
            "score": self.score,
            "positive_words": self.positive_words,
            "negative_words": self.negative_words,
        }


class TextProcessor:
    """文本处理器

    提供中英文混合文本的全方位处理能力。
    所有方法均为纯函数式（除缓存外无副作用），可独立调用。
    """

    def __init__(
        self,
        use_jieba: bool = True,
        use_numpy: bool = True,
        custom_stopwords: Optional[Set[str]] = None,
    ):
        """初始化文本处理器。

        Args:
            use_jieba: 是否使用 jieba 分词（若可用）。
            use_numpy: 是否使用 numpy 加速（若可用）。
            custom_stopwords: 自定义停用词集合。
        """
        self._use_jieba = use_jieba and _HAS_JIEBA
        self._use_numpy = use_numpy and _HAS_NUMPY
        self._stopwords: Set[str] = CHINESE_STOPWORDS | ENGLISH_STOPWORDS
        if custom_stopwords:
            self._stopwords |= custom_stopwords
        # 缓存
        self._token_cache: Dict[str, TokenizeResult] = {}
        self._sentence_cache: Dict[str, List[Sentence]] = {}
        self._max_cache_size = 1000
        # 情感词典
        self._positive_words = {
            # 中文正向
            "好", "优秀", "卓越", "杰出", "突出", "显著", "成功", "有效",
            "高效", "创新", "突破", "进步", "改善", "提升", "优化", "优势",
            "正确", "准确", "精确", "完整", "全面", "深入", "详尽", "充分",
            "稳定", "可靠", "安全", "灵活", "便捷", "智能", "先进", "前沿",
            # 英文正向
            "good", "great", "excellent", "outstanding", "remarkable",
            "successful", "effective", "efficient", "innovative", "novel",
            "breakthrough", "improve", "enhance", "optimize", "advantage",
            "correct", "accurate", "precise", "complete", "comprehensive",
            "stable", "reliable", "secure", "flexible", "convenient",
            "intelligent", "advanced", "cutting-edge", "promising",
        }
        self._negative_words = {
            # 中文负向
            "差", "坏", "失败", "无效", "低效", "落后", "缺陷", "不足",
            "问题", "错误", "偏差", "缺失", "遗漏", "局限", "限制", "障碍",
            "困难", "挑战", "风险", "威胁", "危险", "不稳定", "不可靠",
            "复杂", "繁琐", "困难", "缓慢", "陈旧", "过时", "传统",
            # 英文负向
            "bad", "poor", "fail", "failure", "ineffective", "inefficient",
            "outdated", "defect", "flaw", "limitation", "problem", "error",
            "bias", "missing", "lack", "shortcoming", "drawback", "weakness",
            "difficult", "challenge", "risk", "threat", "unstable",
            "unreliable", "complex", "cumbersome", "slow", "obsolete",
        }

    # ===== 分词 =====

    def tokenize(
        self,
        text: str,
        remove_stopwords: bool = False,
        keep_punctuation: bool = False,
    ) -> TokenizeResult:
        """分词。

        支持中英文混合文本：
            - 中文：使用 jieba（若可用），否则按字符切分
            - 英文：按空白与标点切分
            - 数字：保留为整体

        Args:
            text: 待分词文本。
            remove_stopwords: 是否移除停用词。
            keep_punctuation: 是否保留标点。

        Returns:
            分词结果。
        """
        if not text:
            return TokenizeResult()
        # 检查缓存
        cache_key = f"{hash(text)}|{remove_stopwords}|{keep_punctuation}"
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]
        # 规范化文本
        normalized = self._normalize(text)
        # 检测语言
        language = self.detect_language(normalized)
        # 分词
        if self._use_jieba and language in ("zh", "mixed"):
            tokens = self._tokenize_with_jieba(normalized)
        else:
            tokens = self._tokenize_fallback(normalized)
        # 过滤
        if not keep_punctuation:
            tokens = [t for t in tokens if not self._is_punctuation(t)]
        if remove_stopwords:
            tokens = [t for t in tokens if t.lower() not in self._stopwords]
        # 过滤空 token
        tokens = [t for t in tokens if t.strip()]
        result = TokenizeResult(
            tokens=tokens,
            language=language,
            token_count=len(tokens),
            char_count=len(text),
        )
        # 写入缓存
        self._update_cache(self._token_cache, cache_key, result)
        return result

    def _tokenize_with_jieba(self, text: str) -> List[str]:
        """使用 jieba 分词。"""
        try:
            return list(jieba.cut(text))
        except Exception as e:
            _logger.debug(f"jieba 分词失败，降级到字符级: {e}")
            return self._tokenize_fallback(text)

    def _tokenize_fallback(self, text: str) -> List[str]:
        """降级分词（无 jieba 时）。

        策略：
            - 中文字符使用 2 字滑动窗口（便于匹配词典词）
            - 英文单词整体保留
            - 数字整体保留
        """
        tokens: List[str] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if CJK_PATTERN.match(ch):
                # 收集连续中文字符
                j = i
                while j < n and CJK_PATTERN.match(text[j]):
                    j += 1
                cjk_seq = text[i:j]
                if len(cjk_seq) == 1:
                    tokens.append(cjk_seq)
                else:
                    # 2 字滑动窗口
                    for k in range(len(cjk_seq) - 1):
                        tokens.append(cjk_seq[k:k + 2])
                    # 奇数长度时最后一个单字也加入
                    if len(cjk_seq) % 2 == 1:
                        tokens.append(cjk_seq[-1])
                i = j
            elif ch.isalpha():
                # 英文单词
                m = ENGLISH_WORD_PATTERN.match(text, i)
                if m:
                    tokens.append(m.group())
                    i = m.end()
                else:
                    tokens.append(ch)
                    i += 1
            elif ch.isdigit():
                # 数字
                m = NUMBER_PATTERN.match(text, i)
                if m:
                    tokens.append(m.group())
                    i = m.end()
                else:
                    tokens.append(ch)
                    i += 1
            elif ch.isspace():
                i += 1
            else:
                # 标点或其他
                tokens.append(ch)
                i += 1
        return tokens

    def tokenize_to_words(self, text: str, remove_stopwords: bool = True) -> List[str]:
        """分词并返回词列表（便捷方法）。"""
        return self.tokenize(text, remove_stopwords=remove_stopwords).tokens

    # ===== 句子与段落 =====

    def split_sentences(self, text: str) -> List[Sentence]:
        """句子分割。

        支持中英文标点，保留句子在原文中的位置。
        """
        if not text:
            return []
        cache_key = hash(text)
        if cache_key in self._sentence_cache:
            return self._sentence_cache[cache_key]
        sentences: List[Sentence] = []
        current_start = 0
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch in SENTENCE_ENDINGS:
                # 包含结束符
                sentence_text = text[current_start : i + 1].strip()
                if sentence_text:
                    sentences.append(
                        Sentence(
                            text=sentence_text,
                            start_pos=current_start,
                            end_pos=i + 1,
                            language=self.detect_language(sentence_text),
                        )
                    )
                current_start = i + 1
            i += 1
        # 处理最后未结束的部分
        if current_start < n:
            sentence_text = text[current_start:].strip()
            if sentence_text:
                sentences.append(
                    Sentence(
                        text=sentence_text,
                        start_pos=current_start,
                        end_pos=n,
                        language=self.detect_language(sentence_text),
                    )
                )
        # 写入缓存
        self._update_cache(self._sentence_cache, cache_key, sentences)
        return sentences

    def split_paragraphs(self, text: str) -> List[Paragraph]:
        """段落分割。"""
        if not text:
            return []
        # 按连续换行分割
        raw_paragraphs = re.split(r"\n\s*\n", text)
        paragraphs: List[Paragraph] = []
        pos = 0
        for raw in raw_paragraphs:
            stripped = raw.strip()
            if not stripped:
                pos += len(raw) + 1
                continue
            start = text.find(stripped, pos)
            if start < 0:
                start = pos
            end = start + len(stripped)
            sentences = self.split_sentences(stripped)
            paragraphs.append(
                Paragraph(
                    text=stripped,
                    sentences=sentences,
                    start_pos=start,
                    end_pos=end,
                )
            )
            pos = end
        return paragraphs

    # ===== 文本相似度 =====

    def cosine_similarity(self, text1: str, text2: str) -> float:
        """计算余弦相似度。

        基于词频向量计算，取值 [0, 1]。
        """
        tokens1 = self.tokenize_to_words(text1)
        tokens2 = self.tokenize_to_words(text2)
        if not tokens1 or not tokens2:
            return 0.0
        # 构建词频向量
        counter1 = Counter(tokens1)
        counter2 = Counter(tokens2)
        all_words = set(counter1.keys()) | set(counter2.keys())
        if self._use_numpy:
            vec1 = np.array([counter1.get(w, 0) for w in all_words], dtype=float)
            vec2 = np.array([counter2.get(w, 0) for w in all_words], dtype=float)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(np.dot(vec1, vec2) / (norm1 * norm2))
        # 纯 Python 实现
        dot_product = sum(counter1.get(w, 0) * counter2.get(w, 0) for w in all_words)
        norm1 = math.sqrt(sum(v * v for v in counter1.values()))
        norm2 = math.sqrt(sum(v * v for v in counter2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def jaccard_similarity(self, text1: str, text2: str) -> float:
        """计算 Jaccard 相似度。

        Jaccard = |A ∩ B| / |A ∪ B|，取值 [0, 1]。
        """
        tokens1 = set(self.tokenize_to_words(text1))
        tokens2 = set(self.tokenize_to_words(text2))
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        return len(intersection) / len(union) if union else 0.0

    def edit_distance(self, s1: str, s2: str) -> int:
        """计算编辑距离（Levenshtein 距离）。"""
        if not s1:
            return len(s2)
        if not s2:
            return len(s1)
        m, n = len(s1), len(s2)
        # 使用滚动数组优化空间
        prev = list(range(n + 1))
        curr = [0] * (n + 1)
        for i in range(1, m + 1):
            curr[0] = i
            for j in range(1, n + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                curr[j] = min(
                    prev[j] + 1,  # 删除
                    curr[j - 1] + 1,  # 插入
                    prev[j - 1] + cost,  # 替换
                )
            prev, curr = curr, prev
        return prev[n]

    def edit_distance_ratio(self, s1: str, s2: str) -> float:
        """编辑距离相似度（归一化到 [0, 1]）。"""
        if not s1 and not s2:
            return 1.0
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0
        distance = self.edit_distance(s1, s2)
        return 1.0 - distance / max_len

    def ngram_similarity(self, text1: str, text2: str, n: int = 2) -> float:
        """N-gram 相似度（基于 N-gram 集合的 Jaccard）。"""
        ngrams1 = self._get_ngrams(text1, n)
        ngrams2 = self._get_ngrams(text2, n)
        if not ngrams1 or not ngrams2:
            return 0.0
        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2
        return len(intersection) / len(union) if union else 0.0

    def _get_ngrams(self, text: str, n: int) -> Set[str]:
        """获取 N-gram 集合。"""
        # 按字符切分（中文友好）
        chars = [c for c in text if not c.isspace()]
        if len(chars) < n:
            return set()
        return {"".join(chars[i : i + n]) for i in range(len(chars) - n + 1)}

    def hybrid_similarity(
        self,
        text1: str,
        text2: str,
        cosine_weight: float = 0.5,
        jaccard_weight: float = 0.3,
        edit_weight: float = 0.2,
    ) -> float:
        """混合相似度（加权融合多种相似度）。"""
        cosine = self.cosine_similarity(text1, text2)
        jaccard = self.jaccard_similarity(text1, text2)
        edit = self.edit_distance_ratio(text1, text2)
        total_weight = cosine_weight + jaccard_weight + edit_weight
        if total_weight == 0:
            return 0.0
        return (
            cosine * cosine_weight
            + jaccard * jaccard_weight
            + edit * edit_weight
        ) / total_weight

    # ===== 关键词提取 =====

    def extract_keywords_tfidf(
        self,
        text: str,
        top_k: int = 10,
        document_freq: Optional[Dict[str, int]] = None,
        total_docs: int = 100,
    ) -> List[Keyword]:
        """基于 TF-IDF 提取关键词。

        Args:
            text: 待处理文本。
            top_k: 返回的关键词数。
            document_freq: 文档频率字典（每个词在多少文档中出现过）。
            total_docs: 文档总数。

        Returns:
            关键词列表（按分数降序）。
        """
        tokens = self.tokenize_to_words(text, remove_stopwords=True)
        if not tokens:
            return []
        # 计算 TF
        tf = Counter(tokens)
        total_tokens = len(tokens)
        # 计算 IDF
        keywords: List[Keyword] = []
        for word, count in tf.items():
            tf_val = count / total_tokens
            if document_freq and word in document_freq:
                df = document_freq[word]
            else:
                df = 1  # 默认假设只在当前文档出现
            idf = math.log((total_docs + 1) / (df + 1)) + 1
            score = tf_val * idf
            keywords.append(
                Keyword(word=word, score=score, frequency=count)
            )
        # 排序并截取
        keywords.sort(key=lambda k: k.score, reverse=True)
        return keywords[:top_k]

    def extract_keywords_textrank(
        self,
        text: str,
        top_k: int = 10,
        window_size: int = 4,
        max_iter: int = 50,
        damping: float = 0.85,
        tolerance: float = 1e-5,
    ) -> List[Keyword]:
        """基于 TextRank 提取关键词。

        通过构建词共现图，使用 PageRank 迭代计算词的重要性。

        Args:
            text: 待处理文本。
            top_k: 返回的关键词数。
            window_size: 共现窗口大小。
            max_iter: 最大迭代次数。
            damping: 阻尼系数。
            tolerance: 收敛阈值。

        Returns:
            关键词列表。
        """
        tokens = self.tokenize_to_words(text, remove_stopwords=True)
        if len(tokens) < 2:
            return [Keyword(word=t, score=1.0, frequency=1) for t in tokens][:top_k]
        # 构建共现图
        graph: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for i, word in enumerate(tokens):
            for j in range(i + 1, min(i + window_size, len(tokens))):
                other = tokens[j]
                if word != other:
                    graph[word][other] += 1.0
                    graph[other][word] += 1.0
        if not graph:
            return [Keyword(word=t, score=1.0, frequency=1) for t in tokens][:top_k]
        # 初始化分数
        words = list(graph.keys())
        scores: Dict[str, float] = {w: 1.0 for w in words}
        # PageRank 迭代
        for _ in range(max_iter):
            new_scores: Dict[str, float] = {}
            delta = 0.0
            for word in words:
                # 计算入边贡献
                in_sum = 0.0
                for other, weight in graph[word].items():
                    out_weight_sum = sum(graph[other].values())
                    if out_weight_sum > 0:
                        in_sum += (weight / out_weight_sum) * scores[other]
                new_score = (1 - damping) + damping * in_sum
                new_scores[word] = new_score
                delta += abs(new_score - scores[word])
            scores = new_scores
            if delta < tolerance:
                break
        # 计算词频
        tf = Counter(tokens)
        # 构建结果
        keywords = [
            Keyword(word=w, score=scores[w], frequency=tf[w])
            for w in words
        ]
        keywords.sort(key=lambda k: k.score, reverse=True)
        return keywords[:top_k]

    def extract_keywords(
        self,
        text: str,
        top_k: int = 10,
        method: str = "tfidf",
        **kwargs,
    ) -> List[Keyword]:
        """关键词提取（统一入口）。"""
        if method == "tfidf":
            return self.extract_keywords_tfidf(text, top_k=top_k, **kwargs)
        elif method == "textrank":
            return self.extract_keywords_textrank(text, top_k=top_k, **kwargs)
        else:
            raise ValueError(f"不支持的关键词提取方法: {method}")

    # ===== 摘要生成 =====

    def generate_summary(
        self,
        text: str,
        max_sentences: int = 3,
        method: str = "textrank",
    ) -> str:
        """生成文本摘要。

        基于 TextRank 算法对句子进行排序，选取 top N 句作为摘要。

        Args:
            text: 原文。
            max_sentences: 摘要包含的最大句子数。
            method: 摘要方法（textrank / frequency）。

        Returns:
            摘要字符串。
        """
        sentences = self.split_sentences(text)
        if len(sentences) <= max_sentences:
            return text.strip()
        if method == "textrank":
            return self._summary_textrank(sentences, max_sentences)
        elif method == "frequency":
            return self._summary_frequency(sentences, text, max_sentences)
        else:
            raise ValueError(f"不支持的摘要方法: {method}")

    def _summary_textrank(self, sentences: List[Sentence], top_n: int) -> str:
        """基于 TextRank 的摘要。"""
        if not sentences:
            return ""
        # 构建句子相似度图
        n = len(sentences)
        graph: List[List[float]] = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                sim = self.cosine_similarity(sentences[i].text, sentences[j].text)
                graph[i][j] = sim
                graph[j][i] = sim
        # PageRank 迭代
        scores = [1.0] * n
        damping = 0.85
        for _ in range(50):
            new_scores = []
            for i in range(n):
                in_sum = 0.0
                for j in range(n):
                    if i != j and graph[j][i] > 0:
                        out_sum = sum(graph[j])
                        if out_sum > 0:
                            in_sum += (graph[j][i] / out_sum) * scores[j]
                new_scores.append((1 - damping) + damping * in_sum)
            scores = new_scores
        # 选取 top N 句（保持原文顺序）
        ranked_indices = sorted(range(n), key=lambda i: scores[i], reverse=True)
        selected = sorted(ranked_indices[:top_n])
        return " ".join(sentences[i].text for i in selected)

    def _summary_frequency(
        self,
        sentences: List[Sentence],
        full_text: str,
        top_n: int,
    ) -> str:
        """基于词频的摘要。"""
        # 计算全文词频
        tokens = self.tokenize_to_words(full_text, remove_stopwords=True)
        if not tokens:
            return ""
        word_freq = Counter(tokens)
        max_freq = max(word_freq.values()) if word_freq else 1
        # 归一化
        for w in word_freq:
            word_freq[w] /= max_freq
        # 为每个句子打分
        scored: List[Tuple[int, float]] = []
        for i, sent in enumerate(sentences):
            sent_tokens = self.tokenize_to_words(sent.text, remove_stopwords=True)
            if not sent_tokens:
                continue
            score = sum(word_freq.get(t, 0) for t in sent_tokens) / len(sent_tokens)
            scored.append((i, score))
        # 选取 top N 句（保持原文顺序）
        scored.sort(key=lambda x: x[1], reverse=True)
        selected_indices = sorted(idx for idx, _ in scored[:top_n])
        return " ".join(sentences[i].text for i in selected_indices)

    # ===== 文本分类 =====

    def classify(self, text: str) -> TextClassification:
        """文本分类（基于规则）。

        识别文本属于哪类学术内容：摘要/引言/方法/结果/结论/其他。
        """
        if not text:
            return TextClassification(category="unknown", confidence=0.0)
        # 检测章节标题
        text_lower = text.lower().strip()
        first_line = text_lower.split("\n")[0].strip() if "\n" in text else text_lower[:50]
        # 匹配章节标题
        scores: Dict[str, float] = {}
        for lang_headers in SECTION_HEADERS.values():
            for header in lang_headers:
                if header in first_line or header in text_lower[:100]:
                    category = self._header_to_category(header)
                    scores[category] = scores.get(category, 0) + 1.0
        # 基于关键词的额外判断
        keyword_categories = {
            "abstract": ["摘要", "abstract", "关键词", "keywords"],
            "introduction": ["引言", "绪论", "introduction", "背景", "background"],
            "method": ["方法", "method", "实验设计", "experimental design", "算法", "algorithm"],
            "result": ["结果", "result", "实验结果", "experimental result", "性能", "performance"],
            "conclusion": ["结论", "conclusion", "总结", "summary", "展望", "future work"],
            "reference": ["参考文献", "references", "bibliography"],
        }
        for category, keywords in keyword_categories.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[category] = scores.get(category, 0) + 0.5
        if not scores:
            return TextClassification(category="other", confidence=0.5)
        # 选取最高分
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]
        total_score = sum(scores.values())
        confidence = best_score / total_score if total_score > 0 else 0.0
        return TextClassification(
            category=best_category,
            confidence=min(confidence, 1.0),
            labels=list(scores.keys()),
            scores=scores,
        )

    def _header_to_category(self, header: str) -> str:
        """将章节标题映射到分类。"""
        header_lower = header.lower()
        if header in ("摘要", "abstract"):
            return "abstract"
        if header in ("引言", "绪论", "introduction", "背景", "研究背景", "background"):
            return "introduction"
        if header in ("方法", "研究方法", "method", "methodology", "算法", "技术路线"):
            return "method"
        if header in ("结果", "结果分析", "result", "实验", "实验设计", "experiments"):
            return "result"
        if header in ("结论", "conclusion", "总结", "研究展望"):
            return "conclusion"
        if header in ("参考文献", "references", "bibliography"):
            return "reference"
        if header in ("相关工作", "文献综述", "related work", "literature review"):
            return "related_work"
        if header in ("讨论", "discussion"):
            return "discussion"
        if header in ("致谢", "acknowledgments"):
            return "acknowledgment"
        if header in ("附录", "appendix"):
            return "appendix"
        return "other"

    # ===== 情感分析 =====

    def analyze_sentiment(self, text: str) -> SentimentResult:
        """情感分析（基于词典）。

        适用于学术文本中的评价性语句。
        """
        if not text:
            return SentimentResult(sentiment="neutral", score=0.0)
        tokens = self.tokenize_to_words(text, remove_stopwords=False)
        positive_found: List[str] = []
        negative_found: List[str] = []
        for token in tokens:
            token_lower = token.lower()
            if token_lower in self._positive_words or token in self._positive_words:
                if token not in positive_found:
                    positive_found.append(token)
            elif token_lower in self._negative_words or token in self._negative_words:
                if token not in negative_found:
                    negative_found.append(token)
        pos_count = len(positive_found)
        neg_count = len(negative_found)
        total = pos_count + neg_count
        if total == 0:
            return SentimentResult(sentiment="neutral", score=0.0)
        score = (pos_count - neg_count) / total
        if score > 0.2:
            sentiment = "positive"
        elif score < -0.2:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        return SentimentResult(
            sentiment=sentiment,
            score=round(score, 4),
            positive_words=positive_found,
            negative_words=negative_found,
        )

    # ===== 语言检测 =====

    def detect_language(self, text: str) -> str:
        """检测文本语言。

        Returns:
            "zh" / "en" / "mixed"。
        """
        if not text:
            return "mixed"
        chinese_chars = len(CJK_PATTERN.findall(text))
        english_chars = len(re.findall(r"[a-zA-Z]", text))
        total = chinese_chars + english_chars
        if total == 0:
            return "mixed"
        chinese_ratio = chinese_chars / total
        if chinese_ratio > 0.7:
            return "zh"
        elif chinese_ratio < 0.2:
            return "en"
        return "mixed"

    # ===== 学术文本特殊处理 =====

    def extract_citations(self, text: str) -> List[Citation]:
        """识别引用。"""
        citations: List[Citation] = []
        for pattern in CITATION_PATTERNS:
            for match in pattern.finditer(text):
                citation_type = self._classify_citation(match.group())
                citations.append(
                    Citation(
                        raw_text=match.group(),
                        citation_type=citation_type,
                        start_pos=match.start(),
                        end_pos=match.end(),
                    )
                )
        # 按位置排序
        citations.sort(key=lambda c: c.start_pos)
        return citations

    def _classify_citation(self, raw: str) -> str:
        """分类引用类型。"""
        if raw.startswith("[") and raw.endswith("]"):
            return "bracket"
        if raw.startswith("(") and raw.endswith(")"):
            return "parenthetical"
        if "（" in raw and "）" in raw:
            return "chinese"
        return "unknown"

    def extract_formulas(self, text: str) -> List[Formula]:
        """识别公式。"""
        formulas: List[Formula] = []
        for pattern in FORMULA_PATTERNS:
            for match in pattern.finditer(text):
                formula_type = "block" if "$$" in match.group() or "\\[" in match.group() else "inline"
                formulas.append(
                    Formula(
                        raw_text=match.group(),
                        formula_type=formula_type,
                        start_pos=match.start(),
                        end_pos=match.end(),
                    )
                )
        formulas.sort(key=lambda f: f.start_pos)
        return formulas

    def remove_citations(self, text: str) -> str:
        """移除引用标记。"""
        result = text
        for pattern in CITATION_PATTERNS:
            result = pattern.sub("", result)
        return result

    def remove_formulas(self, text: str) -> str:
        """移除公式。"""
        result = text
        for pattern in FORMULA_PATTERNS:
            result = pattern.sub("", result)
        return result

    def clean_academic_text(self, text: str) -> str:
        """清理学术文本（移除引用、公式、多余空白）。"""
        result = self.remove_citations(text)
        result = self.remove_formulas(result)
        # 规范化空白
        result = re.sub(r"\s+", " ", result).strip()
        return result

    # ===== 去重 =====

    def compute_text_hash(self, text: str) -> str:
        """计算文本哈希（用于去重）。"""
        normalized = self._normalize(text)
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def compute_simhash(self, text: str, hash_bits: int = 64) -> str:
        """计算 SimHash（用于近似去重）。

        Args:
            text: 文本。
            hash_bits: 哈希位数。

        Returns:
            SimHash 值的十六进制字符串。
        """
        tokens = self.tokenize_to_words(text, remove_stopwords=True)
        if not tokens:
            return "0" * (hash_bits // 4)
        # 计算每个 token 的哈希
        token_hashes: List[int] = []
        weights: List[int] = []
        tf = Counter(tokens)
        for token, count in tf.items():
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            token_hashes.append(h)
            weights.append(count)
        # 加权合并
        vector = [0] * hash_bits
        for h, w in zip(token_hashes, weights):
            for i in range(hash_bits):
                bit = (h >> i) & 1
                vector[i] += w if bit else -w
        # 生成最终哈希
        result = 0
        for i in range(hash_bits):
            if vector[i] > 0:
                result |= (1 << i)
        return format(result, f"0{hash_bits // 4}x")

    def hamming_distance(self, hash1: str, hash2: str) -> int:
        """计算两个十六进制哈希的汉明距离。"""
        try:
            n1 = int(hash1, 16)
            n2 = int(hash2, 16)
            xor = n1 ^ n2
            distance = 0
            while xor:
                distance += xor & 1
                xor >>= 1
            return distance
        except ValueError:
            return -1

    def is_duplicate(
        self,
        text1: str,
        text2: str,
        threshold: float = 0.85,
        method: str = "hybrid",
    ) -> bool:
        """判断两段文本是否重复。

        Args:
            text1: 文本 1。
            text2: 文本 2。
            threshold: 重复阈值。
            method: 相似度计算方法（cosine/jaccard/edit/hybrid/ngram）。

        Returns:
            是否重复。
        """
        if method == "cosine":
            sim = self.cosine_similarity(text1, text2)
        elif method == "jaccard":
            sim = self.jaccard_similarity(text1, text2)
        elif method == "edit":
            sim = self.edit_distance_ratio(text1, text2)
        elif method == "ngram":
            sim = self.ngram_similarity(text1, text2, n=2)
        else:
            sim = self.hybrid_similarity(text1, text2)
        return sim >= threshold

    def find_duplicates(
        self,
        texts: List[str],
        threshold: float = 0.85,
        method: str = "hybrid",
    ) -> List[Tuple[int, int, float]]:
        """在文本列表中查找重复对。

        Args:
            texts: 文本列表。
            threshold: 重复阈值。
            method: 相似度方法。

        Returns:
            重复对列表 (i, j, similarity)。
        """
        duplicates: List[Tuple[int, int, float]] = []
        n = len(texts)
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._compute_similarity(texts[i], texts[j], method)
                if sim >= threshold:
                    duplicates.append((i, j, sim))
        return duplicates

    def _compute_similarity(self, text1: str, text2: str, method: str) -> float:
        """根据方法名计算相似度。"""
        if method == "cosine":
            return self.cosine_similarity(text1, text2)
        elif method == "jaccard":
            return self.jaccard_similarity(text1, text2)
        elif method == "edit":
            return self.edit_distance_ratio(text1, text2)
        elif method == "ngram":
            return self.ngram_similarity(text1, text2)
        else:
            return self.hybrid_similarity(text1, text2)

    # ===== 工具方法 =====

    def _normalize(self, text: str) -> str:
        """文本规范化。"""
        if not text:
            return ""
        # Unicode 规范化
        text = unicodedata.normalize("NFKC", text)
        # 全角转半角（英文部分）
        text = text.translate(
            str.maketrans(
                "０１２３４５６７８９"
                "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
                "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
                "0123456789"
                "abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            )
        )
        return text

    def _is_punctuation(self, token: str) -> bool:
        """判断是否为标点。"""
        if not token:
            return False
        if len(token) == 1:
            cp = ord(token)
            # ASCII 标点
            if 33 <= cp <= 47 or 58 <= cp <= 64 or 91 <= cp <= 96 or 123 <= cp <= 126:
                return True
            # 中文标点
            if token in CHINESE_PUNCTUATIONS:
                return True
            # Unicode 标点类别
            try:
                category = unicodedata.category(token)
                if category.startswith("P"):
                    return True
            except Exception:
                pass
        return False

    def _update_cache(self, cache: Dict, key: Any, value: Any) -> None:
        """更新缓存（LRU 策略简化版）。"""
        if len(cache) >= self._max_cache_size:
            # 移除最早的 10% 缓存
            remove_count = max(1, self._max_cache_size // 10)
            for k in list(cache.keys())[:remove_count]:
                cache.pop(k, None)
        cache[key] = value

    def clear_cache(self) -> None:
        """清空缓存。"""
        self._token_cache.clear()
        self._sentence_cache.clear()

    # ===== 统计信息 =====

    def get_text_stats(self, text: str) -> Dict[str, Any]:
        """获取文本统计信息。"""
        if not text:
            return {
                "char_count": 0,
                "word_count": 0,
                "sentence_count": 0,
                "paragraph_count": 0,
                "language": "mixed",
            }
        tokens = self.tokenize(text)
        sentences = self.split_sentences(text)
        paragraphs = self.split_paragraphs(text)
        chinese_chars = len(CJK_PATTERN.findall(text))
        english_words = len(ENGLISH_WORD_PATTERN.findall(text))
        return {
            "char_count": len(text),
            "char_count_no_space": len(text.replace(" ", "").replace("\n", "")),
            "word_count": tokens.token_count,
            "sentence_count": len(sentences),
            "paragraph_count": len(paragraphs),
            "chinese_char_count": chinese_chars,
            "english_word_count": english_words,
            "language": tokens.language,
            "avg_sentence_length": (
                len(text) / len(sentences) if sentences else 0
            ),
            "citation_count": len(self.extract_citations(text)),
            "formula_count": len(self.extract_formulas(text)),
        }

    def extract_section_headers(self, text: str) -> List[str]:
        """识别文本中的章节标题。"""
        headers: List[str] = []
        lines = text.split("\n")
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            # 检查是否匹配已知标题
            for lang_headers in SECTION_HEADERS.values():
                for header in lang_headers:
                    if line_stripped.lower() == header.lower() or line_stripped == header:
                        headers.append(line_stripped)
                        break
        return headers

    def split_by_sections(self, text: str) -> Dict[str, str]:
        """按章节分割文本。

        Returns:
            {section_name: section_text} 字典。
        """
        sections: Dict[str, str] = {}
        current_section = "preamble"
        current_text: List[str] = []
        lines = text.split("\n")
        for line in lines:
            line_stripped = line.strip()
            matched_header = None
            for lang_headers in SECTION_HEADERS.values():
                for header in lang_headers:
                    if line_stripped.lower() == header.lower() or line_stripped == header:
                        matched_header = header
                        break
                if matched_header:
                    break
            if matched_header:
                # 保存上一节
                if current_text:
                    sections[current_section] = "\n".join(current_text).strip()
                current_section = matched_header
                current_text = []
            else:
                current_text.append(line)
        # 保存最后一节
        if current_text:
            sections[current_section] = "\n".join(current_text).strip()
        return sections


# ===== 模块级便捷函数 =====


_text_processor_instance: Optional[TextProcessor] = None
_instance_lock = __import__("threading").Lock()


def get_text_processor() -> TextProcessor:
    """获取全局文本处理器单例。"""
    global _text_processor_instance
    if _text_processor_instance is None:
        with _instance_lock:
            if _text_processor_instance is None:
                _text_processor_instance = TextProcessor()
    return _text_processor_instance


def tokenize(text: str, remove_stopwords: bool = False) -> List[str]:
    """分词便捷函数。"""
    return get_text_processor().tokenize_to_words(text, remove_stopwords=remove_stopwords)


def extract_keywords(text: str, top_k: int = 10, method: str = "tfidf") -> List[str]:
    """关键词提取便捷函数。"""
    processor = get_text_processor()
    keywords = processor.extract_keywords(text, top_k=top_k, method=method)
    return [kw.word for kw in keywords]


def compute_similarity(text1: str, text2: str, method: str = "cosine") -> float:
    """相似度计算便捷函数。"""
    processor = get_text_processor()
    return processor._compute_similarity(text1, text2, method)


def summarize(text: str, max_sentences: int = 3) -> str:
    """摘要生成便捷函数。"""
    return get_text_processor().generate_summary(text, max_sentences=max_sentences)


# ===== 单元测试可运行逻辑 =====


def _run_self_test() -> None:
    """模块自检。

    可直接 `python -m backend.ml.text_processor` 运行。
    """
    processor = TextProcessor()

    # 测试分词
    text_zh = "深度学习在自然语言处理中的应用研究"
    tokens = processor.tokenize(text_zh)
    assert tokens.token_count > 0
    print(f"中文分词: {tokens.tokens[:10]}")

    text_en = "Deep learning has been applied to natural language processing."
    tokens_en = processor.tokenize(text_en)
    assert tokens_en.token_count > 0
    print(f"英文分词: {tokens_en.tokens[:10]}")

    text_mixed = "本文研究 deep learning 在 NLP 中的应用。"
    tokens_mixed = processor.tokenize(text_mixed)
    assert tokens_mixed.language == "mixed"
    print(f"混合分词: {tokens_mixed.tokens[:10]}")

    # 测试句子分割
    text = "这是第一句。这是第二句！这是第三句？最后一句。"
    sentences = processor.split_sentences(text)
    assert len(sentences) == 4
    print(f"句子数: {len(sentences)}")

    # 测试段落分割
    text_paras = "第一段第一句。第一段第二句。\n\n第二段第一句。"
    paragraphs = processor.split_paragraphs(text_paras)
    assert len(paragraphs) == 2

    # 测试相似度
    text1 = "深度学习在自然语言处理中的应用"
    text2 = "自然语言处理中深度学习的应用"
    text3 = "区块链技术在金融领域的探索"
    sim12 = processor.cosine_similarity(text1, text2)
    sim13 = processor.cosine_similarity(text1, text3)
    assert sim12 > sim13, f"相似文本应得分更高: {sim12} vs {sim13}"
    print(f"余弦相似度: {sim12:.4f} (相似) vs {sim13:.4f} (不同)")

    jaccard = processor.jaccard_similarity(text1, text2)
    assert 0 <= jaccard <= 1

    edit = processor.edit_distance("kitten", "sitting")
    assert edit == 3
    edit_ratio = processor.edit_distance_ratio("kitten", "sitting")
    assert 0 <= edit_ratio <= 1

    # 测试关键词提取
    long_text = (
        "深度学习是机器学习的一个分支，通过多层神经网络学习数据的表示。"
        "深度学习在图像识别、自然语言处理、语音识别等领域取得了显著成果。"
        "卷积神经网络和循环神经网络是深度学习的两种重要模型。"
        "近年来，Transformer 架构在自然语言处理任务中表现优异。"
    )
    keywords_tfidf = processor.extract_keywords_tfidf(long_text, top_k=5)
    assert len(keywords_tfidf) > 0
    print(f"TF-IDF 关键词: {[kw.word for kw in keywords_tfidf]}")

    keywords_textrank = processor.extract_keywords_textrank(long_text, top_k=5)
    assert len(keywords_textrank) > 0
    print(f"TextRank 关键词: {[kw.word for kw in keywords_textrank]}")

    # 测试摘要
    summary = processor.generate_summary(long_text, max_sentences=2)
    assert len(summary) > 0
    print(f"摘要: {summary[:80]}...")

    # 测试分类
    abstract_text = "摘要：本文研究深度学习在自然语言处理中的应用。关键词：深度学习；NLP"
    classification = processor.classify(abstract_text)
    assert classification.category == "abstract"
    print(f"分类: {classification.category} (置信度 {classification.confidence:.2f})")

    # 测试情感分析
    sentiment = processor.analyze_sentiment("这种方法取得了显著的成功，效果优秀。")
    assert sentiment.sentiment == "positive"
    print(f"情感: {sentiment.sentiment} (score={sentiment.score})")

    # 测试语言检测
    assert processor.detect_language("你好世界") == "zh"
    assert processor.detect_language("Hello world") == "en"
    assert processor.detect_language("你好 hello") == "mixed"

    # 测试引用识别
    text_with_citations = (
        "深度学习[1]在 NLP 领域广泛应用。"
        "Smith 等（2020）提出了 Transformer 架构。"
        "参见 (Vaswani et al., 2017) 的研究。"
    )
    citations = processor.extract_citations(text_with_citations)
    assert len(citations) >= 2
    print(f"引用数: {len(citations)}")

    # 测试去重
    text_a = "深度学习在自然语言处理中的应用研究"
    text_b = "深度学习在自然语言处理中的应用研究（扩展版）"
    text_c = "完全不同的内容关于区块链技术"
    is_dup = processor.is_duplicate(text_a, text_b, threshold=0.6)
    not_dup = processor.is_duplicate(text_a, text_c, threshold=0.6)
    print(f"重复检测: 相似={is_dup}, 不同={not_dup}")

    # 测试 SimHash
    hash1 = processor.compute_simhash(text1)
    hash2 = processor.compute_simhash(text2)
    hash3 = processor.compute_simhash(text3)
    dist12 = processor.hamming_distance(hash1, hash2)
    dist13 = processor.hamming_distance(hash1, hash3)
    print(f"SimHash 汉明距离: 相似={dist12}, 不同={dist13}")

    # 测试统计
    stats = processor.get_text_stats(long_text)
    assert stats["char_count"] > 0
    assert stats["sentence_count"] > 0
    print(f"文本统计: {stats['char_count']} 字, {stats['sentence_count']} 句")

    # 测试章节分割
    sectioned_text = (
        "摘要\n本文研究深度学习。\n\n"
        "引言\n深度学习是机器学习分支。\n\n"
        "方法\n我们使用 Transformer 模型。"
    )
    sections = processor.split_by_sections(sectioned_text)
    assert "摘要" in sections
    assert "引言" in sections
    assert "方法" in sections
    print(f"章节: {list(sections.keys())}")

    print("TextProcessor 自检通过")


if __name__ == "__main__":
    _run_self_test()
