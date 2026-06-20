"""抄袭检测

提供文本相似度计算、n-gram 分析、引用验证、原创性评分等能力。

核心组件：
    - TextSimilarity: 文本相似度计算器（多种算法）
    - NGramAnalyzer: n-gram 分析器
    - CitationVerifier: 引用验证器
    - OriginalityScorer: 原创性评分器
    - PlagiarismChecker: 抄袭检测器（整合以上组件）

支持的相似度算法：
    - 余弦相似度（Cosine Similarity）
    - Jaccard 相似度
    - 编辑距离（Levenshtein Distance）
    - 最长公共子序列（LCS）
    - n-gram 重叠度
"""
import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional


# ===== 数据结构 =====


@dataclass
class SimilarityResult:
    """相似度结果"""
    score: float  # 0.0 - 1.0
    algorithm: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "algorithm": self.algorithm,
            "details": self.details,
        }


@dataclass
class PlagiarismMatch:
    """抄袭匹配片段"""
    source_text: str
    target_text: str
    similarity: float
    source_start: int = 0
    source_end: int = 0
    target_start: int = 0
    target_end: int = 0
    source_reference: str = ""

    def to_dict(self) -> dict:
        return {
            "source_text": self.source_text,
            "target_text": self.target_text,
            "similarity": self.similarity,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "target_start": self.target_start,
            "target_end": self.target_end,
            "source_reference": self.source_reference,
        }


@dataclass
class OriginalityReport:
    """原创性报告"""
    overall_score: float  # 0.0 - 1.0（1.0 表示完全原创）
    similarity_score: float  # 0.0 - 1.0（0.0 表示完全原创）
    matches: list = field(default_factory=list)
    citation_coverage: float = 0.0
    ngram_analysis: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)
    is_plagiarized: bool = False
    severity: str = "none"  # none / low / medium / high / critical

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "similarity_score": self.similarity_score,
            "matches": [m.to_dict() if isinstance(m, PlagiarismMatch) else m for m in self.matches],
            "citation_coverage": self.citation_coverage,
            "ngram_analysis": self.ngram_analysis,
            "recommendations": self.recommendations,
            "is_plagiarized": self.is_plagiarized,
            "severity": self.severity,
        }


# ===== 文本预处理 =====


def preprocess_text(text: str, remove_punctuation: bool = True, lowercase: bool = True) -> str:
    """文本预处理。

    Args:
        text: 原始文本。
        remove_punctuation: 是否移除标点。
        lowercase: 是否转小写。

    Returns:
        预处理后的文本。
    """
    if not text:
        return ""
    result = text.strip()
    if lowercase:
        result = result.lower()
    if remove_punctuation:
        # 保留中文、字母、数字、空格
        result = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", result)
        result = re.sub(r"\s+", " ", result).strip()
    return result


def tokenize(text: str, language: str = "auto") -> list:
    """分词。

    Args:
        text: 文本。
        language: 语言（auto / chinese / english）。

    Returns:
        词列表。
    """
    if not text:
        return []
    text = preprocess_text(text)
    if language == "chinese":
        # 简单中文分词：按字切分
        return list(text.replace(" ", ""))
    elif language == "english":
        return text.split()
    else:  # auto
        # 中英文混合：中文按字，英文按词
        tokens = []
        current_english = []
        for char in text:
            if re.match(r"[\u4e00-\u9fff]", char):
                if current_english:
                    tokens.append("".join(current_english))
                    current_english = []
                tokens.append(char)
            elif re.match(r"[a-zA-Z0-9]", char):
                current_english.append(char)
            else:
                if current_english:
                    tokens.append("".join(current_english))
                    current_english = []
        if current_english:
            tokens.append("".join(current_english))
        return tokens


# ===== 文本相似度计算器 =====


