"""相似度评分器模块

提供多维度相似度计算能力，专门用于学术文本场景，包括：
    - 语义相似度（基于嵌入向量）
    - 字面相似度（基于词频/编辑距离）
    - 结构相似度（基于章节结构对比）
    - 论题相似度（标题+灵感来源+问题意识）
    - 摘要相似度
    - 方法相似度
    - 重复度检测
    - 抄袭检测
    - 原创性评估
    - 批量评分与排名

仅使用 Python 标准库 + 项目内 ml 模块实现，无外部重依赖。

典型用法：
    scorer = SimilarityScorer()
    score = scorer.score_proposal_similarity(prop1, prop2)
    duplicates = scorer.detect_duplicates(proposals, threshold=0.85)
    originality = scorer.assess_originality(target_proposal, reference_proposals)
"""
from __future__ import annotations

import math
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

# 尝试导入项目内模块
try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)

# 尝试导入文本处理器与嵌入引擎
try:
    from backend.ml.text_processor import TextProcessor, get_text_processor

    _HAS_TEXT_PROCESSOR = True
except Exception:  # pragma: no cover
    _HAS_TEXT_PROCESSOR = False
    TextProcessor = None  # type: ignore
    get_text_processor = None  # type: ignore

try:
    from backend.ml.embedding_engine import EmbeddingEngine, get_embedding_engine

    _HAS_EMBEDDING_ENGINE = True
except Exception:  # pragma: no cover
    _HAS_EMBEDDING_ENGINE = False
    EmbeddingEngine = None  # type: ignore
    get_embedding_engine = None  # type: ignore


# ===== 常量定义 =====

# 默认权重配置
DEFAULT_WEIGHTS: Dict[str, float] = {
    "semantic": 0.35,  # 语义相似度
    "literal": 0.25,  # 字面相似度
    "structure": 0.15,  # 结构相似度
    "keyword": 0.15,  # 关键词相似度
    "topic": 0.10,  # 论题相似度
}

# 论题各字段权重
DEFAULT_PROPOSAL_FIELD_WEIGHTS: Dict[str, float] = {
    "title": 0.30,  # 标题
    "inspiration_source": 0.15,  # 灵感来源
    "problem_awareness": 0.20,  # 问题意识
    "research_significance": 0.10,  # 研究意义
    "differentiation": 0.15,  # 差异化/创新点
    "research_content": 0.10,  # 研究内容
}

# 重复度阈值
DEFAULT_DUPLICATE_THRESHOLD = 0.85
DEFAULT_PLAGIARISM_THRESHOLD = 0.70

# 原创性评分阈值
DEFAULT_ORIGINALITY_HIGH = 0.80
DEFAULT_ORIGINALITY_MEDIUM = 0.60
DEFAULT_ORIGINALITY_LOW = 0.40

# N-gram 默认大小
DEFAULT_NGRAM_SIZE = 3

# 默认 Top K
DEFAULT_TOP_K = 10


@dataclass
class SimilarityScore:
    """相似度评分结果。"""

    overall: float = 0.0
    semantic: float = 0.0
    literal: float = 0.0
    structure: float = 0.0
    keyword: float = 0.0
    topic: float = 0.0
    weights: Dict[str, float] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": round(self.overall, 4),
            "semantic": round(self.semantic, 4),
            "literal": round(self.literal, 4),
            "structure": round(self.structure, 4),
            "keyword": round(self.keyword, 4),
            "topic": round(self.topic, 4),
            "weights": self.weights,
            "details": self.details,
        }


@dataclass
class ProposalData:
    """论题提案数据（用于相似度计算）。"""

    title: str = ""
    inspiration_source: str = ""
    problem_awareness: str = ""
    research_significance: str = ""
    literature_review_outline: str = ""
    differentiation: str = ""
    research_content: List[str] = field(default_factory=list)
    feasibility_analysis: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "inspiration_source": self.inspiration_source,
            "problem_awareness": self.problem_awareness,
            "research_significance": self.research_significance,
            "literature_review_outline": self.literature_review_outline,
            "differentiation": self.differentiation,
            "research_content": self.research_content,
            "feasibility_analysis": self.feasibility_analysis,
            "metadata": self.metadata,
        }

    def get_full_text(self) -> str:
        """获取完整文本（拼接所有字段）。"""
        parts = [
            self.title,
            self.inspiration_source,
            self.problem_awareness,
            self.research_significance,
            self.literature_review_outline,
            self.differentiation,
            " ".join(self.research_content),
            self.feasibility_analysis,
        ]
        return " ".join(p for p in parts if p)


@dataclass
class DuplicatePair:
    """重复对。"""

    doc_id_1: str
    doc_id_2: str
    similarity: float
    score_details: Optional[SimilarityScore] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id_1": self.doc_id_1,
            "doc_id_2": self.doc_id_2,
            "similarity": round(self.similarity, 4),
            "score_details": self.score_details.to_dict() if self.score_details else None,
        }


@dataclass
class PlagiarismResult:
    """抄袭检测结果。"""

    target_id: str
    is_plagiarized: bool
    max_similarity: float
    matched_source_id: str = ""
    matched_segments: List[Dict[str, Any]] = field(default_factory=list)
    overall_score: Optional[SimilarityScore] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "is_plagiarized": self.is_plagiarized,
            "max_similarity": round(self.max_similarity, 4),
            "matched_source_id": self.matched_source_id,
            "matched_segments": self.matched_segments,
            "overall_score": self.overall_score.to_dict() if self.overall_score else None,
        }


