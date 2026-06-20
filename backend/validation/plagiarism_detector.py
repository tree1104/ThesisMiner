"""抄袭检测器模块

提供完整的多算法抄袭检测，包括：
    - 文本指纹（SimHash / MinHash）
    - n-gram 匹配
    - 句子级比对
    - 本地数据库比对
    - 网络搜索比对（模拟）
    - 引用识别与排除
    - 抄袭报告生成、相似段落标注、来源追溯
    - 批量检测、增量检测、定时检测

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可配置：阈值、算法权重均可调整
    4. 可扩展：支持新增比对算法
"""
from __future__ import annotations

import hashlib
import math
import re
import threading
import uuid
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Iterable, Optional


# ===== 常量 =====


# 默认相似度阈值
DEFAULT_SIMILARITY_THRESHOLD = 0.3

# 严重抄袭阈值
CRITICAL_PLAGIARISM_THRESHOLD = 0.5

# n-gram 默认大小
DEFAULT_NGRAM_SIZE = 3

# SimHash 位数
SIMHASH_BITS = 64

# MinHash 哈希函数数量
MINHASH_NUM_HASHES = 128

# 句子最小长度（短于此不参与比对）
MIN_SENTENCE_LENGTH = 10

# 引用识别正则
CITATION_PATTERNS = [
    re.compile(r"\([^)]*\d{4}[^)]*\)"),  # (Author, 2020)
    re.compile(r"（[^）]*\d{4}[^）]*）"),  # 中文括号
    re.compile(r"\[\d+\]"),               # [1]
    re.compile(r"\[\d+[-,;\s\d]+\]"),     # [1, 2, 3]
    re.compile(r"[A-Z][a-z]+\s+et\s+al\.?,?\s*\d{4}"),  # Smith et al., 2020
]

# 严重级别
SEVERITY_LEVELS = {
    "none": "无抄袭",
    "low": "轻度相似",
    "medium": "中度相似",
    "high": "高度相似",
    "critical": "严重抄袭",
}


# ===== 数据结构 =====


@dataclass
class PlagiarismMatch:
    """抄袭匹配片段。

    Attributes:
        id: 匹配 ID。
        source_text: 源文本片段。
        target_text: 目标文本片段。
        similarity: 相似度（0-1）。
        source_start: 源文本起始位置。
        source_end: 源文本结束位置。
        target_start: 目标文本起始位置。
        target_end: 目标文本结束位置。
        source_reference: 源引用信息。
        algorithm: 检测算法。
        is_citation: 是否为引用（已排除）。
    """

    id: str = ""
    source_text: str = ""
    target_text: str = ""
    similarity: float = 0.0
    source_start: int = 0
    source_end: int = 0
    target_start: int = 0
    target_end: int = 0
    source_reference: str = ""
    algorithm: str = ""
    is_citation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlagiarismReport:
    """抄袭检测报告。

    Attributes:
        id: 报告 ID。
        document_id: 文档 ID。
        timestamp: 检测时间。
        overall_similarity: 总体相似度（0-1）。
        matches: 匹配片段列表。
        source_count: 来源数量。
        citation_count: 引用数量（已排除）。
        severity: 严重级别。
        is_plagiarized: 是否构成抄袭。
        algorithm_stats: 各算法统计。
        recommendations: 建议。
        metadata: 元数据。
    """

    id: str = ""
    document_id: str = ""
    timestamp: str = ""
    overall_similarity: float = 0.0
    matches: list[PlagiarismMatch] = field(default_factory=list)
    source_count: int = 0
    citation_count: int = 0
    severity: str = "none"
    is_plagiarized: bool = False
    algorithm_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "timestamp": self.timestamp,
            "overall_similarity": round(self.overall_similarity, 4),
            "matches": [m.to_dict() for m in self.matches],
            "source_count": self.source_count,
            "citation_count": self.citation_count,
            "severity": self.severity,
            "is_plagiarized": self.is_plagiarized,
            "algorithm_stats": self.algorithm_stats,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }


@dataclass
class DocumentRecord:
    """文档记录（用于本地数据库比对）。

    Attributes:
        id: 文档 ID。
        title: 标题。
        content: 内容。
        source: 来源。
        author: 作者。
        year: 年份。
        simhash: SimHash 指纹。
        minhash: MinHash 签名。
        ngrams: n-gram 集合。
        created_at: 创建时间。
    """

    id: str = ""
    title: str = ""
    content: str = ""
    source: str = ""
    author: str = ""
    year: int = 0
    simhash: int = 0
    minhash: list[int] = field(default_factory=list)
    ngrams: set[str] = field(default_factory=set)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "author": self.author,
            "year": self.year,
            "simhash": self.simhash,
            "minhash": self.minhash,
            "ngrams_count": len(self.ngrams),
            "created_at": self.created_at,
        }


