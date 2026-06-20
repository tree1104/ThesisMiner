"""ThesisMiner 机器学习与文本处理模块

提供文本处理、嵌入向量化、相似度评分等能力，支撑：
    - 论题重复度检测
    - 文献相似度计算
    - 抄袭检测
    - 关键词提取
    - 文本摘要

子模块：
    - text_processor: 文本处理器（分词/相似度/关键词/摘要）
    - embedding_engine: 嵌入引擎（向量化/索引/搜索）
    - similarity_scorer: 相似度评分器（多维度评分）

设计原则：
    1. 零外部依赖：仅使用 Python 标准库实现核心算法
    2. 可降级：可选依赖（numpy/jieba）缺失时自动降级
    3. 学术文本优先：针对中文学术论文场景优化
"""
from backend.ml.text_processor import TextProcessor, get_text_processor
from backend.ml.embedding_engine import EmbeddingEngine, get_embedding_engine
from backend.ml.similarity_scorer import SimilarityScorer, get_similarity_scorer

__all__ = [
    # 文本处理
    "TextProcessor",
    "get_text_processor",
    # 嵌入引擎
    "EmbeddingEngine",
    "get_embedding_engine",
    # 相似度评分
    "SimilarityScorer",
    "get_similarity_scorer",
]