@dataclass
class OriginalityAssessment:
    """原创性评估结果。"""

    target_id: str
    originality_score: float  # [0, 1]，越高越原创
    level: str  # high / medium / low / very_low
    max_similarity: float
    most_similar_id: str = ""
    similarity_distribution: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "originality_score": round(self.originality_score, 4),
            "level": self.level,
            "max_similarity": round(self.max_similarity, 4),
            "most_similar_id": self.most_similar_id,
            "similarity_distribution": self.similarity_distribution,
            "recommendations": self.recommendations,
        }


@dataclass
class RankingResult:
    """排名结果。"""

    doc_id: str
    score: float
    rank: int
    details: Optional[SimilarityScore] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "score": round(self.score, 4),
            "rank": self.rank,
            "details": self.details.to_dict() if self.details else None,
        }


class SemanticSimilarity:
    """语义相似度计算器

    基于嵌入向量计算文本的语义相似度。
    """

    def __init__(self, embedding_engine: Optional[EmbeddingEngine] = None):
        """初始化。

        Args:
            embedding_engine: 嵌入引擎实例，None 则使用全局单例。
        """
        if embedding_engine:
            self._engine = embedding_engine
        elif _HAS_EMBEDDING_ENGINE:
            try:
                self._engine = get_embedding_engine()
            except Exception:
                self._engine = None
        else:
            self._engine = None

    def compute(self, text1: str, text2: str) -> float:
        """计算语义相似度。"""
        if not text1 or not text2:
            return 0.0
        if self._engine:
            try:
                return self._engine.compute_similarity(text1, text2, metric="cosine")
            except Exception as e:
                _logger.debug(f"嵌入相似度计算失败，降级到字面相似度: {e}")
        # 降级：使用文本处理器
        if _HAS_TEXT_PROCESSOR:
            processor = get_text_processor()
            return processor.cosine_similarity(text1, text2)
        return 0.0

    def compute_batch(
        self, query: str, candidates: List[str]
    ) -> List[float]:
        """批量计算语义相似度。"""
        return [self.compute(query, c) for c in candidates]


class LiteralSimilarity:
    """字面相似度计算器

    基于词频、编辑距离、N-gram 等计算字面相似度。
    """

    def __init__(self, text_processor: Optional[TextProcessor] = None):
        """初始化。"""
        if text_processor:
            self._processor = text_processor
        elif _HAS_TEXT_PROCESSOR:
            self._processor = get_text_processor()
        else:
            self._processor = None

    def compute(self, text1: str, text2: str) -> float:
        """计算字面相似度（综合多种方法）。"""
        if not text1 or not text2:
            return 0.0
        if self._processor:
            cosine = self._processor.cosine_similarity(text1, text2)
            jaccard = self._processor.jaccard_similarity(text1, text2)
            edit = self._processor.edit_distance_ratio(text1, text2)
            ngram = self._processor.ngram_similarity(text1, text2, n=DEFAULT_NGRAM_SIZE)
            # 加权平均
            return (
                cosine * 0.35
                + jaccard * 0.25
                + edit * 0.20
                + ngram * 0.20
            )
        # 降级：简单的字符级 Jaccard
        set1 = set(text1)
        set2 = set(text2)
        if not set1 or not set2:
            return 0.0
        intersection = set1 & set2
        union = set1 | set2
        return len(intersection) / len(union)

    def compute_cosine(self, text1: str, text2: str) -> float:
        """仅计算余弦相似度。"""
        if self._processor:
            return self._processor.cosine_similarity(text1, text2)
        return 0.0

    def compute_jaccard(self, text1: str, text2: str) -> float:
        """仅计算 Jaccard 相似度。"""
        if self._processor:
            return self._processor.jaccard_similarity(text1, text2)
        return 0.0

    def compute_edit(self, text1: str, text2: str) -> float:
        """仅计算编辑距离相似度。"""
        if self._processor:
            return self._processor.edit_distance_ratio(text1, text2)
        return 0.0

    def compute_ngram(self, text1: str, text2: str, n: int = DEFAULT_NGRAM_SIZE) -> float:
        """仅计算 N-gram 相似度。"""
        if self._processor:
            return self._processor.ngram_similarity(text1, text2, n=n)
        return 0.0


