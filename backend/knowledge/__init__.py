"""知识库模块

提供学科知识库、学科分类体系、研究方法库的核心能力。

子模块：
    - knowledge_base: 知识库主体（条目 CRUD、全文检索、知识图谱、版本管理）
    - discipline_taxonomy: 学科分类体系（学科树、相似度、聚类、推荐）
    - method_library: 研究方法库（定量/定性/混合方法、推荐、评估）

公共导出：
    - KnowledgeBase: 知识库主类
    - DisciplineTaxonomy: 学科分类体系主类
    - MethodLibrary: 研究方法库主类
    - KnowledgeEntry: 知识条目数据结构
    - DisciplineNode: 学科节点数据结构
    - ResearchMethod: 研究方法数据结构
"""
from backend.knowledge.knowledge_base import (
    KnowledgeBase,
    KnowledgeEntry,
    KnowledgeCategory,
    KnowledgeRelation,
)
from backend.knowledge.discipline_taxonomy import (
    DisciplineTaxonomy,
    DisciplineNode,
    DisciplineLevel,
)
from backend.knowledge.method_library import (
    MethodLibrary,
    ResearchMethod,
    MethodCategory,
    MethodStep,
)

__all__ = [
    "KnowledgeBase",
    "KnowledgeEntry",
    "KnowledgeCategory",
    "KnowledgeRelation",
    "DisciplineTaxonomy",
    "DisciplineNode",
    "DisciplineLevel",
    "MethodLibrary",
    "ResearchMethod",
    "MethodCategory",
    "MethodStep",
]

__version__ = "9.0.0"
