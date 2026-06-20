"""逻辑推理模块

提供完整的逻辑推理与论证分析能力，包括：
    - 演绎推理、归纳推理、类比推理、因果推理
    - 论证结构分析、论证强度评估、逻辑谬误检测
    - 假设识别、前提验证、结论推导
    - 推理链构建、推理可视化、推理验证
    - 论点识别、论据提取、论证结构分析
    - 论证强度评估、论证有效性检查、反驳识别
    - 假设形式化、假设分类、假设可测试性评估
    - 统计检验方法选择、样本量计算、功效分析

子模块：
    - logical_reasoner: 逻辑推理器主类
    - argument_analyzer: 论证分析器主类
    - hypothesis_tester: 假设检验器主类

公共导出：
    - LogicalReasoner: 逻辑推理器主类
    - ArgumentAnalyzer: 论证分析器主类
    - HypothesisTester: 假设检验器主类
    - ReasoningChain: 推理链数据结构
    - Argument: 论证数据结构
    - Hypothesis: 假设数据结构
"""
from backend.reasoning.logical_reasoner import (
    LogicalReasoner,
    ReasoningChain,
    ReasoningStep,
    LogicalFallacy,
)
from backend.reasoning.argument_analyzer import (
    ArgumentAnalyzer,
    Argument,
    ArgumentStructure,
    ArgumentStrength,
)
from backend.reasoning.hypothesis_tester import (
    HypothesisTester,
    Hypothesis,
    TestResult,
    StatisticalTest,
)

__all__ = [
    "LogicalReasoner",
    "ReasoningChain",
    "ReasoningStep",
    "LogicalFallacy",
    "ArgumentAnalyzer",
    "Argument",
    "ArgumentStructure",
    "ArgumentStrength",
    "HypothesisTester",
    "Hypothesis",
    "TestResult",
    "StatisticalTest",
]

__version__ = "8.0.0"