class StructureSimilarity:
    """结构相似度计算器

    基于文本结构（章节、段落、句子）计算相似度。
    """

    def __init__(self, text_processor: Optional[TextProcessor] = None):
        """初始化。"""
        if text_processor:
            self._processor = text_processor
        elif _HAS_TEXT_PROCESSOR:
            self._processor = get_text_processor()
        else:
            self._processor = None

    def compute(self, text1: str, text2: str) -> float:
        """计算结构相似度。"""
        if not text1 or not text2:
            return 0.0
        if not self._processor:
            return 0.0
        # 章节结构对比
        sections1 = self._processor.split_by_sections(text1)
        sections2 = self._processor.split_by_sections(text2)
        section_sim = self._compare_sections(sections1, sections2)
        # 段落结构对比
        para1 = self._processor.split_paragraphs(text1)
        para2 = self._processor.split_paragraphs(text2)
        para_sim = self._compare_paragraphs(para1, para2)
        # 句子结构对比
        sent1 = self._processor.split_sentences(text1)
        sent2 = self._processor.split_sentences(text2)
        sent_sim = self._compare_sentences(sent1, sent2)
        # 加权平均
        return section_sim * 0.5 + para_sim * 0.3 + sent_sim * 0.2

    def _compare_sections(
        self, sections1: Dict[str, str], sections2: Dict[str, str]
    ) -> float:
        """对比章节结构。"""
        if not sections1 or not sections2:
            return 0.0
        keys1 = set(sections1.keys())
        keys2 = set(sections2.keys())
        # 章节重合度
        intersection = keys1 & keys2
        union = keys1 | keys2
        key_sim = len(intersection) / len(union) if union else 0.0
        # 重合章节的内容相似度
        content_sims: List[float] = []
        for key in intersection:
            sim = self._processor.cosine_similarity(sections1[key], sections2[key])
            content_sims.append(sim)
        content_sim = sum(content_sims) / len(content_sims) if content_sims else 0.0
        return key_sim * 0.6 + content_sim * 0.4

    def _compare_paragraphs(self, paras1: List, paras2: List) -> float:
        """对比段落结构。"""
        if not paras1 or not paras2:
            return 0.0
        # 段落数量相似度
        count1, count2 = len(paras1), len(paras2)
        max_count = max(count1, count2)
        count_sim = min(count1, count2) / max_count if max_count > 0 else 0.0
        # 段落长度分布相似度
        lengths1 = [len(p.text) for p in paras1]
        lengths2 = [len(p.text) for p in paras2]
        length_sim = self._compare_distributions(lengths1, lengths2)
        return count_sim * 0.5 + length_sim * 0.5

    def _compare_sentences(self, sents1: List, sents2: List) -> float:
        """对比句子结构。"""
        if not sents1 or not sents2:
            return 0.0
        # 句子数量相似度
        count1, count2 = len(sents1), len(sents2)
        max_count = max(count1, count2)
        count_sim = min(count1, count2) / max_count if max_count > 0 else 0.0
        # 句子长度分布相似度
        lengths1 = [len(s.text) for s in sents1]
        lengths2 = [len(s.text) for s in sents2]
        length_sim = self._compare_distributions(lengths1, lengths2)
        return count_sim * 0.5 + length_sim * 0.5

    def _compare_distributions(
        self, dist1: List[float], dist2: List[float]
    ) -> float:
        """对比两个分布的相似度（基于直方图）。"""
        if not dist1 or not dist2:
            return 0.0
        # 计算统计量
        mean1 = sum(dist1) / len(dist1)
        mean2 = sum(dist2) / len(dist2)
        var1 = sum((x - mean1) ** 2 for x in dist1) / len(dist1)
        var2 = sum((x - mean2) ** 2 for x in dist2) / len(dist2)
        std1 = math.sqrt(var1)
        std2 = math.sqrt(var2)
        # 均值相似度
        max_mean = max(mean1, mean2) if max(mean1, mean2) > 0 else 1.0
        mean_sim = 1.0 - abs(mean1 - mean2) / max_mean
        # 标准差相似度
        max_std = max(std1, std2) if max(std1, std2) > 0 else 1.0
        std_sim = 1.0 - abs(std1 - std2) / max_std
        return mean_sim * 0.6 + std_sim * 0.4


class KeywordSimilarity:
    """关键词相似度计算器

    基于关键词重合度计算相似度。
    """

    def __init__(self, text_processor: Optional[TextProcessor] = None):
        """初始化。"""
        if text_processor:
            self._processor = text_processor
        elif _HAS_TEXT_PROCESSOR:
            self._processor = get_text_processor()
        else:
            self._processor = None

    def compute(
        self,
        text1: str,
        text2: str,
        top_k: int = 20,
        method: str = "tfidf",
    ) -> float:
        """计算关键词相似度。"""
        if not text1 or not text2:
            return 0.0
        if not self._processor:
            return 0.0
        # 提取关键词
        keywords1 = self._processor.extract_keywords(text1, top_k=top_k, method=method)
        keywords2 = self._processor.extract_keywords(text2, top_k=top_k, method=method)
        if not keywords1 or not keywords2:
            return 0.0
        # 构建关键词集合
        words1 = {kw.word for kw in keywords1}
        words2 = {kw.word for kw in keywords2}
        # Jaccard 相似度
        intersection = words1 & words2
        union = words1 | words2
        jaccard = len(intersection) / len(union) if union else 0.0
        # 加权重合度（考虑关键词分数）
        scores1 = {kw.word: kw.score for kw in keywords1}
        scores2 = {kw.word: kw.score for kw in keywords2}
        weighted_overlap = 0.0
        total_weight = 0.0
        for word in intersection:
            weighted_overlap += min(scores1[word], scores2[word])
            total_weight += max(scores1[word], scores2[word])
        weighted_sim = weighted_overlap / total_weight if total_weight > 0 else 0.0
        return jaccard * 0.5 + weighted_sim * 0.5

    def get_common_keywords(
        self,
        text1: str,
        text2: str,
        top_k: int = 20,
    ) -> List[str]:
        """获取共同关键词。"""
        if not self._processor:
            return []
        keywords1 = self._processor.extract_keywords(text1, top_k=top_k)
        keywords2 = self._processor.extract_keywords(text2, top_k=top_k)
        words1 = {kw.word for kw in keywords1}
        words2 = {kw.word for kw in keywords2}
        return list(words1 & words2)