class TextSimilarity:
    """文本相似度计算器

    提供多种文本相似度计算算法。
    """

    @staticmethod
    def cosine_similarity(text1: str, text2: str) -> SimilarityResult:
        """余弦相似度。

        基于词频向量的余弦相似度。

        Args:
            text1: 文本1。
            text2: 文本2。

        Returns:
            SimilarityResult，score 为 0.0 - 1.0。
        """
        tokens1 = tokenize(text1)
        tokens2 = tokenize(text2)
        if not tokens1 or not tokens2:
            return SimilarityResult(score=0.0, algorithm="cosine")

        # 构建词频向量
        counter1 = Counter(tokens1)
        counter2 = Counter(tokens2)
        all_tokens = set(counter1.keys()) | set(counter2.keys())

        # 计算点积与模
        dot_product = sum(counter1[t] * counter2[t] for t in all_tokens)
        magnitude1 = math.sqrt(sum(v ** 2 for v in counter1.values()))
        magnitude2 = math.sqrt(sum(v ** 2 for v in counter2.values()))

        if magnitude1 == 0 or magnitude2 == 0:
            return SimilarityResult(score=0.0, algorithm="cosine")

        score = dot_product / (magnitude1 * magnitude2)
        return SimilarityResult(
            score=score,
            algorithm="cosine",
            details={
                "tokens1_count": len(tokens1),
                "tokens2_count": len(tokens2),
                "unique_tokens": len(all_tokens),
            },
        )

    @staticmethod
    def jaccard_similarity(text1: str, text2: str) -> SimilarityResult:
        """Jaccard 相似度。

        交集大小除以并集大小。

        Args:
            text1: 文本1。
            text2: 文本2。

        Returns:
            SimilarityResult。
        """
        tokens1 = set(tokenize(text1))
        tokens2 = set(tokenize(text2))
        if not tokens1 or not tokens2:
            return SimilarityResult(score=0.0, algorithm="jaccard")

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        score = len(intersection) / len(union) if union else 0.0
        return SimilarityResult(
            score=score,
            algorithm="jaccard",
            details={
                "intersection_size": len(intersection),
                "union_size": len(union),
                "common_tokens": list(intersection)[:20],
            },
        )

    @staticmethod
    def levenshtein_distance(text1: str, text2: str) -> SimilarityResult:
        """编辑距离相似度。

        基于编辑距离的相似度：1 - distance / max_length。

        Args:
            text1: 文本1。
            text2: 文本2。

        Returns:
            SimilarityResult。
        """
        if not text1 and not text2:
            return SimilarityResult(score=1.0, algorithm="levenshtein")
        if not text1 or not text2:
            return SimilarityResult(score=0.0, algorithm="levenshtein")

        # 计算编辑距离
        m, n = len(text1), len(text2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if text1[i - 1] == text2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

        distance = dp[m][n]
        max_len = max(m, n)
        score = 1 - distance / max_len if max_len > 0 else 0.0
        return SimilarityResult(
            score=score,
            algorithm="levenshtein",
            details={"distance": distance, "max_length": max_len},
        )

    @staticmethod
    def lcs_similarity(text1: str, text2: str) -> SimilarityResult:
        """最长公共子序列相似度。

        LCS 长度除以较短文本长度。

        Args:
            text1: 文本1。
            text2: 文本2。

        Returns:
            SimilarityResult。
        """
        if not text1 or not text2:
            return SimilarityResult(score=0.0, algorithm="lcs")

        m, n = len(text1), len(text2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if text1[i - 1] == text2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        lcs_length = dp[m][n]
        min_len = min(m, n)
        score = lcs_length / min_len if min_len > 0 else 0.0
        return SimilarityResult(
            score=score,
            algorithm="lcs",
            details={"lcs_length": lcs_length, "min_length": min_len},
        )

    @staticmethod
    def ngram_similarity(text1: str, text2: str, n: int = 3) -> SimilarityResult:
        """n-gram 相似度。

        基于 n-gram 集合的 Jaccard 相似度。

        Args:
            text1: 文本1。
            text2: 文本2。
            n: n-gram 大小。

        Returns:
            SimilarityResult。
        """
        ngrams1 = set(_generate_ngrams(text1, n))
        ngrams2 = set(_generate_ngrams(text2, n))
        if not ngrams1 or not ngrams2:
            return SimilarityResult(score=0.0, algorithm=f"ngram-{n}")

        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2
        score = len(intersection) / len(union) if union else 0.0
        return SimilarityResult(
            score=score,
            algorithm=f"ngram-{n}",
            details={
                "n": n,
                "ngrams1_count": len(ngrams1),
                "ngrams2_count": len(ngrams2),
                "common_ngrams": len(intersection),
            },
        )

    @staticmethod
    def combined_similarity(text1: str, text2: str) -> SimilarityResult:
        """组合相似度。

        综合多种算法的加权平均。

        Returns:
            SimilarityResult。
        """
        cosine = TextSimilarity.cosine_similarity(text1, text2)
        jaccard = TextSimilarity.jaccard_similarity(text1, text2)
        ngram = TextSimilarity.ngram_similarity(text1, text2, n=3)

        # 加权平均
        score = (
            cosine.score * 0.4
            + jaccard.score * 0.3
            + ngram.score * 0.3
        )
        return SimilarityResult(
            score=score,
            algorithm="combined",
            details={
                "cosine": cosine.score,
                "jaccard": jaccard.score,
                "ngram": ngram.score,
            },
        )

    @staticmethod
    def calculate(text1: str, text2: str, algorithm: str = "combined") -> SimilarityResult:
        """计算相似度（按算法名分发）。

        Args:
            text1: 文本1。
            text2: 文本2。
            algorithm: 算法名（cosine/jaccard/levenshtein/lcs/ngram/combined）。

        Returns:
            SimilarityResult。
        """
        algorithms = {
            "cosine": TextSimilarity.cosine_similarity,
            "jaccard": TextSimilarity.jaccard_similarity,
            "levenshtein": TextSimilarity.levenshtein_distance,
            "lcs": TextSimilarity.lcs_similarity,
            "ngram": lambda t1, t2: TextSimilarity.ngram_similarity(t1, t2, n=3),
            "combined": TextSimilarity.combined_similarity,
        }
        func = algorithms.get(algorithm, TextSimilarity.combined_similarity)
        return func(text1, text2)


def _generate_ngrams(text: str, n: int = 3) -> list:
    """生成 n-gram。

    Args:
        text: 文本。
        n: n-gram 大小。

    Returns:
        n-gram 列表。
    """
    text = preprocess_text(text)
    if len(text) < n:
        return [text] if text else []
    return [text[i : i + n] for i in range(len(text) - n + 1)]


# ===== n-gram 分析器 =====


class NGramAnalyzer:
    """n-gram 分析器

    分析文本的 n-gram 分布，检测异常重复模式。
    """

    def __init__(self, n: int = 3):
        self.n = n

    def analyze(self, text: str) -> dict:
        """分析文本的 n-gram 分布。

        Args:
            text: 文本。

        Returns:
            分析结果字典。
        """
        ngrams = _generate_ngrams(text, self.n)
        if not ngrams:
            return {
                "total_ngrams": 0,
                "unique_ngrams": 0,
                "repetition_rate": 0.0,
                "top_ngrams": [],
            }

        counter = Counter(ngrams)
        total = len(ngrams)
        unique = len(counter)
        repetition_rate = 1 - (unique / total) if total > 0 else 0.0

        return {
            "total_ngrams": total,
            "unique_ngrams": unique,
            "repetition_rate": repetition_rate,
            "top_ngrams": [
                {"ngram": ng, "count": count, "frequency": count / total}
                for ng, count in counter.most_common(20)
            ],
        }

    def find_repeated_ngrams(self, text: str, min_count: int = 3) -> list:
        """查找重复的 n-gram。

        Args:
            text: 文本。
            min_count: 最小重复次数。

        Returns:
            重复 n-gram 列表。
        """
        ngrams = _generate_ngrams(text, self.n)
        counter = Counter(ngrams)
        return [
            {"ngram": ng, "count": count}
            for ng, count in counter.items()
            if count >= min_count
        ]

    def compare_texts(self, text1: str, text2: str) -> dict:
        """比较两个文本的 n-gram 分布。

        Args:
            text1: 文本1。
            text2: 文本2。

        Returns:
            比较结果。
        """
        ngrams1 = set(_generate_ngrams(text1, self.n))
        ngrams2 = set(_generate_ngrams(text2, self.n))

        common = ngrams1 & ngrams2
        only_in_1 = ngrams1 - ngrams2
        only_in_2 = ngrams2 - ngrams1

        return {
            "ngrams1_count": len(ngrams1),
            "ngrams2_count": len(ngrams2),
            "common_count": len(common),
            "only_in_text1": len(only_in_1),
            "only_in_text2": len(only_in_2),
            "overlap_rate": len(common) / len(ngrams1 | ngrams2) if (ngrams1 | ngrams2) else 0.0,
            "common_ngrams": list(common)[:50],
        }

    def detect_suspicious_patterns(self, text: str) -> list:
        """检测可疑的重复模式。

        识别文本中异常重复的片段，可能是抄袭迹象。

        Args:
            text: 文本。

        Returns:
            可疑模式列表。
        """
        suspicious = []
        for n in range(3, 8):
            ngrams = _generate_ngrams(text, n)
            counter = Counter(ngrams)
            for ng, count in counter.items():
                if count >= 3 and len(ng) >= n:
                    suspicious.append({
                        "ngram": ng,
                        "n": n,
                        "count": count,
                        "suspicion_level": "high" if count >= 5 else "medium",
                    })
        # 按可疑程度排序
        suspicious.sort(key=lambda x: (x["count"], x["n"]), reverse=True)
        return suspicious[:50]


# ===== 引用验证器 =====


class CitationVerifier:
    """引用验证器

    验证文本中的引用是否正确标注，检测未标注的借鉴内容。
    """

    # 引用模式
    CITATION_PATTERNS = [
        re.compile(r"\[(\d+)\]"),  # [1]
        re.compile(r"\((\d{4})\)"),  # (2020)
        re.compile(r"([A-Z][a-z]+(?:\s+(?:et al\.|and|&)\s+[A-Z][a-z]+)*,\s*\d{4})"),  # Author, 2020
        re.compile(r"（(\d{4})）"),  # 中文括号（2020）
    ]

    def __init__(self):
        self.ngram_analyzer = NGramAnalyzer(n=5)

    def extract_citations(self, text: str) -> list:
        """提取文本中的引用标记。

        Args:
            text: 文本。

        Returns:
            引用列表，每项为 {"type": str, "value": str, "position": int}。
        """
        citations = []
        for i, pattern in enumerate(self.CITATION_PATTERNS):
            for match in pattern.finditer(text):
                cite_type = ["numeric", "year", "author_year", "year_cn"][i]
                citations.append({
                    "type": cite_type,
                    "value": match.group(0),
                    "position": match.start(),
                })
        return citations

    def verify_citation_coverage(
        self,
        text: str,
        reference_texts: list,
        similarity_threshold: float = 0.5,
    ) -> dict:
        """验证引用覆盖率。

        检测文本中与参考文献高度相似的片段是否标注了引用。

        Args:
            text: 待验证文本。
            reference_texts: 参考文献文本列表。
            similarity_threshold: 相似度阈值。

        Returns:
            {"coverage": float, "uncovered_segments": [...], "total_similar": int}
        """
        citations = self.extract_citations(text)
        citation_positions = [c["position"] for c in citations]

        # 分段检测相似度
        segments = self._split_into_segments(text, segment_size=200)
        similar_segments = []
        covered = 0
        total_similar = 0

        for seg in segments:
            is_similar = False
            for ref_text in reference_texts:
                result = TextSimilarity.ngram_similarity(seg["text"], ref_text, n=5)
                if result.score >= similarity_threshold:
                    is_similar = True
                    break

            if is_similar:
                total_similar += 1
                # 检查该段是否有引用
                has_citation = any(
                    seg["start"] <= pos <= seg["end"]
                    for pos in citation_positions
                )
                if has_citation:
                    covered += 1
                else:
                    similar_segments.append({
                        "text": seg["text"][:100] + "...",
                        "start": seg["start"],
                        "end": seg["end"],
                        "has_citation": False,
                    })

        coverage = covered / total_similar if total_similar > 0 else 1.0
        return {
            "coverage": coverage,
            "uncovered_segments": similar_segments,
            "total_similar": total_similar,
            "covered": covered,
            "uncovered": total_similar - covered,
        }

    def _split_into_segments(self, text: str, segment_size: int = 200) -> list:
        """将文本分割为片段。"""
        segments = []
        for i in range(0, len(text), segment_size):
            segments.append({
                "text": text[i : i + segment_size],
                "start": i,
                "end": min(i + segment_size, len(text)),
            })
        return segments

    def check_citation_format(self, text: str, expected_format: str = "numeric") -> dict:
        """检查引用格式一致性。

        Args:
            text: 文本。
            expected_format: 期望格式（numeric / author_year）。

        Returns:
            {"consistent": bool, "found_formats": [...], "inconsistent_count": int}
        """
        citations = self.extract_citations(text)
        formats_found = set(c["type"] for c in citations)
        expected_types = {
            "numeric": ["numeric"],
            "author_year": ["author_year", "year"],
        }
        expected = expected_types.get(expected_format, ["numeric"])
        consistent = formats_found.issubset(set(expected))
        inconsistent = [c for c in citations if c["type"] not in expected]
        return {
            "consistent": consistent,
            "found_formats": list(formats_found),
            "expected_formats": expected,
            "inconsistent_count": len(inconsistent),
            "total_citations": len(citations),
        }


# ===== 原创性评分器 =====


class OriginalityScorer:
    """原创性评分器

    综合多种指标计算文本的原创性评分。
    """

    def __init__(self):
        self.ngram_analyzer = NGramAnalyzer(n=5)
        self.citation_verifier = CitationVerifier()

    def score(
        self,
        text: str,
        reference_texts: Optional[list] = None,
        similarity_threshold: float = 0.5,
    ) -> OriginalityReport:
        """计算原创性评分。

        Args:
            text: 待评分文本。
            reference_texts: 参考文献文本列表。
            similarity_threshold: 相似度阈值。

        Returns:
            OriginalityReport 实例。
        """
        reference_texts = reference_texts or []
        matches = []
        max_similarity = 0.0

        # 与每篇参考文献比较
        for i, ref_text in enumerate(reference_texts):
            result = TextSimilarity.combined_similarity(text, ref_text)
            if result.score >= similarity_threshold:
                max_similarity = max(max_similarity, result.score)
                # 查找相似片段
                seg_matches = self._find_similar_segments(text, ref_text, similarity_threshold)
                for seg in seg_matches:
                    seg.source_reference = f"reference_{i + 1}"
                    matches.append(seg)

        # n-gram 分析
        ngram_analysis = self.ngram_analyzer.analyze(text)
        suspicious_patterns = self.ngram_analyzer.detect_suspicious_patterns(text)

        # 引用覆盖率
        if reference_texts:
            citation_result = self.citation_verifier.verify_citation_coverage(
                text, reference_texts, similarity_threshold
            )
            citation_coverage = citation_result["coverage"]
        else:
            citation_coverage = 1.0
            citation_result = {"coverage": 1.0, "uncovered_segments": [], "total_similar": 0}

        # 计算综合评分
        similarity_score = max_similarity
        # 原创性 = 1 - 相似度，再考虑引用覆盖率
        originality_base = 1.0 - similarity_score
        # 引用覆盖率低则降低原创性
        originality_adjusted = originality_base * (0.5 + 0.5 * citation_coverage)
        # n-gram 重复率影响
        repetition_penalty = ngram_analysis["repetition_rate"] * 0.1
        overall_score = max(0.0, min(1.0, originality_adjusted - repetition_penalty))

        # 判断严重级别
        if similarity_score >= 0.8:
            severity = "critical"
            is_plagiarized = True
        elif similarity_score >= 0.6:
            severity = "high"
            is_plagiarized = True
        elif similarity_score >= 0.4:
            severity = "medium"
            is_plagiarized = False
        elif similarity_score >= 0.2:
            severity = "low"
            is_plagiarized = False
        else:
            severity = "none"
            is_plagiarized = False

        # 生成建议
        recommendations = self._generate_recommendations(
            similarity_score, citation_coverage, ngram_analysis, suspicious_patterns
        )

        return OriginalityReport(
            overall_score=overall_score,
            similarity_score=similarity_score,
            matches=matches,
            citation_coverage=citation_coverage,
            ngram_analysis={
                **ngram_analysis,
                "suspicious_patterns": suspicious_patterns[:10],
            },
            recommendations=recommendations,
            is_plagiarized=is_plagiarized,
            severity=severity,
        )

    def _find_similar_segments(
        self,
        text1: str,
        text2: str,
        threshold: float,
        segment_size: int = 100,
    ) -> list:
        """查找两个文本间的相似片段。"""
        matches = []
        segs1 = self._split_into_segments(text1, segment_size)
        segs2 = self._split_into_segments(text2, segment_size)

        for seg1 in segs1:
            for seg2 in segs2:
                result = TextSimilarity.ngram_similarity(seg1["text"], seg2["text"], n=4)
                if result.score >= threshold:
                    matches.append(PlagiarismMatch(
                        source_text=seg1["text"],
                        target_text=seg2["text"],
                        similarity=result.score,
                        source_start=seg1["start"],
                        source_end=seg1["end"],
                        target_start=seg2["start"],
                        target_end=seg2["end"],
                    ))
        return matches

    def _split_into_segments(self, text: str, segment_size: int = 100) -> list:
        """分割为片段。"""
        segments = []
        for i in range(0, len(text), segment_size):
            segments.append({
                "text": text[i : i + segment_size],
                "start": i,
                "end": min(i + segment_size, len(text)),
            })
        return segments

    def _generate_recommendations(
        self,
        similarity: float,
        citation_coverage: float,
        ngram_analysis: dict,
        suspicious_patterns: list,
    ) -> list:
        """生成改进建议。"""
        recommendations = []

        if similarity >= 0.6:
            recommendations.append("文本与参考文献相似度过高，建议大幅改写")
        elif similarity >= 0.4:
            recommendations.append("文本与参考文献有一定相似度，建议增加原创内容")

        if citation_coverage < 0.5:
            recommendations.append("引用覆盖率低，相似内容未标注引用，建议补充引用")
        elif citation_coverage < 0.8:
            recommendations.append("部分相似内容未标注引用，建议检查引用标注")

        if ngram_analysis["repetition_rate"] > 0.3:
            recommendations.append("文本内重复率较高，建议增加表达多样性")

        if suspicious_patterns:
            recommendations.append(
                f"检测到 {len(suspicious_patterns)} 处可疑重复模式，建议检查"
            )

        if not recommendations:
            recommendations.append("文本原创性良好，未发现明显问题")

        return recommendations


# ===== 抄袭检测器 =====


class PlagiarismChecker:
    """抄袭检测器

    整合相似度计算、n-gram 分析、引用验证与原创性评分。
    """

    def __init__(self, similarity_threshold: float = 0.5, ngram_size: int = 5):
        self.similarity_threshold = similarity_threshold
        self.ngram_size = ngram_size
        self.similarity_calculator = TextSimilarity()
        self.ngram_analyzer = NGramAnalyzer(n=ngram_size)
        self.citation_verifier = CitationVerifier()
        self.originality_scorer = OriginalityScorer()

    def check(
        self,
        text: str,
        reference_texts: Optional[list] = None,
        algorithm: str = "combined",
    ) -> OriginalityReport:
        """执行抄袭检测。

        Args:
            text: 待检测文本。
            reference_texts: 参考文献文本列表。
            algorithm: 相似度算法。

        Returns:
            OriginalityReport 实例。
        """
        return self.originality_scorer.score(
            text,
            reference_texts=reference_texts,
            similarity_threshold=self.similarity_threshold,
        )

    def quick_check(self, text1: str, text2: str, algorithm: str = "combined") -> float:
        """快速检查两段文本的相似度。

        Args:
            text1: 文本1。
            text2: 文本2。
            algorithm: 算法。

        Returns:
            相似度分数（0.0 - 1.0）。
        """
        result = TextSimilarity.calculate(text1, text2, algorithm=algorithm)
        return result.score

    def batch_check(self, text: str, reference_texts: list) -> list:
        """批量检查文本与多篇参考文献的相似度。

        Args:
            text: 待检测文本。
            reference_texts: 参考文献列表。

        Returns:
            相似度结果列表。
        """
        results = []
        for i, ref in enumerate(reference_texts):
            result = TextSimilarity.combined_similarity(text, ref)
            results.append({
                "reference_index": i,
                "similarity": result.score,
                "details": result.details,
            })
        # 按相似度降序排序
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results

    def find_similar_sources(
        self,
        text: str,
        reference_texts: list,
        top_k: int = 5,
    ) -> list:
        """查找最相似的来源。

        Args:
            text: 待检测文本。
            reference_texts: 参考文献列表。
            top_k: 返回前 K 个。

        Returns:
            最相似来源列表。
        """
        batch_results = self.batch_check(text, reference_texts)
        return batch_results[:top_k]

    def get_text_fingerprint(self, text: str) -> str:
        """获取文本指纹（用于快速比对）。

        Args:
            text: 文本。

        Returns:
            指纹哈希字符串。
        """
        ngrams = _generate_ngrams(text, self.ngram_size)
        # 取所有 n-gram 的哈希，然后合并
        hashes = []
        for ng in ngrams:
            hashes.append(hashlib.md5(ng.encode("utf-8")).hexdigest()[:8])
        # 合并为指纹
        fingerprint_input = "".join(sorted(hashes))
        return hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:32]

    def compare_fingerprints(self, fp1: str, fp2: str) -> float:
        """比较两个文本指纹的相似度。

        Args:
            fp1: 指纹1。
            fp2: 指纹2。

        Returns:
            相似度（0.0 - 1.0）。
        """
        if not fp1 or not fp2:
            return 0.0
        if fp1 == fp2:
            return 1.0
        # 汉明距离
        min_len = min(len(fp1), len(fp2))
        matching = sum(1 for i in range(min_len) if fp1[i] == fp2[i])
        return matching / max(len(fp1), len(fp2))


# ===== 便捷函数 =====


def check_plagiarism(text: str, reference_texts: Optional[list] = None) -> OriginalityReport:
    """便捷函数：执行抄袭检测。"""
    checker = PlagiarismChecker()
    return checker.check(text, reference_texts=reference_texts)


def calculate_similarity(text1: str, text2: str, algorithm: str = "combined") -> float:
    """便捷函数：计算相似度。"""
    return TextSimilarity.calculate(text1, text2, algorithm=algorithm).score


def analyze_ngrams(text: str, n: int = 3) -> dict:
    """便捷函数：n-gram 分析。"""
    return NGramAnalyzer(n=n).analyze(text)


def get_text_fingerprint(text: str, n: int = 5) -> str:
    """便捷函数：获取文本指纹。"""
    return PlagiarismChecker(ngram_size=n).get_text_fingerprint(text)
