"""学术诚信模块

提供论文研究全生命周期的学术诚信检查能力，覆盖：
    - 数据造假检测、图表篡改检测、引用伪造检测
    - 自我抄袭检测、重复发表检测、不当署名检测
    - 伦理审查、利益冲突声明、数据来源追溯
    - 引用真实性验证、DOI/URL 校验、引用网络分析
    - 统计异常检测、数据分布验证、实验可重复性评估

子模块：
    - academic_integrity: 学术诚信检查器主类与多维检查规则
    - citation_verifier: 引用验证器（DOI/URL/内容匹配/网络分析）
    - data_authenticator: 数据真实性验证器（统计检验/异常检测）

公共导出：
    - AcademicIntegrityChecker: 学术诚信检查器
    - IntegrityReport: 诚信检查报告
    - CitationVerifier: 引用验证器
    - CitationVerificationReport: 引用验证报告
    - DataAuthenticator: 数据真实性验证器
    - DataAuthenticationReport: 数据验证报告
"""
from backend.integrity.academic_integrity import (
    AcademicIntegrityChecker,
    IntegrityReport,
    IntegrityIssue,
    RiskLevel,
    IntegrityDimension,
)
from backend.integrity.citation_verifier import (
    CitationVerifier,
    CitationVerificationReport,
    CitationIssue,
    CitationStatus,
)
from backend.integrity.data_authenticator import (
    DataAuthenticator,
    DataAuthenticationReport,
    DataAnomaly,
    AnomalyType,
)

__all__ = [
    "AcademicIntegrityChecker",
    "IntegrityReport",
    "IntegrityIssue",
    "RiskLevel",
    "IntegrityDimension",
    "CitationVerifier",
    "CitationVerificationReport",
    "CitationIssue",
    "CitationStatus",
    "DataAuthenticator",
    "DataAuthenticationReport",
    "DataAnomaly",
    "AnomalyType",
]

__version__ = "8.0.0"