# ===== 工具函数 =====


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串。"""
    return datetime.now().isoformat()


def _new_id(prefix: str = "match") -> str:
    """生成带前缀的唯一 ID。"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _tokenize(text: str) -> list[str]:
    """中英文混合分词。"""
    if not text:
        return []
    tokens: list[str] = []
    en_words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", text.lower())
    tokens.extend(en_words)
    cn_chars = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(cn_chars) - 1):
        tokens.append(cn_chars[i] + cn_chars[i + 1])
    tokens.extend(cn_chars)
    return tokens


def _split_sentences(text: str) -> list[tuple[int, int, str]]:
    """分割句子。

    Args:
        text: 待分割文本。

    Returns:
        (start, end, sentence) 元组列表。
    """
    if not text:
        return []
    sentences: list[tuple[int, int, str]] = []
    # 按中英文句号、问号、感叹号、换行分割
    pattern = re.compile(r"[。！？\.\!\?\n]+")
    last_end = 0
    for match in pattern.finditer(text):
        end = match.end()
        sentence = text[last_end:end].strip()
        if sentence and len(sentence) >= MIN_SENTENCE_LENGTH:
            sentences.append((last_end, end, sentence))
        last_end = end
    # 处理最后一段
    if last_end < len(text):
        sentence = text[last_end:].strip()
        if sentence and len(sentence) >= MIN_SENTENCE_LENGTH:
            sentences.append((last_end, len(text), sentence))
    return sentences


def _remove_citations(text: str) -> tuple[str, list[tuple[int, int, str]]]:
    """移除引用标记。

    Args:
        text: 原始文本。

    Returns:
        (清理后文本, 引用位置列表) 元组。
    """
    citations: list[tuple[int, int, str]] = []
    for pattern in CITATION_PATTERNS:
        for match in pattern.finditer(text):
            citations.append((match.start(), match.end(), match.group()))
    # 按位置排序
    citations.sort(key=lambda x: x[0])
    # 构建清理后文本
    if not citations:
        return text, []
    result_parts: list[str] = []
    last_end = 0
    for start, end, cite in citations:
        result_parts.append(text[last_end:start])
        last_end = end
    result_parts.append(text[last_end:])
    return "".join(result_parts), citations


def _hamming_distance(a: int, b: int, bits: int = SIMHASH_BITS) -> int:
    """计算两个整数的汉明距离。"""
    xor = a ^ b
    distance = 0
    while xor and distance < bits:
        distance += xor & 1
        xor >>= 1
    return distance


# ===== SimHash 实现 =====


class SimHash:
    """SimHash 文本指纹算法。

    将文本映射为固定长度的指纹，相似文本的指纹汉明距离小。
    适用于大规模文档快速去重。
    """

    def __init__(self, bits: int = SIMHASH_BITS) -> None:
        """初始化 SimHash。

        Args:
            bits: 指纹位数。
        """
        self._bits = bits

    def compute(self, text: str) -> int:
        """计算文本的 SimHash 指纹。

        Args:
            text: 待计算文本。

        Returns:
            SimHash 指纹（整数）。
        """
        if not text:
            return 0
        tokens = _tokenize(text)
        if not tokens:
            return 0
        # 统计词频
        freq = Counter(tokens)
        # 初始化权重向量
        vector = [0] * self._bits
        for token, weight in freq.items():
            # 计算 token 的哈希
            token_hash = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            # 对每一位加权
            for i in range(self._bits):
                bit = (token_hash >> i) & 1
                if bit:
                    vector[i] += weight
                else:
                    vector[i] -= weight
        # 生成指纹
        fingerprint = 0
        for i in range(self._bits):
            if vector[i] > 0:
                fingerprint |= (1 << i)
        return fingerprint

    def similarity(self, hash1: int, hash2: int) -> float:
        """计算两个指纹的相似度。

        Args:
            hash1: 指纹1。
            hash2: 指纹2。

        Returns:
            相似度（0-1）。
        """
        if hash1 == 0 and hash2 == 0:
            return 0.0
        distance = _hamming_distance(hash1, hash2, self._bits)
        return 1.0 - distance / self._bits


# ===== MinHash 实现 =====


