"""验证模块

提供论题验证、抄袭检测、质量评估的核心能力。

子模块：
    - thesis_validator: 论题验证器（标题/摘要/大纲/参考文献/方法/方案多维度验证）
    - plagiarism_detector: 抄袭检测器（SimHash/MinHash/n-gram/句子级比对）
    - quality_assessor: 质量评估器（创新性/规范性/逻辑性/实用性评估）

公共导出：
    - ThesisValidator: 论题验证器主类
    - PlagiarismDetector: 抄袭检测器主类
    - QualityAssessor: 质量评估器主类
    - ValidationReport: 验证报告数据结构
    - PlagiarismReport: 抄袭报告数据结构
    - QualityReport: 质量评估报告数据结构
"""
from backend.validation.thesis_validator import (
    ThesisValidator,
    ValidationReport,
    ValidationIssue,
    SeverityLevel,
)
from backend.validation.plagiarism_detector import (
    PlagiarismDetector,
    PlagiarismReport,
    PlagiarismMatch,
    SimHash,
    MinHash,
)
from backend.validation.quality_assessor import (
    QualityAssessor,
    QualityReport,
    QualityDimension,
    AssessmentIndicator,
)

__all__ = [
    "ThesisValidator",
    "ValidationReport",
    "ValidationIssue",
    "SeverityLevel",
    "PlagiarismDetector",
    "PlagiarismReport",
    "PlagiarismMatch",
    "SimHash",
    "MinHash",
    "QualityAssessor",
    "QualityReport",
    "QualityDimension",
    "AssessmentIndicator",
]

__version__ = "9.0.0"
