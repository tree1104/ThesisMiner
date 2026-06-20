"""ThesisMiner 自然语言处理模块

提供面向中文学术文本的深度 NLP 能力，支撑：
    - 中文分词、词性标注、命名实体识别
    - 学术论文结构化解析（标题/摘要/方法/结果/参考文献等）
    - 专业术语自动提取与规范化
    - 中英文混合文本处理、繁简转换、全半角归一化
    - 中文关键词提取、摘要生成、情感分析
    - 引用识别、公式识别、术语一致性检查

子模块：
    - chinese_processor: 中文文本处理器（分词/NER/关键词/摘要/情感）
    - academic_parser: 学术文本解析器（结构识别/引用匹配/多格式支持）
    - terminology_extractor: 术语提取器（C-value/NC-value/分类/翻译）

设计原则：
    1. 零外部重依赖：核心算法仅使用 Python 标准库实现
    2. 可降级：可选依赖（jieba）缺失时自动降级为字符级处理
    3. 学术优先：针对中文学术论文场景进行专项优化
    4. 可组合：三个子模块可独立使用，也可协同工作
"""
from backend.nlp.chinese_processor import ChineseProcessor, get_chinese_processor
from backend.nlp.academic_parser import AcademicParser, get_academic_parser
from backend.nlp.terminology_extractor import (
    TerminologyExtractor,
    get_terminology_extractor,
)

__all__ = [
    # 中文处理
    "ChineseProcessor",
    "get_chinese_processor",
    # 学术解析
    "AcademicParser",
    "get_academic_parser",
    # 术语提取
    "TerminologyExtractor",
    "get_terminology_extractor",
]