class MinHash:
    """MinHash 文本签名算法。

    通过多个哈希函数生成签名，用于估算 Jaccard 相似度。
    适用于集合相似度计算。
    """

    def __init__(self, num_hashes: int = MINHASH_NUM_HASHES) -> None:
        """初始化 MinHash。

        Args:
            num_hashes: 哈希函数数量。
        """
        self._num_hashes = num_hashes
        # 生成随机种子（基于固定种子保证可重复）
        self._seeds = [
            int(hashlib.md5(f"seed_{i}".encode()).hexdigest()[:8], 16)
            for i in range(num_hashes)
        ]

    def compute(self, text: str) -> list[int]:
        """计算文本的 MinHash 签名。

        Args:
            text: 待计算文本。

        Returns:
            MinHash 签名列表。
        """
        tokens = set(_tokenize(text))
        if not tokens:
            return [0] * self._num_hashes
        signature: list[int] = []
        for seed in self._seeds:
            min_hash = float("inf")
            for token in tokens:
                # 组合 seed 与 token 计算哈希
                combined = f"{seed}:{token}"
                h = int(hashlib.md5(combined.encode("utf-8")).hexdigest(), 16)
                if h < min_hash:
                    min_hash = h
            signature.append(int(min_hash) if min_hash != float("inf") else 0)
        return signature

    def similarity(self, sig1: list[int], sig2: list[int]) -> float:
        """计算两个签名的相似度（估算 Jaccard）。

        Args:
            sig1: 签名1。
            sig2: 签名2。

        Returns:
            相似度（0-1）。
        """
        if not sig1 or not sig2:
            return 0.0
        min_len = min(len(sig1), len(sig2))
        if min_len == 0:
            return 0.0
        matches = sum(1 for i in range(min_len) if sig1[i] == sig2[i])
        return matches / min_len


# ===== N-gram 分析器 =====


class NGramAnalyzer:
    """n-gram 分析器。

    提取文本的 n-gram 集合，用于精确匹配。
    """

    def __init__(self, n: int = DEFAULT_NGRAM_SIZE) -> None:
        """初始化 n-gram 分析器。

        Args:
            n: n-gram 大小。
        """
        self._n = max(2, n)

    def extract(self, text: str) -> set[str]:
        """提取文本的 n-gram 集合。

        Args:
            text: 待分析文本。

        Returns:
            n-gram 字符串集合。
        """
        if not text:
            return set()
        # 清理文本（去除空白）
        cleaned = re.sub(r"\s+", "", text)
        if len(cleaned) < self._n:
            return {cleaned} if cleaned else set()
        ngrams: set[str] = set()
        for i in range(len(cleaned) - self._n + 1):
            ngrams.add(cleaned[i: i + self._n])
        return ngrams

    def jaccard_similarity(self, set1: set[str], set2: set[str]) -> float:
        """计算两个 n-gram 集合的 Jaccard 相似度。"""
        if not set1 and not set2:
            return 0.0
        union = set1 | set2
        if not union:
            return 0.0
        return len(set1 & set2) / len(union)

    def containment_ratio(self, subset: set[str], superset: set[str]) -> float:
        """计算包含率（subset 中有多少在 superset 中）。"""
        if not subset:
            return 0.0
        return len(subset & superset) / len(subset)

    def find_overlapping_ngrams(self, set1: set[str], set2: set[str]) -> set[str]:
        """找出重叠的 n-gram。"""
        return set1 & set2


# ===== 句子比对器 =====


class SentenceComparator:
    """句子级比对器。

    对文档进行句子分割，逐句计算相似度。
    """

    def __init__(self, threshold: float = 0.5) -> None:
        """初始化句子比对器。

        Args:
            threshold: 句子相似度阈值。
        """
        self._threshold = threshold

    def compare(self, text1: str, text2: str) -> list[tuple[int, int, str, str, float]]:
        """比对两个文本的句子。

        Args:
            text1: 源文本。
            text2: 目标文本。

        Returns:
            (src_start, src_end, src_sentence, tgt_sentence, similarity) 元组列表。
        """
        sentences1 = _split_sentences(text1)
        sentences2 = _split_sentences(text2)
        if not sentences1 or not sentences2:
            return []
        results: list[tuple[int, int, str, str, float]] = []
        for s1_start, s1_end, s1 in sentences1:
            best_match: Optional[tuple[str, float]] = None
            for _, _, s2 in sentences2:
                sim = self._compute_sentence_similarity(s1, s2)
                if sim >= self._threshold:
                    if best_match is None or sim > best_match[1]:
                        best_match = (s2, sim)
            if best_match:
                results.append((s1_start, s1_end, s1, best_match[0], best_match[1]))
        return results

    def _compute_sentence_similarity(self, s1: str, s2: str) -> float:
        """计算两个句子的相似度。

        综合使用字符级 Jaccard 与编辑距离。

        Args:
            s1: 句子1。
            s2: 句子2。

        Returns:
            相似度（0-1）。
        """
        if not s1 or not s2:
            return 0.0
        # 字符级 Jaccard
        chars1 = set(s1)
        chars2 = set(s2)
        jaccard = len(chars1 & chars2) / len(chars1 | chars2) if (chars1 | chars2) else 0.0
        # 编辑距离相似度
        edit_sim = self._edit_distance_similarity(s1, s2)
        # 加权融合
        return 0.4 * jaccard + 0.6 * edit_sim

    def _edit_distance_similarity(self, s1: str, s2: str) -> float:
        """基于编辑距离的相似度。"""
        if not s1 and not s2:
            return 1.0
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0
        distance = self._levenshtein(s1, s2)
        return 1.0 - distance / max_len

    def _levenshtein(self, s1: str, s2: str) -> int:
        """计算编辑距离。"""
        if len(s1) < len(s2):
            return self._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]


