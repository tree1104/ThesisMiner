"""术语提取器模块

提供面向学术文本的专业术语自动提取能力，包括：
    - 基于词频的术语提取
    - 基于 TF-IDF 的术语提取
    - 基于 C-value 的术语提取（考虑嵌套结构）
    - 基于 NC-value 的术语提取（结合上下文权重）
    - 术语边界识别与规范化
    - 术语去重与合并
    - 术语分类（方法/理论/技术/材料术语）
    - 术语词典构建与管理
    - 术语翻译推荐
    - 术语一致性检查
    - 批量提取与增量更新

仅使用 Python 标准库实现，不依赖外部 NLP 库。
针对中文学术论文场景进行专项优化。

典型用法：
    extractor = TerminologyExtractor()
    terms = extractor.extract(text, method="cvalue", top_k=50)
    classified = extractor.classify_terms(terms)
    dictionary = extractor.build_dictionary(corpus)
    consistency = extractor.check_consistency(text, dictionary)
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

# 尝试导入项目内模块
try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)

try:
    from backend.nlp.chinese_processor import (
        ChineseProcessor,
        get_chinese_processor,
        Token,
    )
except Exception:  # pragma: no cover
    ChineseProcessor = None  # type: ignore
    get_chinese_processor = None  # type: ignore
    Token = None  # type: ignore


# ===== 常量定义 =====

# 术语提取方法
EXTRACTION_METHODS = {"frequency", "tfidf", "cvalue", "ncvalue", "hybrid"}

# 术语分类
TERM_CATEGORIES = {
    "method": "方法术语",
    "theory": "理论术语",
    "technique": "技术术语",
    "material": "材料术语",
    "metric": "指标术语",
    "model": "模型术语",
    "algorithm": "算法术语",
    "system": "系统术语",
    "concept": "概念术语",
    "other": "其他术语",
}

# 术语分类关键词映射
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "method": [
        "方法", "算法", "策略", "方案", "途径", "手段", "流程", "步骤",
        "method", "approach", "strategy", "procedure", "methodology",
    ],
    "theory": [
        "理论", "定理", "公理", "原理", "定律", "假说", "学说",
        "theory", "theorem", "principle", "law", "hypothesis",
    ],
    "technique": [
        "技术", "技巧", "工艺", "技法", "技能",
        "technique", "technology", "skill",
    ],
    "material": [
        "材料", "原料", "试剂", "样品", "样本", "物质", "化合物",
        "material", "reagent", "sample", "substance", "compound",
    ],
    "metric": [
        "指标", "参数", "变量", "系数", "因子", "度量", "标准",
        "metric", "indicator", "parameter", "variable", "coefficient", "factor",
    ],
    "model": [
        "模型", "模式", "范式",
        "model", "pattern", "paradigm",
    ],
    "algorithm": [
        "算法", "迭代", "优化", "搜索", "排序", "聚类", "分类", "回归",
        "algorithm", "iteration", "optimization", "search", "sorting",
        "clustering", "classification", "regression",
    ],
    "system": [
        "系统", "框架", "架构", "平台", "环境", "体系",
        "system", "framework", "architecture", "platform", "environment",
    ],
    "concept": [
        "概念", "定义", "范畴", "类别", "类型",
        "concept", "definition", "category", "type", "class",
    ],
}

# 术语后缀（用于术语边界识别）
TERM_SUFFIXES_ZH = {
    "方法", "算法", "模型", "理论", "技术", "系统", "框架", "架构", "机制",
    "策略", "方案", "协议", "标准", "规范", "准则", "原则", "定律", "定理",
    "效应", "现象", "过程", "流程", "阶段", "步骤", "操作", "动作", "行为",
    "结构", "组织", "形态", "形式", "类型", "种类", "类别", "分类", "分级",
    "指标", "参数", "变量", "常量", "系数", "因子", "因素", "元素", "成分",
    "网络", "图", "树", "矩阵", "向量", "张量", "序列", "集合", "空间",
    "函数", "方程", "公式", "表达式", "算子", "变换", "映射", "关系",
    "材料", "试剂", "样品", "样本", "物质", "化合物",
}

# 术语前缀（用于术语边界识别）
TERM_PREFIXES_ZH = {
    "基于", "面向", "用于", "关于", "针对", "自适应", "自组织", "自学习",
    "多", "双", "单", "全", "半", "超", "亚", "准", "伪", "类",
    "高", "低", "大", "小", "长", "短", "宽", "窄", "深", "浅",
    "新", "旧", "传统", "现代", "经典", "新兴", "前沿",
    "分布式", "并行", "串行", "集中式", "去中心化",
    "在线", "离线", "实时", "非实时", "同步", "异步",
}

# 术语翻译词典（中英对照，简化版）
TERM_TRANSLATIONS: Dict[str, str] = {
    "机器学习": "Machine Learning",
    "深度学习": "Deep Learning",
    "神经网络": "Neural Network",
    "卷积神经网络": "Convolutional Neural Network",
    "循环神经网络": "Recurrent Neural Network",
    "生成对抗网络": "Generative Adversarial Network",
    "自然语言处理": "Natural Language Processing",
    "计算机视觉": "Computer Vision",
    "数据挖掘": "Data Mining",
    "模式识别": "Pattern Recognition",
    "信号处理": "Signal Processing",
    "图像处理": "Image Processing",
    "语音识别": "Speech Recognition",
    "知识图谱": "Knowledge Graph",
    "强化学习": "Reinforcement Learning",
    "迁移学习": "Transfer Learning",
    "联邦学习": "Federated Learning",
    "监督学习": "Supervised Learning",
    "无监督学习": "Unsupervised Learning",
    "半监督学习": "Semi-supervised Learning",
    "自监督学习": "Self-supervised Learning",
    "表示学习": "Representation Learning",
    "特征工程": "Feature Engineering",
    "特征提取": "Feature Extraction",
    "特征选择": "Feature Selection",
    "注意力机制": "Attention Mechanism",
    "变换器": "Transformer",
    "支持向量机": "Support Vector Machine",
    "决策树": "Decision Tree",
    "随机森林": "Random Forest",
    "梯度提升": "Gradient Boosting",
    "贝叶斯网络": "Bayesian Network",
    "马尔可夫模型": "Markov Model",
    "隐马尔可夫模型": "Hidden Markov Model",
    "条件随机场": "Conditional Random Field",
    "梯度下降": "Gradient Descent",
    "反向传播": "Backpropagation",
    "随机梯度下降": "Stochastic Gradient Descent",
    "批量归一化": "Batch Normalization",
    "丢弃": "Dropout",
    "正则化": "Regularization",
    "过拟合": "Overfitting",
    "欠拟合": "Underfitting",
    "泛化": "Generalization",
    "鲁棒性": "Robustness",
    "准确率": "Accuracy",
    "精确率": "Precision",
    "召回率": "Recall",
    "F1值": "F1 Score",
    "交叉验证": "Cross Validation",
    "混淆矩阵": "Confusion Matrix",
    "损失函数": "Loss Function",
    "目标函数": "Objective Function",
    "激活函数": "Activation Function",
    "softmax": "Softmax",
    "sigmoid": "Sigmoid",
    "relu": "ReLU",
    "tanh": "Tanh",
    "池化": "Pooling",
    "卷积": "Convolution",
    "全连接层": "Fully Connected Layer",
    "嵌入层": "Embedding Layer",
    "编码器": "Encoder",
    "解码器": "Decoder",
    "自编码器": "Autoencoder",
    "生成模型": "Generative Model",
    "判别模型": "Discriminative Model",
    "端到端": "End-to-end",
    "迁移": "Transfer",
    "微调": "Fine-tuning",
    "预训练": "Pre-training",
    "词向量": "Word Embedding",
    "词嵌入": "Word Embedding",
    "句向量": "Sentence Embedding",
    "文档向量": "Document Embedding",
    "主题模型": "Topic Model",
    "潜在狄利克雷分配": "Latent Dirichlet Allocation",
    "主成分分析": "Principal Component Analysis",
    "奇异值分解": "Singular Value Decomposition",
    "独立成分分析": "Independent Component Analysis",
    "线性判别分析": "Linear Discriminant Analysis",
    "聚类": "Clustering",
    "分类": "Classification",
    "回归": "Regression",
    "排序": "Ranking",
    "推荐": "Recommendation",
    "检索": "Retrieval",
    "匹配": "Matching",
    "对齐": "Alignment",
    "标注": "Annotation",
    "语料库": "Corpus",
    "数据集": "Dataset",
    "基准": "Benchmark",
    "评估": "Evaluation",
    "验证": "Validation",
    "测试": "Testing",
    "训练": "Training",
    "推理": "Inference",
    "部署": "Deployment",
    "优化": "Optimization",
    "收敛": "Convergence",
    "发散": "Divergence",
    "学习率": "Learning Rate",
    "批次大小": "Batch Size",
    "迭代次数": "Number of Iterations",
    "轮次": "Epoch",
    "权重": "Weight",
    "偏置": "Bias",
    "梯度": "Gradient",
    "海森矩阵": "Hessian Matrix",
    "雅可比矩阵": "Jacobian Matrix",
    "动量": "Momentum",
    "自适应矩估计": "Adaptive Moment Estimation",
    "均方根传播": "Root Mean Square Propagation",
    "适应性梯度": "Adaptive Gradient",
}

# 术语规范化映射（同义词合并）
TERM_NORMALIZATION_MAP: Dict[str, str] = {
    "CNN": "卷积神经网络",
    "RNN": "循环神经网络",
    "GAN": "生成对抗网络",
    "NLP": "自然语言处理",
    "CV": "计算机视觉",
    "SVM": "支持向量机",
    "DT": "决策树",
    "RF": "随机森林",
    "GBDT": "梯度提升决策树",
    "HMM": "隐马尔可夫模型",
    "CRF": "条件随机场",
    "SGD": "随机梯度下降",
    "BN": "批量归一化",
    "PCA": "主成分分析",
    "SVD": "奇异值分解",
    "ICA": "独立成分分析",
    "LDA": "潜在狄利克雷分配",
    "LSTM": "长短期记忆网络",
    "GRU": "门控循环单元",
    "BERT": "双向编码器表示",
    "GPT": "生成式预训练变换器",
    "Adam": "适应性矩估计",
    "RMSprop": "均方根传播",
    "Adagrad": "适应性梯度",
}

# 停用术语（过滤无意义的候选）
STOP_TERMS = {
    "的方法", "的技术", "的理论", "的模型", "的算法", "的系统",
    "这一方法", "这一技术", "这一理论", "这一模型", "这一算法",
    "本文方法", "本文技术", "本文理论", "本文模型", "本文算法",
    "上述方法", "上述技术", "上述理论", "上述模型", "上述算法",
    "该方法", "该技术", "该理论", "该模型", "该算法", "该系统",
    "新方法", "新技术", "新理论", "新模型", "新算法", "新系统",
    "旧方法", "旧技术", "旧理论", "旧模型", "旧算法",
    "好方法", "好技术", "好理论", "好模型", "好算法",
    "大方法", "大技术", "大理论", "大模型", "大算法",
    "小方法", "小技术", "小理论", "小模型", "小算法",
}


# ===== 数据类定义 =====

@dataclass
class Term:
    """术语。

    Attributes:
        text: 术语文本。
        frequency: 出现频次。
        score: 术语评分（提取算法计算得出）。
        category: 术语分类。
        length: 术语长度（字符数）。
        contexts: 出现的上下文列表（用于 NC-value 计算）。
        translation: 翻译（若有）。
        normalized: 规范化后的术语文本。
        variants: 变体列表（同义词/缩写）。
        confidence: 置信度（0-1）。
        source: 来源（corpus/dictionary/manual）。
    """
    text: str = ""
    frequency: int = 0
    score: float = 0.0
    category: str = "other"
    length: int = 0
    contexts: List[str] = field(default_factory=list)
    translation: str = ""
    normalized: str = ""
    variants: List[str] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "corpus"

    def __post_init__(self) -> None:
        if self.length == 0:
            self.length = len(self.text)
        if not self.normalized:
            self.normalized = self.text

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "text": self.text,
            "frequency": self.frequency,
            "score": round(self.score, 4),
            "category": self.category,
            "category_name": TERM_CATEGORIES.get(self.category, "其他术语"),
            "length": self.length,
            "translation": self.translation,
            "normalized": self.normalized,
            "variants": self.variants,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "context_count": len(self.contexts),
        }


@dataclass
class TermDictionary:
    """术语词典。

    Attributes:
        terms: 术语集合（文本到 Term 对象的映射）。
        name: 词典名称。
        domain: 领域。
        version: 版本。
        created_at: 创建时间。
        updated_at: 更新时间。
    """
    terms: Dict[str, Term] = field(default_factory=dict)
    name: str = ""
    domain: str = ""
    version: str = "1.0"
    created_at: str = ""
    updated_at: str = ""

    def add_term(self, term: Term) -> None:
        """添加术语。"""
        self.terms[term.normalized] = term
        self.updated_at = _iso_now()

    def remove_term(self, term_text: str) -> bool:
        """移除术语。"""
        if term_text in self.terms:
            del self.terms[term_text]
            self.updated_at = _iso_now()
            return True
        return False

    def get_term(self, term_text: str) -> Optional[Term]:
        """获取术语。"""
        return self.terms.get(term_text)

    def has_term(self, term_text: str) -> bool:
        """判断术语是否存在。"""
        return term_text in self.terms

    def size(self) -> int:
        """返回术语数量。"""
        return len(self.terms)

    def to_list(self) -> List[Term]:
        """返回所有术语列表。"""
        return list(self.terms.values())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "name": self.name,
            "domain": self.domain,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "term_count": len(self.terms),
            "terms": [t.to_dict() for t in self.terms.values()],
        }


@dataclass
class ConsistencyReport:
    """术语一致性报告。

    Attributes:
        total_terms: 检查的术语总数。
        consistent: 一致术语数。
        inconsistent: 不一致术语数。
        issues: 一致性问题列表。
        suggestions: 修改建议列表。
    """
    total_terms: int = 0
    consistent: int = 0
    inconsistent: int = 0
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def consistency_rate(self) -> float:
        """一致率。"""
        if self.total_terms == 0:
            return 0.0
        return self.consistent / self.total_terms

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "total_terms": self.total_terms,
            "consistent": self.consistent,
            "inconsistent": self.inconsistent,
            "consistency_rate": round(self.consistency_rate, 4),
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


@dataclass
class ExtractionConfig:
    """术语提取配置。

    Attributes:
        method: 提取方法。
        top_k: 返回的术语数量。
        min_frequency: 最小频次。
        min_length: 最小术语长度。
        max_length: 最大术语长度。
        remove_stop_terms: 是否过滤停用术语。
        normalize: 是否进行术语规范化。
        classify: 是否进行术语分类。
        with_context: 是否提取上下文。
        context_window: 上下文窗口大小。
    """
    method: str = "cvalue"
    top_k: int = 50
    min_frequency: int = 2
    min_length: int = 2
    max_length: int = 20
    remove_stop_terms: bool = True
    normalize: bool = True
    classify: bool = True
    with_context: bool = True
    context_window: int = 5


# ===== 工具函数 =====

def _iso_now() -> str:
    """获取当前 UTC 时间的 ISO8601 字符串。"""
    from datetime import datetime, timezone
    return datetime.now(tz=timezone.utc).isoformat()


def _is_cjk_char(ch: str) -> bool:
    """判断字符是否为 CJK 汉字。"""
    if not ch:
        return False
    code = ord(ch)
    return (0x4E00 <= code <= 0x9FFF or
            0x3400 <= code <= 0x4DBF or
            0xF900 <= code <= 0xFAFF)


def _is_chinese(text: str) -> bool:
    """判断文本是否主要包含中文字符。"""
    if not text:
        return False
    cjk_count = sum(1 for ch in text if _is_cjk_char(ch))
    return cjk_count / max(len(text), 1) > 0.5


# ===== 主类：术语提取器 =====

class TerminologyExtractor:
    """术语提取器。

    提供多种术语提取算法（词频/TF-IDF/C-value/NC-value），
    支持术语规范化、分类、翻译、一致性检查与词典管理。

    线程安全说明：本类为无状态提取器，可在多线程环境共享实例。
    术语词典为实例属性，若需并发修改需外部加锁。

    Attributes:
        chinese_processor: 中文处理器实例。
        dictionary: 内置术语词典。
        stop_terms: 停用术语集合。
    """

    # 单例实例
    _instance: Optional["TerminologyExtractor"] = None

    def __init__(
        self,
        chinese_processor: Optional[ChineseProcessor] = None,
    ) -> None:
        """初始化术语提取器。

        Args:
            chinese_processor: 自定义中文处理器，为 None 时使用全局单例。
        """
        # 中文处理器
        if chinese_processor is not None:
            self.chinese_processor = chinese_processor
        elif get_chinese_processor is not None:
            try:
                self.chinese_processor = get_chinese_processor()
            except Exception:  # pragma: no cover
                self.chinese_processor = None
        else:
            self.chinese_processor = None
        # 停用术语
        self.stop_terms: Set[str] = set(STOP_TERMS)
        # 术语后缀与前缀
        self.term_suffixes: Set[str] = set(TERM_SUFFIXES_ZH)
        self.term_prefixes: Set[str] = set(TERM_PREFIXES_ZH)
        # 翻译词典
        self.translations: Dict[str, str] = dict(TERM_TRANSLATIONS)
        # 规范化映射
        self.normalization_map: Dict[str, str] = dict(TERM_NORMALIZATION_MAP)
        # 反向规范化映射（规范化后的术语 -> 变体列表）
        self._build_reverse_normalization()
        # 分类关键词
        self.category_keywords: Dict[str, List[str]] = dict(CATEGORY_KEYWORDS)
        # 内置术语词典
        self.dictionary: TermDictionary = TermDictionary(
            name="内置术语词典",
            domain="通用学术",
            created_at=_iso_now(),
            updated_at=_iso_now(),
        )
        # 初始化内置术语
        self._init_builtin_terms()
        _logger.debug(
            "TerminologyExtractor 初始化完成，内置术语=%d，翻译=%d",
            self.dictionary.size(), len(self.translations),
        )

    @classmethod
    def get_instance(cls) -> "TerminologyExtractor":
        """获取全局单例实例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _build_reverse_normalization(self) -> None:
        """构建反向规范化映射。"""
        self.reverse_normalization: Dict[str, List[str]] = defaultdict(list)
        for variant, standard in self.normalization_map.items():
            self.reverse_normalization[standard].append(variant)

    def _init_builtin_terms(self) -> None:
        """初始化内置术语词典。"""
        for term_text, translation in self.translations.items():
            term = Term(
                text=term_text,
                frequency=0,
                score=1.0,
                translation=translation,
                normalized=term_text,
                source="dictionary",
                confidence=1.0,
            )
            term.category = self._classify_single_term(term_text)
            term.variants = self.reverse_normalization.get(term_text, [])
            self.dictionary.add_term(term)

    # ===== 主提取入口 =====

    def extract(
        self,
        text: str,
        method: str = "cvalue",
        top_k: int = 50,
        min_frequency: int = 2,
        min_length: int = 2,
        max_length: int = 20,
        remove_stop_terms: bool = True,
        normalize: bool = True,
        classify: bool = True,
        with_context: bool = True,
    ) -> List[Term]:
        """提取术语。

        主提取入口，支持多种算法。

        Args:
            text: 待提取文本。
            method: 提取方法（frequency/tfidf/cvalue/ncvalue/hybrid）。
            top_k: 返回的术语数量。
            min_frequency: 最小频次阈值。
            min_length: 最小术语长度。
            max_length: 最大术语长度。
            remove_stop_terms: 是否过滤停用术语。
            normalize: 是否进行术语规范化。
            classify: 是否进行术语分类。
            with_context: 是否提取上下文。

        Returns:
            术语列表，按评分降序排列。
        """
        if not text:
            return []
        method = method.lower()
        if method not in EXTRACTION_METHODS:
            method = "cvalue"
        # 候选术语提取
        candidates = self._extract_candidates(text, min_length, max_length)
        if not candidates:
            return []
        # 频次统计
        term_freq: Counter = Counter(candidates)
        # 过滤低频
        term_freq = Counter({t: f for t, f in term_freq.items() if f >= min_frequency})
        if not term_freq:
            return []
        # 过滤停用术语
        if remove_stop_terms:
            term_freq = Counter({t: f for t, f in term_freq.items() if t not in self.stop_terms})
        if not term_freq:
            return []
        # 提取上下文（用于 NC-value）
        contexts: Dict[str, List[str]] = {}
        if with_context or method in ("ncvalue", "hybrid"):
            contexts = self._extract_contexts(text, term_freq.keys(), window=5)
        # 按方法计算评分
        if method == "frequency":
            terms = self._score_frequency(term_freq, contexts, with_context)
        elif method == "tfidf":
            terms = self._score_tfidf(text, term_freq, contexts, with_context)
        elif method == "cvalue":
            terms = self._score_cvalue(text, term_freq, contexts, with_context)
        elif method == "ncvalue":
            terms = self._score_ncvalue(text, term_freq, contexts, with_context)
        else:  # hybrid
            terms = self._score_hybrid(text, term_freq, contexts, with_context)
        # 规范化
        if normalize:
            terms = self._normalize_terms(terms)
        # 分类
        if classify:
            for term in terms:
                term.category = self._classify_single_term(term.text)
        # 翻译
        for term in terms:
            if term.text in self.translations:
                term.translation = self.translations[term.text]
        # 排序与截断
        terms.sort(key=lambda t: t.score, reverse=True)
        terms = terms[:top_k]
        # 设置置信度
        if terms:
            max_score = terms[0].score
            for term in terms:
                term.confidence = min(1.0, term.score / max_score) if max_score > 0 else 0.0
        _logger.debug("术语提取完成：方法=%s，候选=%d，返回=%d", method, len(term_freq), len(terms))
        return terms

    def _extract_candidates(
        self,
        text: str,
        min_length: int,
        max_length: int,
    ) -> List[str]:
        """提取候选术语。

        基于分词结果与术语后缀/前缀规则，提取候选术语。

        Args:
            text: 待提取文本。
            min_length: 最小长度。
            max_length: 最大长度。

        Returns:
            候选术语文本列表（含重复）。
        """
        candidates: List[str] = []
        if self.chinese_processor is not None:
            # 使用中文处理器分词
            tokens = self.chinese_processor.tokenize(text, with_pos=True, with_offset=True)
            # 提取名词性词组组合
            candidates = self._extract_noun_phrases(tokens, min_length, max_length)
        else:
            # 降级：基于正则的 n-gram 提取
            candidates = self._extract_ngrams(text, min_length, max_length)
        return candidates

    def _extract_noun_phrases(
        self,
        tokens: List[Any],
        min_length: int,
        max_length: int,
    ) -> List[str]:
        """提取名词性词组。

        基于词性标注，将连续的名词性词元组合为候选术语。

        Args:
            tokens: 词元列表。
            min_length: 最小长度。
            max_length: 最大长度。

        Returns:
            候选术语列表。
        """
        candidates: List[str] = []
        if not tokens:
            return candidates
        # 名词性词性集合
        noun_pos = {"n", "nr", "ns", "nt", "nz", "vn", "an", "ng", "nl", "eng"}
        i = 0
        while i < len(tokens):
            token = tokens[i]
            # 检查是否为名词性词元
            if token.pos in noun_pos and not token.is_stopword:
                # 向后扩展名词组合
                phrase_tokens: List[Any] = [token]
                j = i + 1
                while j < len(tokens):
                    next_tok = tokens[j]
                    # 名词性词元或术语后缀
                    if (next_tok.pos in noun_pos and not next_tok.is_stopword):
                        phrase_tokens.append(next_tok)
                        j += 1
                        # 检查组合长度
                        combined = "".join(t.text for t in phrase_tokens)
                        if len(combined) > max_length:
                            phrase_tokens.pop()
                            j -= 1
                            break
                    else:
                        break
                # 生成候选
                if len(phrase_tokens) > 0:
                    phrase = "".join(t.text for t in phrase_tokens)
                    if min_length <= len(phrase) <= max_length:
                        candidates.append(phrase)
                        # 同时添加子短语（用于 C-value 嵌套分析）
                        if len(phrase_tokens) > 2:
                            for start in range(len(phrase_tokens)):
                                for end in range(start + 2, len(phrase_tokens) + 1):
                                    sub_phrase = "".join(t.text for t in phrase_tokens[start:end])
                                    if min_length <= len(sub_phrase) <= max_length:
                                        candidates.append(sub_phrase)
                i = j
            else:
                i += 1
        return candidates

    def _extract_ngrams(
        self,
        text: str,
        min_length: int,
        max_length: int,
    ) -> List[str]:
        """基于 n-gram 的候选提取（降级方案）。

        Args:
            text: 待提取文本。
            min_length: 最小长度。
            max_length: 最大长度。

        Returns:
            候选术语列表。
        """
        candidates: List[str] = []
        # 按非中文字符分割
        segments = re.findall(r"[\u4e00-\u9fff]+", text)
        for seg in segments:
            # 生成 2-gram 到 max_length-gram
            for n in range(min_length, min(max_length, len(seg)) + 1):
                for i in range(len(seg) - n + 1):
                    candidates.append(seg[i:i + n])
        return candidates

    def _extract_contexts(
        self,
        text: str,
        terms: Iterable[str],
        window: int = 5,
    ) -> Dict[str, List[str]]:
        """提取术语的上下文。

        为每个术语提取出现位置的上下文（前后各 window 个词）。

        Args:
            text: 原始文本。
            terms: 术语集合。
            window: 上下文窗口大小。

        Returns:
            术语到上下文列表的映射。
        """
        contexts: Dict[str, List[str]] = defaultdict(list)
        if self.chinese_processor is not None:
            tokens = self.chinese_processor.tokenize(text, with_offset=False)
        else:
            # 降级：按字符切分
            tokens = list(text)
        token_texts = [t.text if hasattr(t, "text") else t for t in tokens]
        term_set = set(terms)
        # 遍历查找术语出现位置
        for term in term_set:
            term_len = len(term)
            # 在 token 序列中查找
            i = 0
            while i < len(token_texts):
                # 尝试匹配术语（可能跨越多个 token）
                combined = ""
                j = i
                while j < len(token_texts) and len(combined) < term_len:
                    combined += token_texts[j]
                    j += 1
                if combined == term:
                    # 提取上下文
                    start = max(0, i - window)
                    end = min(len(token_texts), j + window)
                    context = "".join(token_texts[start:end])
                    contexts[term].append(context)
                    i = j
                else:
                    i += 1
        return dict(contexts)

    # ===== 评分方法 =====

    def _score_frequency(
        self,
        term_freq: Counter,
        contexts: Dict[str, List[str]],
        with_context: bool,
    ) -> List[Term]:
        """基于词频的术语评分。

        Args:
            term_freq: 术语频次统计。
            contexts: 术语上下文。
            with_context: 是否包含上下文。

        Returns:
            术语列表。
        """
        terms: List[Term] = []
        for term_text, freq in term_freq.items():
            term = Term(
                text=term_text,
                frequency=freq,
                score=float(freq),
                contexts=contexts.get(term_text, []) if with_context else [],
            )
            terms.append(term)
        return terms

    def _score_tfidf(
        self,
        text: str,
        term_freq: Counter,
        contexts: Dict[str, List[str]],
        with_context: bool,
    ) -> List[Term]:
        """基于 TF-IDF 的术语评分。

        Args:
            text: 原始文本。
            term_freq: 术语频次。
            contexts: 术语上下文。
            with_context: 是否包含上下文。

        Returns:
            术语列表。
        """
        terms: List[Term] = []
        total = sum(term_freq.values())
        if total == 0:
            return terms
        # 计算 TF
        tf: Dict[str, float] = {t: f / total for t, f in term_freq.items()}
        # 计算 IDF（使用文档长度近似）
        doc_len = len(text)
        for term_text, freq in term_freq.items():
            tf_val = tf[term_text]
            # 简化 IDF：长术语 IDF 较高
            idf_val = math.log(1 + doc_len / (len(term_text) * freq + 1))
            score = tf_val * idf_val
            term = Term(
                text=term_text,
                frequency=freq,
                score=score,
                contexts=contexts.get(term_text, []) if with_context else [],
            )
            terms.append(term)
        return terms

    def _score_cvalue(
        self,
        text: str,
        term_freq: Counter,
        contexts: Dict[str, List[str]],
        with_context: bool,
    ) -> List[Term]:
        """基于 C-value 的术语评分。

        C-value 算法考虑术语的嵌套结构，对作为其他术语子串的术语进行惩罚。
        公式：
            若术语 a 不嵌套在其他术语中：
                C-value(a) = log2(|a|) * freq(a)
            若术语 a 嵌套在其他术语中：
                C-value(a) = log2(|a|) * (freq(a) - (1/N) * sum(freq(b)))
                其中 N 是包含 a 的术语数量，b 是包含 a 的术语。

        Args:
            text: 原始文本。
            term_freq: 术语频次。
            contexts: 术语上下文。
            with_context: 是否包含上下文。

        Returns:
            术语列表。
        """
        terms: List[Term] = []
        # 构建嵌套关系：term -> 包含它的更长的术语列表
        nesting_map: Dict[str, List[str]] = defaultdict(list)
        all_terms = list(term_freq.keys())
        for i, term_a in enumerate(all_terms):
            for term_b in all_terms:
                if term_a != term_b and term_a in term_b and len(term_a) < len(term_b):
                    nesting_map[term_a].append(term_b)
        # 计算 C-value
        for term_text, freq in term_freq.items():
            length = len(term_text)
            log_len = math.log2(length) if length > 0 else 0
            containing_terms = nesting_map.get(term_text, [])
            if not containing_terms:
                # 不嵌套在其他术语中
                cvalue = log_len * freq
            else:
                # 嵌套在其他术语中
                total_containing_freq = sum(term_freq.get(t, 0) for t in containing_terms)
                n_containing = len(containing_terms)
                cvalue = log_len * (freq - total_containing_freq / n_containing)
                cvalue = max(0.0, cvalue)  # 避免负值
            term = Term(
                text=term_text,
                frequency=freq,
                score=cvalue,
                contexts=contexts.get(term_text, []) if with_context else [],
            )
            terms.append(term)
        return terms

    def _score_ncvalue(
        self,
        text: str,
        term_freq: Counter,
        contexts: Dict[str, List[str]],
        with_context: bool,
    ) -> List[Term]:
        """基于 NC-value 的术语评分。

        NC-value 在 C-value 基础上结合上下文权重，考虑术语出现的上下文词汇。

        公式：NC-value(a) = 0.8 * C-value(a) + 0.2 * context_weight(a)

        Args:
            text: 原始文本。
            term_freq: 术语频次。
            contexts: 术语上下文。
            with_context: 是否包含上下文。

        Returns:
            术语列表。
        """
        # 先计算 C-value
        cvalue_terms = self._score_cvalue(text, term_freq, contexts, with_context)
        cvalue_scores: Dict[str, float] = {t.text: t.score for t in cvalue_terms}
        # 计算上下文权重
        # 统计所有术语的上下文词频
        context_word_freq: Counter = Counter()
        term_context_words: Dict[str, Counter] = {}
        for term_text, ctxs in contexts.items():
            ctx_counter: Counter = Counter()
            for ctx in ctxs:
                # 简化：按字符切分上下文词
                if self.chinese_processor is not None:
                    ctx_tokens = self.chinese_processor.tokenize(ctx)
                    for tok in ctx_tokens:
                        if not tok.is_stopword and len(tok.text) >= 2:
                            ctx_counter[tok.text] += 1
                            context_word_freq[tok.text] += 1
                else:
                    # 降级：2-gram
                    for i in range(len(ctx) - 1):
                        ctx_counter[ctx[i:i + 2]] += 1
                        context_word_freq[ctx[i:i + 2]] += 1
            term_context_words[term_text] = ctx_counter
        # 计算上下文词的权重（出现于多少个不同术语的上下文中）
        context_word_weights: Dict[str, float] = {}
        total_terms = len(contexts)
        for word, freq in context_word_freq.items():
            # 权重 = 出现于不同术语上下文的频率
            context_word_weights[word] = freq / total_terms if total_terms > 0 else 0
        # 计算 NC-value
        terms: List[Term] = []
        for term in cvalue_terms:
            cvalue = cvalue_scores[term.text]
            # 上下文权重
            ctx_words = term_context_words.get(term.text, Counter())
            context_weight = sum(
                context_word_weights.get(w, 0) * f for w, f in ctx_words.items()
            )
            # 归一化上下文权重
            if ctx_words:
                context_weight = context_weight / sum(ctx_words.values())
            # NC-value = 0.8 * C-value + 0.2 * context_weight
            ncvalue = 0.8 * cvalue + 0.2 * context_weight * cvalue
            term.score = ncvalue
            terms.append(term)
        return terms

    def _score_hybrid(
        self,
        text: str,
        term_freq: Counter,
        contexts: Dict[str, List[str]],
        with_context: bool,
    ) -> List[Term]:
        """混合评分方法。

        综合 C-value、TF-IDF 与词频，加权计算最终评分。

        Args:
            text: 原始文本。
            term_freq: 术语频次。
            contexts: 术语上下文。
            with_context: 是否包含上下文。

        Returns:
            术语列表。
        """
        # 分别计算三种评分
        cvalue_terms = self._score_cvalue(text, term_freq, contexts, with_context)
        tfidf_terms = self._score_tfidf(text, term_freq, contexts, with_context)
        freq_terms = self._score_frequency(term_freq, contexts, with_context)
        # 构建评分映射
        cvalue_scores: Dict[str, float] = {t.text: t.score for t in cvalue_terms}
        tfidf_scores: Dict[str, float] = {t.text: t.score for t in tfidf_terms}
        freq_scores: Dict[str, float] = {t.text: t.score for t in freq_terms}
        # 归一化各评分到 [0, 1]
        def normalize(scores: Dict[str, float]) -> Dict[str, float]:
            if not scores:
                return {}
            max_val = max(scores.values())
            min_val = min(scores.values())
            if max_val == min_val:
                return {k: 1.0 for k in scores}
            return {k: (v - min_val) / (max_val - min_val) for k, v in scores.items()}
        norm_cvalue = normalize(cvalue_scores)
        norm_tfidf = normalize(tfidf_scores)
        norm_freq = normalize(freq_scores)
        # 加权融合（C-value 权重最高）
        weights = {"cvalue": 0.5, "tfidf": 0.3, "freq": 0.2}
        terms: List[Term] = []
        for term_text, freq in term_freq.items():
            hybrid_score = (
                weights["cvalue"] * norm_cvalue.get(term_text, 0) +
                weights["tfidf"] * norm_tfidf.get(term_text, 0) +
                weights["freq"] * norm_freq.get(term_text, 0)
            )
            term = Term(
                text=term_text,
                frequency=freq,
                score=hybrid_score,
                contexts=contexts.get(term_text, []) if with_context else [],
            )
            terms.append(term)
        return terms

    # ===== 术语规范化 =====

    def _normalize_terms(self, terms: List[Term]) -> List[Term]:
        """术语规范化。

        将同义词/缩写合并到标准形式。

        Args:
            terms: 待规范化的术语列表。

        Returns:
            规范化后的术语列表。
        """
        normalized_map: Dict[str, Term] = {}
        for term in terms:
            # 查找规范化形式
            standard = self.normalization_map.get(term.text, term.text)
            if standard in normalized_map:
                # 合并到已有术语
                existing = normalized_map[standard]
                existing.frequency += term.frequency
                existing.score = max(existing.score, term.score)
                existing.contexts.extend(term.contexts)
                if term.text != standard and term.text not in existing.variants:
                    existing.variants.append(term.text)
            else:
                # 新建规范化术语
                if term.text != standard:
                    term.variants = list(term.variants)
                    if term.text not in term.variants:
                        term.variants.append(term.text)
                term.normalized = standard
                term.text = standard
                normalized_map[standard] = term
        return list(normalized_map.values())

    # ===== 术语分类 =====

    def classify_terms(self, terms: List[Term]) -> List[Term]:
        """术语分类。

        将术语分类到方法/理论/技术/材料等类别。

        Args:
            terms: 待分类的术语列表。

        Returns:
            分类后的术语列表（原地修改 category 字段）。
        """
        for term in terms:
            term.category = self._classify_single_term(term.text)
        return terms

    def _classify_single_term(self, term_text: str) -> str:
        """分类单个术语。

        基于术语后缀与关键词匹配进行分类。

        Args:
            term_text: 术语文本。

        Returns:
            分类字符串。
        """
        term_lower = term_text.lower()
        # 基于后缀匹配
        for category, keywords in self.category_keywords.items():
            for kw in keywords:
                if term_text.endswith(kw) or term_lower.endswith(kw.lower()):
                    return category
        # 基于包含匹配
        for category, keywords in self.category_keywords.items():
            for kw in keywords:
                if kw in term_text or kw.lower() in term_lower:
                    return category
        # 检查内置词典
        if term_text in self.dictionary.terms:
            return self.dictionary.terms[term_text].category
        return "other"

    # ===== 术语翻译 =====

    def translate_term(self, term_text: str) -> str:
        """翻译术语。

        Args:
            term_text: 术语文本。

        Returns:
            翻译文本，若无翻译返回空字符串。
        """
        # 直接查找
        if term_text in self.translations:
            return self.translations[term_text]
        # 查找规范化形式
        standard = self.normalization_map.get(term_text)
        if standard and standard in self.translations:
            return self.translations[standard]
        return ""

    def add_translation(self, term_text: str, translation: str) -> None:
        """添加术语翻译。"""
        self.translations[term_text] = translation

    def recommend_translations(
        self,
        term_text: str,
        top_k: int = 5,
    ) -> List[str]:
        """推荐术语翻译。

        基于术语组成部分与相似术语推荐翻译。

        Args:
            term_text: 术语文本。
            top_k: 返回的推荐数量。

        Returns:
            推荐翻译列表。
        """
        # 直接翻译
        direct = self.translate_term(term_text)
        if direct:
            return [direct]
        # 基于组成部分翻译
        recommendations: List[str] = []
        # 查找包含的已知术语
        for known_term, translation in self.translations.items():
            if known_term in term_text and known_term != term_text:
                recommendations.append(translation)
        # 查找相似术语
        if self.chinese_processor is not None:
            similar_terms = self._find_similar_terms(term_text, top_k=top_k * 2)
            for sim_term in similar_terms:
                trans = self.translate_term(sim_term)
                if trans and trans not in recommendations:
                    recommendations.append(trans)
        return recommendations[:top_k]

    def _find_similar_terms(self, term_text: str, top_k: int = 10) -> List[str]:
        """查找相似术语。

        Args:
            term_text: 目标术语。
            top_k: 返回数量。

        Returns:
            相似术语列表。
        """
        if self.chinese_processor is None:
            return []
        similarities: List[Tuple[str, float]] = []
        for known_term in self.translations.keys():
            if known_term == term_text:
                continue
            sim = self.chinese_processor.compute_similarity(term_text, known_term, method="cosine")
            similarities.append((known_term, sim))
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [t[0] for t in similarities[:top_k]]

    # ===== 术语词典管理 =====

    def build_dictionary(
        self,
        corpus: Union[str, List[str]],
        name: str = "",
        domain: str = "",
        method: str = "cvalue",
        top_k: int = 200,
        min_frequency: int = 2,
    ) -> TermDictionary:
        """从语料构建术语词典。

        Args:
            corpus: 语料文本（单个文本或文本列表）。
            name: 词典名称。
            domain: 领域。
            method: 提取方法。
            top_k: 提取的术语数量。
            min_frequency: 最小频次。

        Returns:
            构建的术语词典。
        """
        # 合并语料
        if isinstance(corpus, str):
            corpus = [corpus]
        full_text = "\n".join(corpus)
        # 提取术语
        terms = self.extract(
            full_text,
            method=method,
            top_k=top_k,
            min_frequency=min_frequency,
            normalize=True,
            classify=True,
            with_context=False,
        )
        # 构建词典
        dictionary = TermDictionary(
            name=name or "自动构建术语词典",
            domain=domain or "通用",
            created_at=_iso_now(),
            updated_at=_iso_now(),
        )
        for term in terms:
            dictionary.add_term(term)
        _logger.info("术语词典构建完成：%s，术语数=%d", dictionary.name, dictionary.size())
        return dictionary

    def update_dictionary(
        self,
        dictionary: TermDictionary,
        new_text: str,
        method: str = "cvalue",
        min_frequency: int = 2,
        merge_strategy: str = "merge",
    ) -> int:
        """增量更新术语词典。

        Args:
            dictionary: 待更新的词典。
            new_text: 新增文本。
            method: 提取方法。
            min_frequency: 最小频次。
            merge_strategy: 合并策略（merge/replace/keep）。

        Returns:
            新增的术语数量。
        """
        # 从新文本提取术语
        new_terms = self.extract(
            new_text,
            method=method,
            top_k=500,
            min_frequency=min_frequency,
            normalize=True,
            classify=True,
            with_context=False,
        )
        added = 0
        for term in new_terms:
            if term.normalized in dictionary.terms:
                # 已存在：根据策略处理
                if merge_strategy == "merge":
                    existing = dictionary.terms[term.normalized]
                    existing.frequency += term.frequency
                    existing.score = max(existing.score, term.score)
                elif merge_strategy == "replace":
                    dictionary.terms[term.normalized] = term
                # keep: 不修改
            else:
                # 新术语
                dictionary.add_term(term)
                added += 1
        dictionary.updated_at = _iso_now()
        _logger.info("术语词典增量更新：新增=%d，总计=%d", added, dictionary.size())
        return added

    def export_dictionary(
        self,
        dictionary: TermDictionary,
        format: str = "json",
    ) -> str:
        """导出术语词典。

        Args:
            dictionary: 术语词典。
            format: 导出格式（json/csv）。

        Returns:
            导出的字符串。
        """
        import json
        if format.lower() == "json":
            return json.dumps(dictionary.to_dict(), ensure_ascii=False, indent=2)
        elif format.lower() == "csv":
            lines: List[str] = ["术语,频次,评分,分类,翻译,规范化形式,变体,置信度,来源"]
            for term in dictionary.terms.values():
                variants_str = "|".join(term.variants)
                lines.append(
                    f"{term.text},{term.frequency},{term.score:.4f},"
                    f"{term.category},{term.translation},{term.normalized},"
                    f"{variants_str},{term.confidence:.4f},{term.source}"
                )
            return "\n".join(lines)
        else:
            return json.dumps(dictionary.to_dict(), ensure_ascii=False, indent=2)

    # ===== 术语一致性检查 =====

    def check_consistency(
        self,
        text: str,
        dictionary: Optional[TermDictionary] = None,
    ) -> ConsistencyReport:
        """术语一致性检查。

        检查文本中术语使用的一致性，包括：
            - 同一概念是否使用了不同的术语形式
            - 缩写与全称是否一致
            - 术语拼写是否统一

        Args:
            text: 待检查文本。
            dictionary: 术语词典，为 None 时使用内置词典。

        Returns:
            一致性报告。
        """
        if not text:
            return ConsistencyReport()
        dict_to_use = dictionary or self.dictionary
        report = ConsistencyReport()
        # 提取文本中的所有术语
        terms_in_text = self.extract(
            text,
            method="frequency",
            top_k=1000,
            min_frequency=1,
            normalize=False,
            classify=False,
            with_context=False,
        )
        term_set = {t.text for t in terms_in_text}
        report.total_terms = len(term_set)
        # 检查每个术语的一致性
        for term_text in term_set:
            # 检查是否有规范化形式
            standard = self.normalization_map.get(term_text)
            if standard and standard != term_text:
                # 使用了缩写/变体
                if standard in term_set:
                    # 文本中同时存在标准形式与变体
                    report.inconsistent += 1
                    report.issues.append({
                        "type": "variant_mixed",
                        "term": term_text,
                        "standard": standard,
                        "message": f"术语 '{term_text}' 与其标准形式 '{standard}' 同时出现",
                    })
                    report.suggestions.append({
                        "term": term_text,
                        "suggestion": standard,
                        "reason": "建议统一使用标准形式",
                    })
                else:
                    # 仅使用了变体
                    report.consistent += 1
                    report.suggestions.append({
                        "term": term_text,
                        "suggestion": standard,
                        "reason": "建议使用标准形式",
                    })
            else:
                report.consistent += 1
        # 检查词典中的术语变体
        for term_text in term_set:
            if term_text in dict_to_use.terms:
                term_obj = dict_to_use.terms[term_text]
                for variant in term_obj.variants:
                    if variant in term_set and variant != term_text:
                        report.inconsistent += 1
                        report.issues.append({
                            "type": "variant_conflict",
                            "term": term_text,
                            "variant": variant,
                            "message": f"术语 '{term_text}' 与变体 '{variant}' 同时使用",
                        })
                        report.suggestions.append({
                            "term": variant,
                            "suggestion": term_text,
                            "reason": f"建议统一使用 '{term_text}'",
                        })
        # 重新计算一致数（避免重复计数）
        consistent_terms = report.total_terms - len({i["term"] for i in report.issues})
        report.consistent = max(0, consistent_terms)
        report.inconsistent = report.total_terms - report.consistent
        return report

    # ===== 术语推荐 =====

    def recommend_terms(
        self,
        text: str,
        dictionary: Optional[TermDictionary] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """推荐文本中应使用的术语。

        基于词典，推荐文本中可能遗漏的术语。

        Args:
            text: 待分析文本。
            dictionary: 术语词典，为 None 时使用内置词典。
            top_k: 推荐数量。

        Returns:
            推荐术语列表，每个条目包含 term、reason、score。
        """
        dict_to_use = dictionary or self.dictionary
        recommendations: List[Dict[str, Any]] = []
        # 提取文本已有术语
        existing_terms = self.extract(
            text,
            method="frequency",
            top_k=1000,
            min_frequency=1,
            normalize=False,
            classify=False,
            with_context=False,
        )
        existing_set = {t.text for t in existing_terms}
        # 遍历词典，查找相关但未使用的术语
        for term_text, term_obj in dict_to_use.terms.items():
            if term_text in existing_set:
                continue
            # 检查术语的组成部分是否在文本中出现
            relevance_score = 0.0
            reasons: List[str] = []
            # 检查术语的子串是否出现
            if len(term_text) >= 4:
                # 检查前半部分与后半部分
                half = len(term_text) // 2
                prefix = term_text[:half]
                suffix = term_text[half:]
                if prefix in text:
                    relevance_score += 0.3
                    reasons.append(f"文本包含术语前缀 '{prefix}'")
                if suffix in text:
                    relevance_score += 0.3
                    reasons.append(f"文本包含术语后缀 '{suffix}'")
            # 检查变体是否出现
            for variant in term_obj.variants:
                if variant in text:
                    relevance_score += 0.5
                    reasons.append(f"文本包含术语变体 '{variant}'")
                    break
            # 检查同分类术语是否出现
            term_category = term_obj.category
            same_category_in_text = [
                t for t in existing_set
                if t in dict_to_use.terms
                and dict_to_use.terms[t].category == term_category
            ]
            if same_category_in_text:
                relevance_score += 0.2
                reasons.append(f"文本包含同类术语: {', '.join(same_category_in_text[:3])}")
            if relevance_score > 0:
                recommendations.append({
                    "term": term_text,
                    "translation": term_obj.translation,
                    "category": term_obj.category,
                    "score": relevance_score,
                    "reasons": reasons,
                })
        # 排序与截断
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations[:top_k]

    # ===== 批量提取 =====

    def batch_extract(
        self,
        texts: List[str],
        method: str = "cvalue",
        top_k: int = 50,
    ) -> List[List[Term]]:
        """批量术语提取。

        Args:
            texts: 文本列表。
            method: 提取方法。
            top_k: 每个文本返回的术语数。

        Returns:
            每个文本的术语列表。
        """
        return [
            self.extract(t, method=method, top_k=top_k)
            for t in texts
        ]

    def extract_from_corpus(
        self,
        corpus: List[str],
        method: str = "cvalue",
        top_k: int = 100,
        min_frequency: int = 2,
    ) -> List[Term]:
        """从语料库提取术语。

        合并所有文本后提取术语，适用于构建领域术语词典。

        Args:
            corpus: 文本列表。
            method: 提取方法。
            top_k: 返回的术语数。
            min_frequency: 最小频次。

        Returns:
            术语列表。
        """
        full_text = "\n".join(corpus)
        return self.extract(
            full_text,
            method=method,
            top_k=top_k,
            min_frequency=min_frequency,
        )

    # ===== 术语评估 =====

    def evaluate_extraction(
        self,
        extracted_terms: List[Term],
        gold_terms: Set[str],
    ) -> Dict[str, Any]:
        """评估术语提取质量。

        Args:
            extracted_terms: 提取的术语列表。
            gold_terms: 标准术语集合（金标准）。

        Returns:
            评估指标字典，包含 precision、recall、f1。
        """
        extracted_set = {t.text for t in extracted_terms}
        # 计算指标
        true_positives = extracted_set & gold_terms
        false_positives = extracted_set - gold_terms
        false_negatives = gold_terms - extracted_set
        tp_count = len(true_positives)
        fp_count = len(false_positives)
        fn_count = len(false_negatives)
        precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
        recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "true_positives": tp_count,
            "false_positives": fp_count,
            "false_negatives": fn_count,
            "extracted_count": len(extracted_set),
            "gold_count": len(gold_terms),
            "matched_terms": sorted(true_positives),
            "missed_terms": sorted(false_negatives),
            "wrong_terms": sorted(false_positives),
        }

    # ===== 术语统计 =====

    def term_statistics(self, terms: List[Term]) -> Dict[str, Any]:
        """术语统计信息。

        Args:
            terms: 术语列表。

        Returns:
            统计信息字典。
        """
        if not terms:
            return {
                "total": 0, "categories": {}, "avg_length": 0,
                "avg_frequency": 0, "avg_score": 0,
            }
        # 分类统计
        category_counts: Counter = Counter(t.category for t in terms)
        # 长度统计
        lengths = [t.length for t in terms]
        avg_length = sum(lengths) / len(lengths)
        # 频次统计
        frequencies = [t.frequency for t in terms]
        avg_frequency = sum(frequencies) / len(frequencies)
        # 评分统计
        scores = [t.score for t in terms]
        avg_score = sum(scores) / len(scores)
        return {
            "total": len(terms),
            "categories": {
                cat: {"count": count, "name": TERM_CATEGORIES.get(cat, "其他")}
                for cat, count in category_counts.most_common()
            },
            "avg_length": round(avg_length, 2),
            "min_length": min(lengths),
            "max_length": max(lengths),
            "avg_frequency": round(avg_frequency, 2),
            "min_frequency": min(frequencies),
            "max_frequency": max(frequencies),
            "avg_score": round(avg_score, 4),
            "min_score": min(scores),
            "max_score": max(scores),
            "with_translation": sum(1 for t in terms if t.translation),
            "with_variants": sum(1 for t in terms if t.variants),
        }

    # ===== 词典操作 =====

    def add_term_to_dictionary(
        self,
        term_text: str,
        translation: str = "",
        category: str = "other",
        variants: Optional[List[str]] = None,
        dictionary: Optional[TermDictionary] = None,
    ) -> Term:
        """添加术语到词典。

        Args:
            term_text: 术语文本。
            translation: 翻译。
            category: 分类。
            variants: 变体列表。
            dictionary: 目标词典，为 None 时使用内置词典。

        Returns:
            添加的术语对象。
        """
        dict_to_use = dictionary or self.dictionary
        term = Term(
            text=term_text,
            normalized=term_text,
            translation=translation,
            category=category,
            variants=variants or [],
            source="manual",
            confidence=1.0,
            score=1.0,
        )
        dict_to_use.add_term(term)
        # 更新翻译词典
        if translation:
            self.translations[term_text] = translation
        # 更新规范化映射
        if variants:
            for variant in variants:
                self.normalization_map[variant] = term_text
                self.reverse_normalization[term_text].append(variant)
        return term

    def remove_term_from_dictionary(
        self,
        term_text: str,
        dictionary: Optional[TermDictionary] = None,
    ) -> bool:
        """从词典移除术语。"""
        dict_to_use = dictionary or self.dictionary
        return dict_to_use.remove_term(term_text)

    def search_terms(
        self,
        query: str,
        dictionary: Optional[TermDictionary] = None,
        top_k: int = 20,
    ) -> List[Term]:
        """搜索术语。

        Args:
            query: 查询字符串。
            dictionary: 术语词典。
            top_k: 返回数量。

        Returns:
            匹配的术语列表。
        """
        dict_to_use = dictionary or self.dictionary
        results: List[Term] = []
        query_lower = query.lower()
        for term_text, term_obj in dict_to_use.terms.items():
            # 精确匹配
            if term_text == query:
                results.append(term_obj)
                continue
            # 包含匹配
            if query_lower in term_text.lower():
                results.append(term_obj)
                continue
            # 变体匹配
            if any(query_lower in v.lower() for v in term_obj.variants):
                results.append(term_obj)
                continue
            # 翻译匹配
            if term_obj.translation and query_lower in term_obj.translation.lower():
                results.append(term_obj)
                continue
        return results[:top_k]


# ===== 模块级单例访问 =====

def get_terminology_extractor() -> TerminologyExtractor:
    """获取全局术语提取器单例。"""
    return TerminologyExtractor.get_instance()


def extract_terms(
    text: str,
    method: str = "cvalue",
    top_k: int = 50,
) -> List[Term]:
    """模块级术语提取便捷函数。"""
    return get_terminology_extractor().extract(text, method=method, top_k=top_k)


def build_term_dictionary(
    corpus: Union[str, List[str]],
    name: str = "",
    domain: str = "",
) -> TermDictionary:
    """模块级词典构建便捷函数。"""
    return get_terminology_extractor().build_dictionary(corpus, name=name, domain=domain)


def check_term_consistency(
    text: str,
    dictionary: Optional[TermDictionary] = None,
) -> ConsistencyReport:
    """模块级一致性检查便捷函数。"""
    return get_terminology_extractor().check_consistency(text, dictionary)