class TopicSimilarity:
    """论题相似度计算器

    专门用于论题提案的相似度计算，考虑标题、灵感来源、问题意识等字段。
    """

    def __init__(
        self,
        text_processor: Optional[TextProcessor] = None,
        field_weights: Optional[Dict[str, float]] = None,
    ):
        """初始化。"""
        if text_processor:
            self._processor = text_processor
        elif _HAS_TEXT_PROCESSOR:
            self._processor = get_text_processor()
        else:
            self._processor = None
        self._field_weights = field_weights or DEFAULT_PROPOSAL_FIELD_WEIGHTS

    def compute(self, prop1: ProposalData, prop2: ProposalData) -> float:
        """计算论题相似度。"""
        if not self._processor:
            return 0.0
        # 各字段相似度
        field_sims: Dict[str, float] = {}
        # 标题
        field_sims["title"] = self._compute_field_similarity(
            prop1.title, prop2.title, is_title=True
        )
        # 灵感来源
        field_sims["inspiration_source"] = self._compute_field_similarity(
            prop1.inspiration_source, prop2.inspiration_source
        )
        # 问题意识
        field_sims["problem_awareness"] = self._compute_field_similarity(
            prop1.problem_awareness, prop2.problem_awareness
        )
        # 研究意义
        field_sims["research_significance"] = self._compute_field_similarity(
            prop1.research_significance, prop2.research_significance
        )
        # 差异化
        field_sims["differentiation"] = self._compute_field_similarity(
            prop1.differentiation, prop2.differentiation
        )
        # 研究内容
        content1 = " ".join(prop1.research_content) if prop1.research_content else ""
        content2 = " ".join(prop2.research_content) if prop2.research_content else ""
        field_sims["research_content"] = self._compute_field_similarity(
            content1, content2
        )
        # 加权平均
        total_score = 0.0
        total_weight = 0.0
        for field, weight in self._field_weights.items():
            if field in field_sims:
                total_score += field_sims[field] * weight
                total_weight += weight
        return total_score / total_weight if total_weight > 0 else 0.0

    def _compute_field_similarity(
        self, text1: str, text2: str, is_title: bool = False
    ) -> float:
        """计算单字段相似度。"""
        if not text1 or not text2:
            return 0.0
        if is_title:
            # 标题使用混合相似度（更看重字面）
            return self._processor.hybrid_similarity(
                text1, text2,
                cosine_weight=0.4,
                jaccard_weight=0.4,
                edit_weight=0.2,
            )
        # 其他字段使用余弦相似度
        return self._processor.cosine_similarity(text1, text2)