# ===== 抄袭检测器主类 =====


class PlagiarismDetector:
    """抄袭检测器主类。

    整合多种检测算法，提供：
        - SimHash / MinHash 指纹比对
        - n-gram 精确匹配
        - 句子级比对
        - 本地数据库比对
        - 网络搜索比对（模拟）
        - 引用识别与排除
        - 抄袭报告生成
        - 批量检测、增量检测

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self, similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
                 ngram_size: int = DEFAULT_NGRAM_SIZE) -> None:
        """初始化抄袭检测器。

        Args:
            similarity_threshold: 相似度阈值。
            ngram_size: n-gram 大小。
        """
        self._lock = threading.RLock()
        self._threshold = similarity_threshold
        self._simhash = SimHash()
        self._minhash = MinHash()
        self._ngram = NGramAnalyzer(ngram_size)
        self._sentence_comparator = SentenceComparator(threshold=similarity_threshold)
        # 本地文档库：doc_id -> DocumentRecord
        self._documents: dict[str, DocumentRecord] = {}
        # SimHash 索引：simhash -> set of doc_id
        self._simhash_index: dict[int, set[str]] = defaultdict(set)
        # 检测历史
        self._history: list[PlagiarismReport] = []
        # 算法权重
        self._algorithm_weights = {
            "simhash": 0.2,
            "minhash": 0.2,
            "ngram": 0.3,
            "sentence": 0.3,
        }

    # ===== 文档库管理 =====

    def add_document(self, doc_id: str, title: str, content: str,
                     source: str = "", author: str = "", year: int = 0) -> str:
        """添加文档到本地库。

        Args:
            doc_id: 文档 ID（为空则自动生成）。
            title: 标题。
            content: 内容。
            source: 来源。
            author: 作者。
            year: 年份。

        Returns:
            文档 ID。
        """
        if not doc_id:
            doc_id = _new_id("doc")
        with self._lock:
            # 移除引用后计算指纹
            clean_content, _ = _remove_citations(content)
            simhash = self._simhash.compute(clean_content)
            minhash = self._minhash.compute(clean_content)
            ngrams = self._ngram.extract(clean_content)
            record = DocumentRecord(
                id=doc_id,
                title=title,
                content=content,
                source=source,
                author=author,
                year=year,
                simhash=simhash,
                minhash=minhash,
                ngrams=ngrams,
                created_at=_now_iso(),
            )
            self._documents[doc_id] = record
            self._simhash_index[simhash].add(doc_id)
            return doc_id

    def remove_document(self, doc_id: str) -> bool:
        """移除文档。"""
        with self._lock:
            record = self._documents.pop(doc_id, None)
            if record is None:
                return False
            self._simhash_index[record.simhash].discard(doc_id)
            if not self._simhash_index[record.simhash]:
                del self._simhash_index[record.simhash]
            return True

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        """获取文档。"""
        with self._lock:
            return self._documents.get(doc_id)

    def list_documents(self) -> list[DocumentRecord]:
        """列出所有文档。"""
        with self._lock:
            return list(self._documents.values())

    def document_count(self) -> int:
        """返回文档数量。"""
        with self._lock:
            return len(self._documents)

    # ===== 检测接口 =====

    def detect(self, text: str, document_id: str = "",
               compare_with: Optional[list[str]] = None,
               exclude_citations: bool = True,
               algorithms: Optional[list[str]] = None) -> PlagiarismReport:
        """执行抄袭检测。

        Args:
            text: 待检测文本。
            document_id: 文档 ID（用于报告标识）。
            compare_with: 指定比对的文档 ID 列表。None 表示比对全部。
            exclude_citations: 是否排除引用。
            algorithms: 使用的算法列表。None 表示全部。

        Returns:
            抄袭检测报告。
        """
        with self._lock:
            report = PlagiarismReport(
                id=_new_id("report"),
                document_id=document_id,
                timestamp=_now_iso(),
            )
            if not text or not text.strip():
                report.recommendations = ["待检测文本为空"]
                return report
            # 预处理：移除引用
            clean_text = text
            citations: list[tuple[int, int, str]] = []
            if exclude_citations:
                clean_text, citations = _remove_citations(text)
                report.citation_count = len(citations)
            # 计算待检测文本的指纹
            query_simhash = self._simhash.compute(clean_text)
            query_minhash = self._minhash.compute(clean_text)
            query_ngrams = self._ngram.extract(clean_text)
            # 确定比对范围
            if compare_with:
                target_docs = [
                    self._documents[did] for did in compare_with
                    if did in self._documents
                ]
            else:
                target_docs = list(self._documents.values())
            # 执行各算法检测
            all_matches: list[PlagiarismMatch] = []
            algorithm_results: dict[str, list[float]] = defaultdict(list)
            target_algorithms = algorithms or list(self._algorithm_weights.keys())
            for doc in target_docs:
                # SimHash 比对
                if "simhash" in target_algorithms:
                    sim = self._simhash.similarity(query_simhash, doc.simhash)
                    algorithm_results["simhash"].append(sim)
                    if sim >= self._threshold:
                        all_matches.append(PlagiarismMatch(
                            id=_new_id(),
                            source_text=clean_text[:200],
                            target_text=doc.content[:200],
                            similarity=sim,
                            source_reference=f"{doc.title} ({doc.author}, {doc.year})",
                            algorithm="simhash",
                        ))
                # MinHash 比对
                if "minhash" in target_algorithms:
                    sim = self._minhash.similarity(query_minhash, doc.minhash)
                    algorithm_results["minhash"].append(sim)
                    if sim >= self._threshold:
                        all_matches.append(PlagiarismMatch(
                            id=_new_id(),
                            source_text=clean_text[:200],
                            target_text=doc.content[:200],
                            similarity=sim,
                            source_reference=f"{doc.title} ({doc.author}, {doc.year})",
                            algorithm="minhash",
                        ))
                # n-gram 比对
                if "ngram" in target_algorithms:
                    overlap = self._ngram.find_overlapping_ngrams(query_ngrams, doc.ngrams)
                    if overlap:
                        containment = len(overlap) / len(query_ngrams) if query_ngrams else 0
                        jaccard = len(overlap) / len(query_ngrams | doc.ngrams) if (query_ngrams | doc.ngrams) else 0
                        sim = max(containment, jaccard)
                        algorithm_results["ngram"].append(sim)
                        if sim >= self._threshold:
                            # 找出具体匹配片段
                            matched_text = self._extract_matched_text(clean_text, overlap)
                            all_matches.append(PlagiarismMatch(
                                id=_new_id(),
                                source_text=matched_text[:200],
                                target_text=doc.content[:200],
                                similarity=sim,
                                source_reference=f"{doc.title} ({doc.author}, {doc.year})",
                                algorithm="ngram",
                            ))
                # 句子级比对
                if "sentence" in target_algorithms:
                    sentence_matches = self._sentence_comparator.compare(clean_text, doc.content)
                    for s_start, s_end, s1, s2, sim in sentence_matches:
                        algorithm_results["sentence"].append(sim)
                        if sim >= self._threshold:
                            all_matches.append(PlagiarismMatch(
                                id=_new_id(),
                                source_text=s1,
                                target_text=s2,
                                similarity=sim,
                                source_start=s_start,
                                source_end=s_end,
                                source_reference=f"{doc.title} ({doc.author}, {doc.year})",
                                algorithm="sentence",
                            ))
            # 去重与合并匹配
            all_matches = self._merge_matches(all_matches)
            # 计算总体相似度
            report.matches = all_matches
            report.overall_similarity = self._compute_overall_similarity(
                algorithm_results, len(clean_text)
            )
            report.source_count = len({m.source_reference for m in all_matches})
            # 严重级别
            report.severity = self._determine_severity(report.overall_similarity)
            report.is_plagiarized = report.overall_similarity >= CRITICAL_PLAGIARISM_THRESHOLD
            # 算法统计
            report.algorithm_stats = self._compute_algorithm_stats(algorithm_results)
            # 建议
            report.recommendations = self._generate_recommendations(report)
            # 保存历史
            self._history.append(report)
            return report

    def _extract_matched_text(self, text: str, ngrams: set[str]) -> str:
        """从文本中提取匹配 n-gram 所在的片段。"""
        if not ngrams:
            return ""
        # 找出第一个匹配的位置
        cleaned = re.sub(r"\s+", "", text)
        for i in range(len(cleaned) - self._ngram._n + 1):
            gram = cleaned[i: i + self._ngram._n]
            if gram in ngrams:
                # 返回前后各50字符的上下文
                start = max(0, i - 50)
                end = min(len(cleaned), i + self._ngram._n + 50)
                return cleaned[start:end]
        return ""

    def _merge_matches(self, matches: list[PlagiarismMatch]) -> list[PlagiarismMatch]:
        """合并重叠的匹配片段。"""
        if not matches:
            return []
        # 按相似度降序排序
        sorted_matches = sorted(matches, key=lambda x: x.similarity, reverse=True)
        # 简单去重：相同 source_reference + algorithm 只保留最高分
        seen: set[tuple[str, str]] = set()
        merged: list[PlagiarismMatch] = []
        for match in sorted_matches:
            key = (match.source_reference, match.algorithm)
            if key in seen:
                continue
            seen.add(key)
            merged.append(match)
        return merged

    def _compute_overall_similarity(self, algorithm_results: dict[str, list[float]],
                                    text_length: int) -> float:
        """计算总体相似度。

        基于各算法的最大相似度，按权重加权。

        Args:
            algorithm_results: 各算法的相似度列表。
            text_length: 文本长度。

        Returns:
            总体相似度（0-1）。
        """
        if not algorithm_results:
            return 0.0
        weighted_sum = 0.0
        total_weight = 0.0
        for algo, sims in algorithm_results.items():
            if not sims:
                continue
            max_sim = max(sims)
            weight = self._algorithm_weights.get(algo, 0.1)
            weighted_sum += max_sim * weight
            total_weight += weight
        if total_weight == 0:
            return 0.0
        return weighted_sum / total_weight

    def _determine_severity(self, similarity: float) -> str:
        """确定严重级别。"""
        if similarity >= 0.7:
            return "critical"
        elif similarity >= 0.5:
            return "high"
        elif similarity >= 0.3:
            return "medium"
        elif similarity >= 0.1:
            return "low"
        else:
            return "none"

    def _compute_algorithm_stats(self, algorithm_results: dict[str, list[float]]) -> dict[str, dict[str, Any]]:
        """计算各算法统计。"""
        stats: dict[str, dict[str, Any]] = {}
        for algo, sims in algorithm_results.items():
            if not sims:
                stats[algo] = {
                    "count": 0,
                    "max": 0.0,
                    "avg": 0.0,
                    "above_threshold": 0,
                }
                continue
            stats[algo] = {
                "count": len(sims),
                "max": round(max(sims), 4),
                "avg": round(sum(sims) / len(sims), 4),
                "above_threshold": sum(1 for s in sims if s >= self._threshold),
            }
        return stats

    def _generate_recommendations(self, report: PlagiarismReport) -> list[str]:
        """生成建议。"""
        recommendations: list[str] = []
        if report.is_plagiarized:
            recommendations.append(
                f"⚠ 检测到严重抄袭（相似度{report.overall_similarity:.1%}），需大幅改写"
            )
        elif report.overall_similarity >= 0.3:
            recommendations.append(
                f"存在中度相似（{report.overall_similarity:.1%}），建议改写相似段落"
            )
        elif report.overall_similarity >= 0.1:
            recommendations.append(
                f"存在轻度相似（{report.overall_similarity:.1%}），注意规范引用"
            )
        else:
            recommendations.append("✓ 未检测到明显抄袭")
        # 针对匹配的建议
        if report.matches:
            top_match = max(report.matches, key=lambda x: x.similarity)
            recommendations.append(
                f"最高相似度片段来自：{top_match.source_reference}（{top_match.similarity:.1%}）"
            )
        # 引用相关
        if report.citation_count > 0:
            recommendations.append(
                f"已识别并排除{report.citation_count}处引用标记"
            )
        # 算法建议
        for algo, stats in report.algorithm_stats.items():
            if stats.get("above_threshold", 0) > 0:
                algo_names = {
                    "simhash": "SimHash指纹",
                    "minhash": "MinHash签名",
                    "ngram": "n-gram匹配",
                    "sentence": "句子比对",
                }
                recommendations.append(
                    f"{algo_names.get(algo, algo)}检测到{stats['above_threshold']}处相似"
                )
        return recommendations

    # ===== 批量检测 =====

    def detect_batch(self, documents: list[dict[str, Any]],
                     exclude_citations: bool = True) -> list[PlagiarismReport]:
        """批量检测多个文档。

        Args:
            documents: 文档列表，每项含 text, document_id 等。
            exclude_citations: 是否排除引用。

        Returns:
            检测报告列表。
        """
        with self._lock:
            reports: list[PlagiarismReport] = []
            for doc in documents:
                text = doc.get("text", "")
                doc_id = doc.get("document_id", "")
                report = self.detect(text, doc_id, exclude_citations=exclude_citations)
                reports.append(report)
            return reports

    def detect_incremental(self, text: str, document_id: str = "",
                           new_documents: Optional[list[dict[str, Any]]] = None) -> PlagiarismReport:
        """增量检测：仅比对新增文档。

        Args:
            text: 待检测文本。
            document_id: 文档 ID。
            new_documents: 新增文档列表。

        Returns:
            检测报告。
        """
        with self._lock:
            # 添加新文档
            new_ids: list[str] = []
            if new_documents:
                for doc in new_documents:
                    doc_id = self.add_document(
                        doc_id=doc.get("id", ""),
                        title=doc.get("title", ""),
                        content=doc.get("content", ""),
                        source=doc.get("source", ""),
                        author=doc.get("author", ""),
                        year=doc.get("year", 0),
                    )
                    new_ids.append(doc_id)
            # 仅比对新增文档
            return self.detect(text, document_id, compare_with=new_ids)

    # ===== 配置 =====

    def set_threshold(self, threshold: float) -> None:
        """设置相似度阈值。"""
        with self._lock:
            self._threshold = max(0.0, min(1.0, threshold))
            self._sentence_comparator._threshold = self._threshold

    def set_algorithm_weights(self, weights: dict[str, float]) -> None:
        """设置算法权重。"""
        with self._lock:
            self._algorithm_weights.update(weights)

    def get_config(self) -> dict[str, Any]:
        """获取当前配置。"""
        with self._lock:
            return {
                "similarity_threshold": self._threshold,
                "ngram_size": self._ngram._n,
                "algorithm_weights": dict(self._algorithm_weights),
                "document_count": len(self._documents),
            }

    # ===== 历史与统计 =====

    def get_history(self, document_id: Optional[str] = None,
                    limit: int = 10) -> list[PlagiarismReport]:
        """获取检测历史。"""
        with self._lock:
            if document_id:
                reports = [r for r in self._history if r.document_id == document_id]
            else:
                reports = list(self._history)
            return reports[-limit:]

    def stats(self) -> dict[str, Any]:
        """返回检测器统计信息。"""
        with self._lock:
            if not self._history:
                return {
                    "total_detections": 0,
                    "avg_similarity": 0.0,
                    "plagiarism_rate": 0.0,
                }
            total = len(self._history)
            avg_sim = sum(r.overall_similarity for r in self._history) / total
            plagiarized = sum(1 for r in self._history if r.is_plagiarized)
            return {
                "total_detections": total,
                "avg_similarity": round(avg_sim, 4),
                "plagiarism_rate": round(plagiarized / total, 4),
                "document_count": len(self._documents),
                "total_matches": sum(len(r.matches) for r in self._history),
            }

    def clear_history(self) -> None:
        """清空检测历史。"""
        with self._lock:
            self._history.clear()

    # ===== 定时检测 =====

    def schedule_detection(self, document_ids: list[str],
                           interval_hours: int = 24) -> dict[str, Any]:
        """配置定时检测任务（模拟）。

        实际生产环境应集成任务调度框架，此处仅记录配置。

        Args:
            document_ids: 待定时检测的文档 ID 列表。
            interval_hours: 检测间隔（小时）。

        Returns:
            调度配置信息。
        """
        with self._lock:
            config = {
                "task_id": _new_id("task"),
                "document_ids": document_ids,
                "interval_hours": interval_hours,
                "created_at": _now_iso(),
                "status": "scheduled",
                "last_run": None,
                "next_run": None,
                "run_count": 0,
            }
            return config

    def run_scheduled_detection(self, document_ids: list[str]) -> list[PlagiarismReport]:
        """执行一次定时检测。

        Args:
            document_ids: 待检测文档 ID 列表。

        Returns:
            检测报告列表。
        """
        with self._lock:
            reports: list[PlagiarismReport] = []
            for doc_id in document_ids:
                doc = self._documents.get(doc_id)
                if doc is None:
                    continue
                # 文档与库内其他文档比对
                other_ids = [d for d in self._documents.keys() if d != doc_id]
                if not other_ids:
                    continue
                report = self.detect(
                    doc.content,
                    document_id=doc_id,
                    compare_with=other_ids,
                )
                reports.append(report)
            return reports

    # ===== 来源追溯 =====

    def trace_source(self, match_id: str,
                     report_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """追溯匹配片段的来源。

        Args:
            match_id: 匹配 ID。
            report_id: 限定报告 ID。

        Returns:
            来源追溯信息。
        """
        with self._lock:
            # 在历史报告中查找
            for report in self._history:
                if report_id and report.id != report_id:
                    continue
                for match in report.matches:
                    if match.id == match_id:
                        # 解析来源引用
                        source_info = self._parse_source_reference(match.source_reference)
                        # 查找原文档
                        source_doc = None
                        for doc in self._documents.values():
                            if source_info.get("title") and source_info["title"] in doc.title:
                                source_doc = doc
                                break
                        return {
                            "match": match.to_dict(),
                            "source_info": source_info,
                            "source_document": source_doc.to_dict() if source_doc else None,
                            "report_id": report.id,
                            "report_timestamp": report.timestamp,
                        }
            return None

    def _parse_source_reference(self, reference: str) -> dict[str, Any]:
        """解析来源引用字符串。

        Args:
            reference: 来源引用字符串（如 "论文标题 (作者, 2020)"）。

        Returns:
            解析后的来源信息字典。
        """
        info: dict[str, Any] = {
            "raw": reference,
            "title": "",
            "author": "",
            "year": 0,
        }
        if not reference:
            return info
        # 提取括号内信息
        match = re.search(r"\(([^)]*)\)", reference)
        if match:
            inner = match.group(1)
            info["title"] = reference[: match.start()].strip()
            # 解析作者与年份
            parts = [p.strip() for p in inner.split(",")]
            for part in parts:
                year = _extract_year(part)
                if year:
                    info["year"] = year
                else:
                    if part:
                        info["author"] = part
        else:
            info["title"] = reference
        return info

    # ===== 相似段落标注 =====

    def annotate_text(self, text: str, report: PlagiarismReport) -> str:
        """在原文中标注相似段落。

        Args:
            text: 原始文本。
            report: 检测报告。

        Returns:
            标注后的文本（使用【】标记相似段落）。
        """
        with self._lock:
            if not report.matches:
                return text
            # 收集所有需要标注的位置区间
            intervals: list[tuple[int, int, float, str]] = []
            for match in report.matches:
                if match.source_start > 0 or match.source_end > 0:
                    intervals.append((
                        match.source_start,
                        match.source_end,
                        match.similarity,
                        match.source_reference,
                    ))
            if not intervals:
                return text
            # 按起始位置排序
            intervals.sort(key=lambda x: x[0])
            # 构建标注文本
            result_parts: list[str] = []
            last_end = 0
            for start, end, sim, ref in intervals:
                if start < last_end:
                    continue  # 跳过重叠区间
                result_parts.append(text[last_end:start])
                result_parts.append(
                    f"【相似度{sim:.0%}，来源：{ref}】"
                    f"{text[start:end]}"
                    f"【标注结束】"
                )
                last_end = end
            result_parts.append(text[last_end:])
            return "".join(result_parts)

    def get_similarity_distribution(self, report: PlagiarismReport) -> dict[str, int]:
        """获取相似度分布统计。

        Args:
            report: 检测报告。

        Returns:
            各相似度区间的匹配数量。
        """
        with self._lock:
            distribution = {
                "0-10%": 0,
                "10-30%": 0,
                "30-50%": 0,
                "50-70%": 0,
                "70-100%": 0,
            }
            for match in report.matches:
                sim = match.similarity
                if sim < 0.1:
                    distribution["0-10%"] += 1
                elif sim < 0.3:
                    distribution["10-30%"] += 1
                elif sim < 0.5:
                    distribution["30-50%"] += 1
                elif sim < 0.7:
                    distribution["50-70%"] += 1
                else:
                    distribution["70-100%"] += 1
            return distribution

    def export_report(self, report: PlagiarismReport, format: str = "dict") -> Any:
        """导出检测报告。

        Args:
            report: 检测报告。
            format: 导出格式（dict/json/text）。

        Returns:
            导出的报告内容。
        """
        with self._lock:
            if format == "dict":
                return report.to_dict()
            elif format == "json":
                import json
                return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
            elif format == "text":
                lines: list[str] = []
                lines.append("=" * 60)
                lines.append("抄袭检测报告")
                lines.append("=" * 60)
                lines.append(f"报告ID: {report.id}")
                lines.append(f"文档ID: {report.document_id}")
                lines.append(f"检测时间: {report.timestamp}")
                lines.append(f"总体相似度: {report.overall_similarity:.2%}")
                lines.append(f"严重级别: {SEVERITY_LEVELS.get(report.severity, report.severity)}")
                lines.append(f"是否抄袭: {'是' if report.is_plagiarized else '否'}")
                lines.append(f"匹配数量: {len(report.matches)}")
                lines.append(f"来源数量: {report.source_count}")
                lines.append(f"引用数量: {report.citation_count}")
                lines.append("")
                lines.append("匹配详情:")
                for i, match in enumerate(report.matches, 1):
                    lines.append(f"  {i}. [{match.algorithm}] 相似度{match.similarity:.2%}")
                    lines.append(f"     来源: {match.source_reference}")
                    lines.append(f"     片段: {match.source_text[:100]}...")
                lines.append("")
                lines.append("建议:")
                for rec in report.recommendations:
                    lines.append(f"  - {rec}")
                lines.append("=" * 60)
                return "\n".join(lines)
            else:
                return report.to_dict()


# ===== 模块级单例 =====


_global_instance: Optional[PlagiarismDetector] = None
_global_lock = threading.Lock()


def get_plagiarism_detector() -> PlagiarismDetector:
    """获取全局抄袭检测器单例。"""
    global _global_instance
    if _global_instance is None:
        with _global_lock:
            if _global_instance is None:
                _global_instance = PlagiarismDetector()
    return _global_instance


def reset_plagiarism_detector() -> None:
    """重置全局单例（主要用于测试）。"""
    global _global_instance
    with _global_lock:
        _global_instance = None