class SimilarityScorer:
    """相似度评分器（单例）

    整合多种相似度计算器，提供：
        - 多维度相似度评分
        - 论题提案相似度
        - 重复度检测
        - 抄袭检测
        - 原创性评估
        - 批量评分与排名
        - 阈值过滤
    """

    _instance: Optional["SimilarityScorer"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "SimilarityScorer":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """初始化相似度评分器。

        Args:
            weights: 各维度权重，None 则使用默认权重。
        """
        if self._initialized:
            return
        self._initialized = True
        self._weights = dict(weights or DEFAULT_WEIGHTS)
        # 初始化子计算器
        self._semantic = SemanticSimilarity()
        self._literal = LiteralSimilarity()
        self._structure = StructureSimilarity()
        self._keyword = KeywordSimilarity()
        self._topic = TopicSimilarity()
        self._lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> "SimilarityScorer":
        """获取单例实例。"""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（仅用于测试）。"""
        with cls._instance_lock:
            cls._instance = None

    def set_weights(self, weights: Dict[str, float]) -> None:
        """设置权重。"""
        # 归一化
        total = sum(weights.values())
        if total > 0:
            self._weights = {k: v / total for k, v in weights.items()}
        else:
            self._weights = dict(weights)

    def get_weights(self) -> Dict[str, float]:
        """获取当前权重。"""
        return dict(self._weights)

    # ===== 综合相似度评分 =====

    def score(
        self,
        text1: str,
        text2: str,
        include_structure: bool = True,
    ) -> SimilarityScore:
        """计算两段文本的综合相似度。"""
        if not text1 or not text2:
            return SimilarityScore()
        # 计算各维度
        semantic = self._semantic.compute(text1, text2)
        literal = self._literal.compute(text1, text2)
        keyword = self._keyword.compute(text1, text2)
        if include_structure:
            structure = self._structure.compute(text1, text2)
        else:
            structure = 0.0
        # 论题相似度（若文本较长，模拟为论题）
        topic = self._compute_topic_similarity_from_text(text1, text2)
        # 加权平均
        weights = self._weights.copy()
        if not include_structure:
            weights.pop("structure", None)
            # 重新归一化
            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}
        overall = (
            semantic * weights.get("semantic", 0)
            + literal * weights.get("literal", 0)
            + structure * weights.get("structure", 0)
            + keyword * weights.get("keyword", 0)
            + topic * weights.get("topic", 0)
        )
        return SimilarityScore(
            overall=overall,
            semantic=semantic,
            literal=literal,
            structure=structure,
            keyword=keyword,
            topic=topic,
            weights=weights,
            details={
                "text1_length": len(text1),
                "text2_length": len(text2),
            },
        )

    def _compute_topic_similarity_from_text(self, text1: str, text2: str) -> float:
        """从纯文本计算论题相似度（简化版）。"""
        if not self._literal._processor:
            return 0.0
        # 使用混合相似度作为论题相似度
        return self._literal._processor.hybrid_similarity(text1, text2)

    def score_batch(
        self,
        query: str,
        candidates: List[str],
        include_structure: bool = False,
    ) -> List[SimilarityScore]:
        """批量计算相似度。"""
        return [
            self.score(query, c, include_structure=include_structure)
            for c in candidates
        ]

    # ===== 论题提案相似度 =====

    def score_proposal_similarity(
        self,
        prop1: ProposalData,
        prop2: ProposalData,
    ) -> SimilarityScore:
        """计算两个论题提案的相似度。"""
        # 论题字段相似度
        topic_sim = self._topic.compute(prop1, prop2)
        # 全文相似度
        full_text1 = prop1.get_full_text()
        full_text2 = prop2.get_full_text()
        semantic = self._semantic.compute(full_text1, full_text2)
        literal = self._literal.compute(full_text1, full_text2)
        keyword = self._keyword.compute(full_text1, full_text2)
        # 标题特殊处理
        title_sim = self._literal._processor.cosine_similarity(
            prop1.title, prop2.title
        ) if (self._literal._processor and prop1.title and prop2.title) else 0.0
        # 加权
        weights = self._weights.copy()
        overall = (
            semantic * weights.get("semantic", 0)
            + literal * weights.get("literal", 0)
            + keyword * weights.get("keyword", 0)
            + topic_sim * weights.get("topic", 0)
            + title_sim * 0.15  # 标题额外加权
        )
        return SimilarityScore(
            overall=min(overall, 1.0),
            semantic=semantic,
            literal=literal,
            structure=0.0,
            keyword=keyword,
            topic=topic_sim,
            weights=weights,
            details={
                "title_similarity": title_sim,
                "prop1_title": prop1.title,
                "prop2_title": prop2.title,
            },
        )

    def score_proposal_batch(
        self,
        query: ProposalData,
        candidates: List[Tuple[str, ProposalData]],
    ) -> List[Tuple[str, SimilarityScore]]:
        """批量计算论题相似度。"""
        results: List[Tuple[str, SimilarityScore]] = []
        for doc_id, candidate in candidates:
            score = self.score_proposal_similarity(query, candidate)
            results.append((doc_id, score))
        return results

    # ===== 重复度检测 =====

    def detect_duplicates(
        self,
        documents: List[Tuple[str, str]],
        threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
        include_structure: bool = False,
    ) -> List[DuplicatePair]:
        """检测文档列表中的重复对。

        Args:
            documents: (doc_id, text) 列表。
            threshold: 重复阈值。
            include_structure: 是否包含结构相似度。

        Returns:
            重复对列表。
        """
        duplicates: List[DuplicatePair] = []
        n = len(documents)
        for i in range(n):
            for j in range(i + 1, n):
                score = self.score(
                    documents[i][1],
                    documents[j][1],
                    include_structure=include_structure,
                )
                if score.overall >= threshold:
                    duplicates.append(
                        DuplicatePair(
                            doc_id_1=documents[i][0],
                            doc_id_2=documents[j][0],
                            similarity=score.overall,
                            score_details=score,
                        )
                    )
        # 按相似度降序排序
        duplicates.sort(key=lambda d: d.similarity, reverse=True)
        return duplicates

    def detect_proposal_duplicates(
        self,
        proposals: List[Tuple[str, ProposalData]],
        threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
    ) -> List[DuplicatePair]:
        """检测论题提案列表中的重复对。"""
        duplicates: List[DuplicatePair] = []
        n = len(proposals)
        for i in range(n):
            for j in range(i + 1, n):
                score = self.score_proposal_similarity(
                    proposals[i][1], proposals[j][1]
                )
                if score.overall >= threshold:
                    duplicates.append(
                        DuplicatePair(
                            doc_id_1=proposals[i][0],
                            doc_id_2=proposals[j][0],
                            similarity=score.overall,
                            score_details=score,
                        )
                    )
        duplicates.sort(key=lambda d: d.similarity, reverse=True)
        return duplicates

    def find_duplicates_of(
        self,
        target: str,
        candidates: List[Tuple[str, str]],
        threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
    ) -> List[Tuple[str, float, SimilarityScore]]:
        """查找与目标文档重复的候选文档。"""
        results: List[Tuple[str, float, SimilarityScore]] = []
        for doc_id, text in candidates:
            score = self.score(target, text)
            if score.overall >= threshold:
                results.append((doc_id, score.overall, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # ===== 抄袭检测 =====

    def detect_plagiarism(
        self,
        target_text: str,
        target_id: str,
        sources: List[Tuple[str, str]],
        threshold: float = DEFAULT_PLAGIARISM_THRESHOLD,
        segment_length: int = 100,
    ) -> PlagiarismResult:
        """抄袭检测。

        Args:
            target_text: 待检测文本。
            target_id: 待检测文本 ID。
            sources: (source_id, source_text) 列表。
            threshold: 抄袭阈值。
            segment_length: 分段长度（字符数）。

        Returns:
            抄袭检测结果。
        """
        if not target_text or not sources:
            return PlagiarismResult(
                target_id=target_id,
                is_plagiarized=False,
                max_similarity=0.0,
            )
        max_sim = 0.0
        matched_source = ""
        matched_segments: List[Dict[str, Any]] = []
        best_score: Optional[SimilarityScore] = None
        # 分段检测
        target_segments = self._segment_text(target_text, segment_length)
        for source_id, source_text in sources:
            source_segments = self._segment_text(source_text, segment_length)
            for i, t_seg in enumerate(target_segments):
                for j, s_seg in enumerate(source_segments):
                    seg_score = self.score(t_seg, s_seg, include_structure=False)
                    if seg_score.overall >= threshold:
                        matched_segments.append(
                            {
                                "target_segment_index": i,
                                "target_segment": t_seg[:200],
                                "source_id": source_id,
                                "source_segment_index": j,
                                "source_segment": s_seg[:200],
                                "similarity": seg_score.overall,
                            }
                        )
                        if seg_score.overall > max_sim:
                            max_sim = seg_score.overall
                            matched_source = source_id
                            best_score = seg_score
        # 整体相似度
        overall_scores: List[SimilarityScore] = []
        for source_id, source_text in sources:
            score = self.score(target_text, source_text, include_structure=False)
            overall_scores.append(score)
            if score.overall > max_sim:
                max_sim = score.overall
                matched_source = source_id
                best_score = score
        is_plagiarized = max_sim >= threshold
        return PlagiarismResult(
            target_id=target_id,
            is_plagiarized=is_plagiarized,
            max_similarity=max_sim,
            matched_source_id=matched_source,
            matched_segments=matched_segments[:20],  # 限制返回数量
            overall_score=best_score,
        )

    def _segment_text(self, text: str, segment_length: int) -> List[str]:
        """将文本分段。"""
        if not text:
            return []
        if len(text) <= segment_length:
            return [text]
        segments: List[str] = []
        # 按句子边界分段
        if self._literal._processor:
            sentences = self._literal._processor.split_sentences(text)
            current = ""
            for sent in sentences:
                if len(current) + len(sent.text) > segment_length and current:
                    segments.append(current.strip())
                    current = sent.text
                else:
                    current += sent.text
            if current.strip():
                segments.append(current.strip())
        else:
            # 简单按长度切分
            for i in range(0, len(text), segment_length):
                segments.append(text[i : i + segment_length])
        return segments

    # ===== 原创性评估 =====

    def assess_originality(
        self,
        target: ProposalData,
        target_id: str,
        references: List[Tuple[str, ProposalData]],
    ) -> OriginalityAssessment:
        """评估论题提案的原创性。

        Args:
            target: 待评估提案。
            target_id: 待评估提案 ID。
            references: (reference_id, proposal) 参考提案列表。

        Returns:
            原创性评估结果。
        """
        if not references:
            return OriginalityAssessment(
                target_id=target_id,
                originality_score=1.0,
                level="high",
                max_similarity=0.0,
                recommendations=["无参考提案，原创性评估基于目标提案自身。"],
            )
        # 计算与每个参考提案的相似度
        similarities: List[Tuple[str, float, SimilarityScore]] = []
        for ref_id, ref_prop in references:
            score = self.score_proposal_similarity(target, ref_prop)
            similarities.append((ref_id, score.overall, score))
        # 排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        max_sim = similarities[0][1] if similarities else 0.0
        most_similar_id = similarities[0][0] if similarities else ""
        # 原创性分数 = 1 - 最大相似度
        originality_score = max(0.0, 1.0 - max_sim)
        # 分级
        if originality_score >= DEFAULT_ORIGINALITY_HIGH:
            level = "high"
        elif originality_score >= DEFAULT_ORIGINALITY_MEDIUM:
            level = "medium"
        elif originality_score >= DEFAULT_ORIGINALITY_LOW:
            level = "low"
        else:
            level = "very_low"
        # 相似度分布
        distribution: Dict[str, float] = {
            "max": max_sim,
            "min": similarities[-1][1] if similarities else 0.0,
            "avg": sum(s[1] for s in similarities) / len(similarities) if similarities else 0.0,
            "p90": self._percentile([s[1] for s in similarities], 0.9),
        }
        # 生成建议
        recommendations = self._generate_originality_recommendations(
            target, similarities, level
        )
        return OriginalityAssessment(
            target_id=target_id,
            originality_score=originality_score,
            level=level,
            max_similarity=max_sim,
            most_similar_id=most_similar_id,
            similarity_distribution=distribution,
            recommendations=recommendations,
        )

    def _percentile(self, values: List[float], q: float) -> float:
        """计算分位数。"""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        pos = q * (n - 1)
        lower = int(pos)
        upper = min(lower + 1, n - 1)
        frac = pos - lower
        return sorted_vals[lower] * (1 - frac) + sorted_vals[upper] * frac

    def _generate_originality_recommendations(
        self,
        target: ProposalData,
        similarities: List[Tuple[str, float, SimilarityScore]],
        level: str,
    ) -> List[str]:
        """生成原创性改进建议。"""
        recommendations: List[str] = []
        if level == "high":
            recommendations.append("原创性较高，与现有研究差异明显。")
            recommendations.append("建议进一步深化差异化论述，突出创新点。")
        elif level == "medium":
            recommendations.append("原创性中等，与部分参考提案存在相似性。")
            if similarities and similarities[0][2].topic > 0.6:
                recommendations.append("论题相似度较高，建议调整研究方向或问题意识。")
            if similarities and similarities[0][2].literal > 0.6:
                recommendations.append("字面相似度较高，建议重写表述方式。")
            recommendations.append("建议加强差异化论述，明确与现有研究的区别。")
        elif level == "low":
            recommendations.append("原创性较低，与参考提案相似度较高。")
            recommendations.append("强烈建议重新审视研究方向，调整论题。")
            recommendations.append("可尝试跨学科视角或新方法以提升原创性。")
        else:
            recommendations.append("原创性极低，论题与现有研究高度重复。")
            recommendations.append("必须重新选题，避免学术不端风险。")
            recommendations.append("建议从全新角度切入，或更换研究对象。")
        # 基于具体字段的建议
        if similarities:
            top_score = similarities[0][2]
            if top_score.details.get("title_similarity", 0) > 0.7:
                recommendations.append("标题与现有研究过于相似，建议修改标题。")
            if top_score.semantic > 0.7:
                recommendations.append("语义层面相似度较高，建议调整研究内容。")
        return recommendations

    # ===== 排名 =====

    def rank_documents(
        self,
        query: str,
        candidates: List[Tuple[str, str]],
        top_k: int = DEFAULT_TOP_K,
        threshold: float = 0.0,
    ) -> List[RankingResult]:
        """对候选文档按相似度排名。"""
        scored: List[Tuple[str, float, SimilarityScore]] = []
        for doc_id, text in candidates:
            score = self.score(query, text, include_structure=False)
            if score.overall >= threshold:
                scored.append((doc_id, score.overall, score))
        # 排序
        scored.sort(key=lambda x: x[1], reverse=True)
        # 截取 top_k
        results: List[RankingResult] = []
        for rank, (doc_id, score_val, score_obj) in enumerate(scored[:top_k]):
            results.append(
                RankingResult(
                    doc_id=doc_id,
                    score=score_val,
                    rank=rank + 1,
                    details=score_obj,
                )
            )
        return results

    def rank_proposals(
        self,
        query: ProposalData,
        candidates: List[Tuple[str, ProposalData]],
        top_k: int = DEFAULT_TOP_K,
        threshold: float = 0.0,
    ) -> List[RankingResult]:
        """对候选提案按相似度排名。"""
        scored: List[Tuple[str, float, SimilarityScore]] = []
        for doc_id, prop in candidates:
            score = self.score_proposal_similarity(query, prop)
            if score.overall >= threshold:
                scored.append((doc_id, score.overall, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        results: List[RankingResult] = []
        for rank, (doc_id, score_val, score_obj) in enumerate(scored[:top_k]):
            results.append(
                RankingResult(
                    doc_id=doc_id,
                    score=score_val,
                    rank=rank + 1,
                    details=score_obj,
                )
            )
        return results

    # ===== 阈值过滤 =====

    def filter_by_threshold(
        self,
        scores: List[Tuple[str, SimilarityScore]],
        threshold: float,
    ) -> List[Tuple[str, SimilarityScore]]:
        """按阈值过滤相似度结果。"""
        return [(doc_id, score) for doc_id, score in scores if score.overall >= threshold]

    def filter_top_n(
        self,
        scores: List[Tuple[str, SimilarityScore]],
        n: int,
    ) -> List[Tuple[str, SimilarityScore]]:
        """获取 Top N。"""
        sorted_scores = sorted(scores, key=lambda x: x[1].overall, reverse=True)
        return sorted_scores[:n]

    # ===== 摘要与方法相似度 =====

    def score_abstract_similarity(
        self,
        abstract1: str,
        abstract2: str,
    ) -> SimilarityScore:
        """计算摘要相似度。"""
        return self.score(abstract1, abstract2, include_structure=True)

    def score_method_similarity(
        self,
        method1: str,
        method2: str,
    ) -> SimilarityScore:
        """计算方法相似度。"""
        # 方法部分更看重语义与关键词
        weights = {
            "semantic": 0.45,
            "literal": 0.20,
            "structure": 0.10,
            "keyword": 0.25,
            "topic": 0.0,
        }
        old_weights = self._weights
        self._weights = weights
        try:
            return self.score(method1, method2, include_structure=True)
        finally:
            self._weights = old_weights

    # ===== 工具方法 =====

    def compute_text_similarity(
        self,
        text1: str,
        text2: str,
        method: str = "overall",
    ) -> float:
        """计算文本相似度（便捷方法）。

        Args:
            text1: 文本 1。
            text2: 文本 2。
            method: 相似度方法（overall/semantic/literal/keyword/structure）。

        Returns:
            相似度分数。
        """
        if method == "overall":
            return self.score(text1, text2, include_structure=False).overall
        elif method == "semantic":
            return self._semantic.compute(text1, text2)
        elif method == "literal":
            return self._literal.compute(text1, text2)
        elif method == "keyword":
            return self._keyword.compute(text1, text2)
        elif method == "structure":
            return self._structure.compute(text1, text2)
        else:
            return self.score(text1, text2, include_structure=False).overall

    def get_common_keywords(
        self,
        text1: str,
        text2: str,
        top_k: int = 20,
    ) -> List[str]:
        """获取两段文本的共同关键词。"""
        return self._keyword.get_common_keywords(text1, text2, top_k=top_k)

    def explain_similarity(
        self,
        text1: str,
        text2: str,
    ) -> Dict[str, Any]:
        """解释相似度计算结果（用于调试与可视化）。"""
        score = self.score(text1, text2, include_structure=True)
        common_keywords = self.get_common_keywords(text1, text2, top_k=10)
        return {
            "score": score.to_dict(),
            "common_keywords": common_keywords,
            "text1_stats": {
                "length": len(text1),
                "language": self._detect_language(text1),
            },
            "text2_stats": {
                "length": len(text2),
                "language": self._detect_language(text2),
            },
            "interpretation": self._interpret_score(score.overall),
        }

    def _detect_language(self, text: str) -> str:
        """检测语言。"""
        if self._literal._processor:
            return self._literal._processor.detect_language(text)
        return "unknown"

    def _interpret_score(self, score: float) -> str:
        """解释相似度分数。"""
        if score >= 0.9:
            return "高度相似，可能为重复内容"
        elif score >= 0.7:
            return "较高相似度，存在重复风险"
        elif score >= 0.5:
            return "中等相似度，存在关联"
        elif score >= 0.3:
            return "较低相似度，关联较弱"
        else:
            return "低相似度，内容差异较大"

    def shutdown(self) -> None:
        """关闭评分器。"""
        _logger.info("相似度评分器已关闭")


# ===== 模块级便捷函数 =====


_similarity_scorer_instance: Optional[SimilarityScorer] = None
_scorer_lock = threading.Lock()


def get_similarity_scorer() -> SimilarityScorer:
    """获取全局相似度评分器单例。"""
    global _similarity_scorer_instance
    if _similarity_scorer_instance is None:
        with _scorer_lock:
            if _similarity_scorer_instance is None:
                _similarity_scorer_instance = SimilarityScorer()
    return _similarity_scorer_instance


def compute_similarity(text1: str, text2: str) -> float:
    """计算相似度便捷函数。"""
    return get_similarity_scorer().compute_text_similarity(text1, text2)


def check_duplicate(text1: str, text2: str, threshold: float = 0.85) -> bool:
    """检查是否重复便捷函数。"""
    scorer = get_similarity_scorer()
    score = scorer.score(text1, text2, include_structure=False)
    return score.overall >= threshold


def assess_originality(
    target: ProposalData,
    target_id: str,
    references: List[Tuple[str, ProposalData]],
) -> OriginalityAssessment:
    """评估原创性便捷函数。"""
    return get_similarity_scorer().assess_originality(target, target_id, references)


# ===== 单元测试可运行逻辑 =====


def _run_self_test() -> None:
    """模块自检。

    可直接 `python -m backend.ml.similarity_scorer` 运行。
    """
    SimilarityScorer.reset_instance()
    scorer = SimilarityScorer()

    # 测试基础相似度
    text1 = "深度学习在自然语言处理中的应用研究"
    text2 = "自然语言处理中深度学习的应用探索"
    text3 = "区块链技术在金融领域的创新应用"
    score12 = scorer.score(text1, text2, include_structure=False)
    score13 = scorer.score(text1, text3, include_structure=False)
    assert score12.overall > score13.overall
    print(f"相似文本相似度: {score12.overall:.4f}")
    print(f"不同文本相似度: {score13.overall:.4f}")

    # 测试论题相似度
    prop1 = ProposalData(
        title="基于深度学习的中文文本分类研究",
        inspiration_source="受 BERT 模型在 NLP 任务中表现的启发",
        problem_awareness="传统文本分类方法在处理长文本时效果不佳",
        research_significance="提升中文文本分类的准确率",
        differentiation="结合预训练模型与领域适配",
        research_content=["模型设计", "数据集构建", "实验验证"],
    )
    prop2 = ProposalData(
        title="深度学习在中文文本分类中的应用",
        inspiration_source="BERT 等预训练模型在自然语言处理中的成功",
        problem_awareness="现有文本分类方法对长文本处理能力有限",
        research_significance="提高中文文本分类性能",
        differentiation="采用预训练模型与微调策略",
        research_content=["模型架构", "数据准备", "实验评估"],
    )
    prop3 = ProposalData(
        title="区块链技术在供应链管理中的应用",
        inspiration_source="区块链去中心化特性适用于多方协作场景",
        problem_awareness="传统供应链管理存在信任与透明度问题",
        research_significance="提升供应链透明度与效率",
        differentiation="结合智能合约实现自动化",
        research_content=["链上数据管理", "智能合约设计", "性能评估"],
    )
    prop_score = scorer.score_proposal_similarity(prop1, prop2)
    print(f"相似论题相似度: {prop_score.overall:.4f}")
    print(f"  标题相似度: {prop_score.details.get('title_similarity', 0):.4f}")

    prop_score_diff = scorer.score_proposal_similarity(prop1, prop3)
    assert prop_score.overall > prop_score_diff.overall
    print(f"不同论题相似度: {prop_score_diff.overall:.4f}")

    # 测试重复检测
    documents = [
        ("doc1", "深度学习是机器学习的一个分支，通过神经网络学习数据表示。"),
        ("doc2", "深度学习是机器学习的分支，使用神经网络学习数据特征。"),
        ("doc3", "区块链是一种分布式账本技术，用于记录交易数据。"),
        ("doc4", "强化学习通过试错机制学习最优策略。"),
    ]
    duplicates = scorer.detect_duplicates(documents, threshold=0.5)
    print(f"检测到 {len(duplicates)} 对重复文档")
    for d in duplicates:
        print(f"  {d.doc_id_1} <-> {d.doc_id_2}: {d.similarity:.4f}")

    # 测试抄袭检测
    target = "深度学习通过多层神经网络学习数据的表示，在图像识别和自然语言处理领域取得了显著成果。"
    sources = [
        ("src1", "深度学习使用多层神经网络学习数据表示，在图像识别与自然语言处理领域获得显著成果。"),
        ("src2", "区块链技术是一种去中心化的分布式账本。"),
    ]
    plagiarism = scorer.detect_plagiarism(target, "target1", sources, threshold=0.5)
    print(f"抄袭检测结果: is_plagiarized={plagiarism.is_plagiarized}, max_sim={plagiarism.max_similarity:.4f}")

    # 测试原创性评估
    references = [
        ("ref1", prop2),
        ("ref2", prop3),
    ]
    originality = scorer.assess_originality(prop1, "target1", references)
    print(f"原创性评估: score={originality.originality_score:.4f}, level={originality.level}")
    print(f"  建议: {originality.recommendations[:2]}")

    # 测试排名
    candidates = [
        ("cand1", "深度学习在图像识别中的应用"),
        ("cand2", "自然语言处理中的 Transformer 模型"),
        ("cand3", "深度学习在 NLP 中的应用研究"),
        ("cand4", "区块链在金融中的应用"),
    ]
    ranking = scorer.rank_documents("深度学习应用", candidates, top_k=3)
    print(f"排名结果（top 3）:")
    for r in ranking:
        print(f"  [{r.rank}] {r.doc_id}: {r.score:.4f}")

    # 测试摘要与方法相似度
    abstract1 = "本文研究深度学习在自然语言处理中的应用，提出了基于 BERT 的文本分类方法。"
    abstract2 = "本研究探讨深度学习技术在 NLP 领域的应用，设计了基于 BERT 的分类模型。"
    abstract_score = scorer.score_abstract_similarity(abstract1, abstract2)
    print(f"摘要相似度: {abstract_score.overall:.4f}")

    method1 = "采用 BERT 预训练模型，结合微调策略，在中文文本分类数据集上评估。"
    method2 = "使用 BERT 模型进行预训练，通过微调方法，在中文分类数据集上测试。"
    method_score = scorer.score_method_similarity(method1, method2)
    print(f"方法相似度: {method_score.overall:.4f}")

    # 测试解释
    explanation = scorer.explain_similarity(text1, text2)
    print(f"相似度解释: {explanation['interpretation']}")
    print(f"共同关键词: {explanation['common_keywords'][:5]}")

    # 测试权重设置
    scorer.set_weights({"semantic": 0.5, "literal": 0.3, "keyword": 0.2})
    weights = scorer.get_weights()
    print(f"权重设置: {weights}")

    scorer.shutdown()
    print("SimilarityScorer 自检通过")


if __name__ == "__main__":
    _run_self_test()
