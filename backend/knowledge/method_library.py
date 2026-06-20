"""研究方法库模块

提供完整的研究方法库实现，包括：
    - 定量方法 / 定性方法 / 混合方法分类管理
    - 方法适用场景、优缺点、组合推荐
    - 方法-学科关联、方法-论题匹配
    - 方法迁移建议
    - 方法详细步骤、参数、评估
    - 智能推荐算法

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可扩展：方法数据可动态添加
"""
from __future__ import annotations

import re
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Iterable, Optional


# ===== 枚举与常量 =====


class MethodCategory:
    """研究方法分类常量。"""

    QUANTITATIVE = "quantitative"  # 定量方法
    QUALITATIVE = "qualitative"    # 定性方法
    MIXED = "mixed"                # 混合方法
    THEORETICAL = "theoretical"    # 理论方法
    EMPIRICAL = "empirical"        # 经验方法


# 方法分类中文名
CATEGORY_NAMES = {
    MethodCategory.QUANTITATIVE: "定量方法",
    MethodCategory.QUALITATIVE: "定性方法",
    MethodCategory.MIXED: "混合方法",
    MethodCategory.THEORETICAL: "理论方法",
    MethodCategory.EMPIRICAL: "经验方法",
}

# 方法难度等级
DIFFICULTY_LEVELS = {
    1: "入门",
    2: "基础",
    3: "中级",
    4: "进阶",
    5: "高级",
}

# 默认研究方法数据（精选常用方法）
DEFAULT_METHODS = [
    # ===== 定量方法 =====
    {
        "id": "method_survey",
        "name": "问卷调查法",
        "category": MethodCategory.QUANTITATIVE,
        "aliases": ["问卷法", "调查问卷", "survey"],
        "description": "通过设计问卷收集大规模样本数据，进行统计分析。",
        "applicable_scenarios": [
            "大样本态度/意见调查", "消费者行为研究", "社会现象量化分析",
            "用户满意度评估", "市场需求调研",
        ],
        "advantages": [
            "可大规模收集数据", "成本相对较低", "结果可量化",
            "便于统计推断", "可重复性强",
        ],
        "disadvantages": [
            "难以深入探究原因", "回收率可能较低", "存在回答偏差",
            "问卷设计要求高", "无法捕捉复杂情境",
        ],
        "steps": [
            "明确研究目的与假设",
            "设计问卷（题项、量表、结构）",
            "小范围预测试与修订",
            "确定抽样方案",
            "发放与回收问卷",
            "数据清洗与编码",
            "统计分析（描述统计、推断统计）",
            "撰写研究报告",
        ],
        "parameters": {
            "sample_size": {"type": "int", "min": 30, "max": 100000, "default": 300},
            "response_rate": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.6},
            "scale_type": {"type": "enum", "options": ["likert", "semantic", "guttman"], "default": "likert"},
        },
        "applicable_disciplines": ["0401", "0402", "1202", "0303", "0202"],
        "data_types": ["截面数据", "纵向数据"],
        "tools": ["SPSS", "R", "Stata", "问卷星"],
        "difficulty": 2,
        "time_cost": "中",
        "cost_level": "低",
    },
    {
        "id": "method_experiment",
        "name": "实验研究法",
        "category": MethodCategory.QUANTITATIVE,
        "aliases": ["实验法", "experiment", "controlled_experiment"],
        "description": "在控制条件下操纵自变量，观察因变量变化，建立因果关系。",
        "applicable_scenarios": [
            "因果关系验证", "药物疗效评估", "心理学行为研究",
            "教学干预效果", "产品可用性测试",
        ],
        "advantages": [
            "可建立因果关系", "控制变量严谨", "可重复验证",
            "内部效度高", "结果客观",
        ],
        "disadvantages": [
            "生态效度可能较低", "伦理限制多", "成本较高",
            "难以研究复杂社会现象", "样本招募困难",
        ],
        "steps": [
            "提出研究假设",
            "确定自变量与因变量",
            "设计实验方案（对照组、随机分组）",
            "准备实验材料与设备",
            "招募被试并随机分组",
            "实施实验操纵",
            "测量与记录数据",
            "统计分析（方差分析、t检验）",
            "撰写实验报告",
        ],
        "parameters": {
            "group_count": {"type": "int", "min": 2, "max": 10, "default": 2},
            "sample_per_group": {"type": "int", "min": 10, "max": 1000, "default": 30},
            "design_type": {"type": "enum", "options": ["between", "within", "mixed"], "default": "between"},
        },
        "applicable_disciplines": ["0402", "0701", "0702", "0703", "1001", "0811"],
        "data_types": ["实验数据"],
        "tools": ["SPSS", "R", "Python", "E-Prime", "PsychoPy"],
        "difficulty": 4,
        "time_cost": "高",
        "cost_level": "中",
    },
    {
        "id": "method_regression",
        "name": "回归分析法",
        "category": MethodCategory.QUANTITATIVE,
        "aliases": ["回归分析", "regression", "线性回归"],
        "description": "建立变量间关系的数学模型，用于预测与解释。",
        "applicable_scenarios": [
            "影响因素分析", "趋势预测", "政策效果评估",
            "经济建模", "风险因素识别",
        ],
        "advantages": [
            "可量化变量关系", "支持多变量分析", "预测能力强",
            "假设检验严谨", "应用广泛",
        ],
        "disadvantages": [
            "要求数据满足假设", "易受异常值影响", "相关性不等于因果",
            "多重共线性问题", "对样本量有要求",
        ],
        "steps": [
            "明确研究问题与变量",
            "收集与整理数据",
            "探索性数据分析",
            "选择回归模型（线性/逻辑/多项式）",
            "估计模型参数",
            "模型诊断（残差、共线性、异方差）",
            "模型解释与预测",
            "稳健性检验",
        ],
        "parameters": {
            "model_type": {"type": "enum", "options": ["linear", "logistic", "polynomial", "ridge", "lasso"], "default": "linear"},
            "alpha": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.05},
            "min_samples": {"type": "int", "min": 30, "max": 100000, "default": 100},
        },
        "applicable_disciplines": ["0201", "0202", "0204", "0714", "1201"],
        "data_types": ["截面数据", "时间序列数据", "面板数据"],
        "tools": ["R", "Python", "Stata", "SPSS", "MATLAB"],
        "difficulty": 3,
        "time_cost": "中",
        "cost_level": "低",
    },
    # ===== 定性方法 =====
    {
        "id": "method_interview",
        "name": "深度访谈法",
        "category": MethodCategory.QUALITATIVE,
        "aliases": ["访谈法", "interview", "in-depth_interview"],
        "description": "通过面对面或远程访谈，深入获取受访者的观点与经历。",
        "applicable_scenarios": [
            "探索性研究", "个人经历探究", "专家意见收集",
            "敏感话题研究", "组织文化调研",
        ],
        "advantages": [
            "可深入理解现象", "灵活性高", "可追问细节",
            "适合复杂主题", "捕捉非语言信息",
        ],
        "disadvantages": [
            "样本量小", "主观性强", "耗时耗力",
            "分析复杂", "难以推广",
        ],
        "steps": [
            "确定研究问题",
            "选择访谈类型（结构化/半结构化/无结构）",
            "设计访谈提纲",
            "招募受访者",
            "进行访谈并录音",
            "转录与编码",
            "主题分析",
            "撰写研究报告",
        ],
        "parameters": {
            "interview_type": {"type": "enum", "options": ["structured", "semi-structured", "unstructured"], "default": "semi-structured"},
            "duration_minutes": {"type": "int", "min": 30, "max": 180, "default": 60},
            "sample_size": {"type": "int", "min": 5, "max": 50, "default": 15},
        },
        "applicable_disciplines": ["0303", "0401", "1202", "0501", "0602"],
        "data_types": ["文本数据", "音频数据"],
        "tools": ["NVivo", "ATLAS.ti", "录音设备", "转录软件"],
        "difficulty": 3,
        "time_cost": "高",
        "cost_level": "中",
    },
    {
        "id": "method_case_study",
        "name": "案例研究法",
        "category": MethodCategory.QUALITATIVE,
        "aliases": ["案例分析", "case_study", "个案研究"],
        "description": "对单个或多个案例进行深入、全面的分析。",
        "applicable_scenarios": [
            "典型现象剖析", "组织管理研究", "政策实施评估",
            "历史事件分析", "教学案例开发",
        ],
        "advantages": [
            "研究深入全面", "结合真实情境", "适合回答如何/为什么",
            "理论构建能力强", "可多案例比较",
        ],
        "disadvantages": [
            "外部效度有限", "易受研究者偏见影响", "耗时较长",
            "数据量大", "结论难以推广",
        ],
        "steps": [
            "界定研究问题与案例",
            "选择案例（单案例/多案例）",
            "确定数据来源（文档、访谈、观察）",
            "收集多源数据",
            "案例内分析",
            "跨案例分析（多案例）",
            "理论提炼",
            "撰写案例报告",
        ],
        "parameters": {
            "case_count": {"type": "int", "min": 1, "max": 20, "default": 3},
            "data_sources": {"type": "list", "options": ["document", "interview", "observation", "archive"], "default": ["document", "interview"]},
        },
        "applicable_disciplines": ["1202", "1204", "0301", "0302", "0602"],
        "data_types": ["文本数据", "档案数据"],
        "tools": ["NVivo", "文档管理工具", "时间线工具"],
        "difficulty": 3,
        "time_cost": "高",
        "cost_level": "低",
    },
    {
        "id": "method_ethnography",
        "name": "民族志研究法",
        "category": MethodCategory.QUALITATIVE,
        "aliases": ["田野调查", "ethnography", "fieldwork"],
        "description": "研究者长期深入研究对象群体，通过参与观察理解其文化。",
        "applicable_scenarios": [
            "文化研究", "社群研究", "组织文化探究",
            "亚文化群体研究", "跨文化比较",
        ],
        "advantages": [
            "理解深入", "情境真实", "发现隐含文化",
            "理论扎根实践", "适合独特群体",
        ],
        "disadvantages": [
            "耗时极长", "研究者介入影响", "伦理问题复杂",
            "主观性强", "难以复制",
        ],
        "steps": [
            "选择研究田野",
            "获得进入许可",
            "参与观察（长期）",
            "田野笔记记录",
            "深度访谈补充",
            "文化主题分析",
            "撰写民族志",
        ],
        "parameters": {
            "field_duration_months": {"type": "int", "min": 3, "max": 36, "default": 12},
            "participation_level": {"type": "enum", "options": ["observer", "participant", "complete"], "default": "participant"},
        },
        "applicable_disciplines": ["0303", "0304", "0501", "0602", "0401"],
        "data_types": ["田野笔记", "访谈记录", "影像资料"],
        "tools": ["田野笔记本", "录音设备", "相机"],
        "difficulty": 5,
        "time_cost": "极高",
        "cost_level": "中",
    },
    # ===== 混合方法 =====
    {
        "id": "method_mixed_sequential",
        "name": "顺序混合方法",
        "category": MethodCategory.MIXED,
        "aliases": ["顺序解释设计", "sequential_mixed"],
        "description": "先进行定量研究，再用定性研究解释结果（或反之）。",
        "applicable_scenarios": [
            "复杂现象综合研究", "定量结果深入解释", "理论构建与验证",
            "政策评估", "教育干预研究",
        ],
        "advantages": [
            "优势互补", "研究全面", "结论更可信",
            "可发现单一方法遗漏的问题", "适合复杂问题",
        ],
        "disadvantages": [
            "耗时较长", "成本较高", "整合分析困难",
            "对研究者能力要求高", "可能产生矛盾结论",
        ],
        "steps": [
            "确定研究问题与混合设计",
            "实施第一阶段研究（定量/定性）",
            "分析第一阶段结果",
            "基于第一阶段设计第二阶段",
            "实施第二阶段研究",
            "整合两阶段数据",
            "综合分析与解释",
            "撰写混合方法报告",
        ],
        "parameters": {
            "sequence": {"type": "enum", "options": ["quant_qual", "qual_quant", "concurrent"], "default": "quant_qual"},
            "priority": {"type": "enum", "options": ["equal", "quant_dominant", "qual_dominant"], "default": "equal"},
        },
        "applicable_disciplines": ["0401", "0402", "1202", "0303", "0202"],
        "data_types": ["定量数据", "定性数据"],
        "tools": ["SPSS", "NVivo", "R", "Python"],
        "difficulty": 5,
        "time_cost": "极高",
        "cost_level": "高",
    },
    # ===== 理论方法 =====
    {
        "id": "method_literature_review",
        "name": "文献研究法",
        "category": MethodCategory.THEORETICAL,
        "aliases": ["文献综述", "文献分析", "literature_review"],
        "description": "系统收集、分析已有文献，梳理研究脉络。",
        "applicable_scenarios": [
            "研究综述撰写", "理论建构", "研究缺口识别",
            "概念辨析", "学术史梳理",
        ],
        "advantages": [
            "成本较低", "可追溯发展脉络", "适合理论构建",
            "无伦理风险", "可发现研究缺口",
        ],
        "disadvantages": [
            "依赖文献质量", "可能存在发表偏差", "时效性有限",
            "整合分析困难", "主观性较强",
        ],
        "steps": [
            "确定研究主题与范围",
            "制定检索策略",
            "数据库检索与筛选",
            "文献质量评估",
            "信息提取与编码",
            "主题/叙述性综合",
            "撰写综述",
        ],
        "parameters": {
            "review_type": {"type": "enum", "options": ["narrative", "systematic", "scoping", "meta"], "default": "narrative"},
            "time_span_years": {"type": "int", "min": 1, "max": 50, "default": 10},
        },
        "applicable_disciplines": ["0101", "0104", "0601", "0602", "0603", "0712"],
        "data_types": ["文献数据"],
        "tools": ["EndNote", "Zotero", "Mendeley", "VOSviewer"],
        "difficulty": 2,
        "time_cost": "中",
        "cost_level": "低",
    },
    {
        "id": "method_meta_analysis",
        "name": "元分析法",
        "category": MethodCategory.QUANTITATIVE,
        "aliases": ["meta分析", "荟萃分析", "meta_analysis"],
        "description": "对多项独立研究的结果进行统计整合，得出综合结论。",
        "applicable_scenarios": [
            "矛盾研究结果整合", "效应量综合估计", "证据强度评估",
            " moderator 分析", "发表偏差检验",
        ],
        "advantages": [
            "提高统计效力", "结论更可靠", "可识别 moderator",
            "量化整合", "证据等级高",
        ],
        "disadvantages": [
            "依赖原始研究质量", "异质性问题", "发表偏差",
            "苹果与橘子问题", "工作量大",
        ],
        "steps": [
            "提出研究问题",
            "制定纳入排除标准",
            "系统检索文献",
            "数据提取与质量评价",
            "计算效应量",
            "异质性检验",
            "合并效应量（固定/随机效应模型）",
            "亚组分析与敏感性分析",
            "发表偏差检验",
            "撰写元分析报告",
        ],
        "parameters": {
            "effect_model": {"type": "enum", "options": ["fixed", "random"], "default": "random"},
            "min_studies": {"type": "int", "min": 2, "max": 1000, "default": 5},
        },
        "applicable_disciplines": ["1001", "1002", "0401", "0402", "0710"],
        "data_types": ["文献数据", "效应量数据"],
        "tools": ["RevMan", "CMA", "R", "Stata"],
        "difficulty": 5,
        "time_cost": "高",
        "cost_level": "低",
    },
]


# ===== 数据结构 =====


@dataclass
class MethodStep:
    """研究方法步骤。

    Attributes:
        order: 步骤序号（从1开始）。
        name: 步骤名称。
        description: 步骤详细描述。
        duration_estimate: 预计耗时。
        required: 是否必需。
        tips: 实施建议。
    """

    order: int = 0
    name: str = ""
    description: str = ""
    duration_estimate: str = ""
    required: bool = True
    tips: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MethodParameter:
    """研究方法参数。

    Attributes:
        name: 参数名。
        param_type: 参数类型（int/float/enum/list/string）。
        description: 参数描述。
        default: 默认值。
        options: 可选值（enum/list 类型）。
        min_value: 最小值（数值类型）。
        max_value: 最大值（数值类型）。
        required: 是否必需。
    """

    name: str = ""
    param_type: str = "string"
    description: str = ""
    default: Any = None
    options: list[Any] = field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchMethod:
    """研究方法数据结构。

    Attributes:
        id: 方法 ID。
        name: 方法名称。
        category: 方法分类。
        aliases: 别名列表。
        description: 方法描述。
        applicable_scenarios: 适用场景列表。
        advantages: 优点列表。
        disadvantages: 缺点列表。
        steps: 实施步骤列表。
        parameters: 方法参数。
        applicable_disciplines: 适用学科代码列表。
        data_types: 适用数据类型。
        tools: 推荐工具。
        difficulty: 难度（1-5）。
        time_cost: 时间成本（低/中/高/极高）。
        cost_level: 经济成本（低/中/高）。
        keywords: 关键词。
        related_methods: 相关方法 ID。
        metadata: 扩展元数据。
    """

    id: str = ""
    name: str = ""
    category: str = MethodCategory.QUANTITATIVE
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    applicable_scenarios: list[str] = field(default_factory=list)
    advantages: list[str] = field(default_factory=list)
    disadvantages: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    applicable_disciplines: list[str] = field(default_factory=list)
    data_types: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    difficulty: int = 3
    time_cost: str = "中"
    cost_level: str = "低"
    keywords: list[str] = field(default_factory=list)
    related_methods: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchMethod":
        defaults = cls().__dict__
        merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        return cls(**merged)

    def get_detailed_steps(self) -> list[MethodStep]:
        """获取详细步骤对象列表。"""
        return [
            MethodStep(
                order=i + 1,
                name=step if isinstance(step, str) else step.get("name", ""),
                description=step if isinstance(step, str) else step.get("description", ""),
            )
            for i, step in enumerate(self.steps)
        ]

    def get_parameters(self) -> list[MethodParameter]:
        """获取参数对象列表。"""
        result: list[MethodParameter] = []
        for name, spec in self.parameters.items():
            result.append(MethodParameter(
                name=name,
                param_type=spec.get("type", "string"),
                description=spec.get("description", ""),
                default=spec.get("default"),
                options=spec.get("options", []),
                min_value=spec.get("min"),
                max_value=spec.get("max"),
                required=spec.get("required", False),
            ))
        return result


# ===== 工具函数 =====


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串。"""
    return datetime.now().isoformat()


def _new_id(prefix: str = "method") -> str:
    """生成带前缀的唯一 ID。"""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


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


def _jaccard(set1: set[str], set2: set[str]) -> float:
    """Jaccard 相似度。"""
    if not set1 and not set2:
        return 0.0
    union = set1 | set2
    if not union:
        return 0.0
    return len(set1 & set2) / len(union)


# ===== 研究方法库主类 =====


class MethodLibrary:
    """研究方法库主类。

    管理研究方法的完整生命周期，提供：
        - 方法 CRUD
        - 分类管理（定量/定性/混合/理论/经验）
        - 适用场景查询
        - 优缺点对比
        - 方法组合推荐
        - 方法-学科关联
        - 方法-论题匹配
        - 方法迁移建议
        - 方法评估

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self) -> None:
        """初始化研究方法库，自动加载默认方法。"""
        self._lock = threading.RLock()
        # id -> ResearchMethod
        self._methods: dict[str, ResearchMethod] = {}
        # name/alias -> id（名称索引）
        self._name_index: dict[str, str] = {}
        # category -> set of id
        self._category_index: dict[str, set[str]] = defaultdict(set)
        # discipline_code -> set of id
        self._discipline_index: dict[str, set[str]] = defaultdict(set)
        # keyword -> set of id
        self._keyword_index: dict[str, set[str]] = defaultdict(set)
        # 方法组合缓存
        self._combination_cache: dict[str, list[dict[str, Any]]] = {}
        # 加载默认方法
        self._load_default_methods()

    def _load_default_methods(self) -> None:
        """加载默认研究方法数据。"""
        for method_data in DEFAULT_METHODS:
            method = ResearchMethod.from_dict(method_data)
            self._add_method_internal(method)

    def _add_method_internal(self, method: ResearchMethod) -> None:
        """内部添加方法（不加锁）。"""
        self._methods[method.id] = method
        self._name_index[method.name] = method.id
        for alias in method.aliases:
            self._name_index[alias] = method.id
        self._category_index[method.category].add(method.id)
        for disc in method.applicable_disciplines:
            self._discipline_index[disc].add(method.id)
        # 自动提取关键词
        if not method.keywords:
            method.keywords = self._extract_keywords(method)
        for kw in method.keywords:
            self._keyword_index[kw].add(method.id)

    def _extract_keywords(self, method: ResearchMethod) -> list[str]:
        """从方法信息中提取关键词。"""
        keywords: list[str] = [method.name]
        keywords.extend(method.aliases)
        # 从描述提取
        tokens = _tokenize(method.description)
        # 取频率较高的
        freq: dict[str, int] = defaultdict(int)
        for t in tokens:
            freq[t] += 1
        sorted_tokens = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        for token, _ in sorted_tokens[:5]:
            if token not in keywords:
                keywords.append(token)
        return keywords

    # ===== 方法 CRUD =====

    def add_method(self, name: str, category: str, description: str = "",
                   aliases: Optional[list[str]] = None,
                   applicable_scenarios: Optional[list[str]] = None,
                   advantages: Optional[list[str]] = None,
                   disadvantages: Optional[list[str]] = None,
                   steps: Optional[list[str]] = None,
                   parameters: Optional[dict[str, dict[str, Any]]] = None,
                   applicable_disciplines: Optional[list[str]] = None,
                   data_types: Optional[list[str]] = None,
                   tools: Optional[list[str]] = None,
                   difficulty: int = 3, time_cost: str = "中",
                   cost_level: str = "低",
                   keywords: Optional[list[str]] = None,
                   related_methods: Optional[list[str]] = None,
                   metadata: Optional[dict[str, Any]] = None) -> str:
        """添加研究方法。

        Args:
            name: 方法名称。
            category: 方法分类。
            description: 方法描述。
            其他参数见 ResearchMethod。

        Returns:
            新建方法的 ID。

        Raises:
            ValueError: 名称为空或分类无效。
        """
        if not name or not name.strip():
            raise ValueError("方法名称不能为空")
        if category not in CATEGORY_NAMES:
            raise ValueError(f"未知方法分类: {category}")
        with self._lock:
            method_id = _new_id()
            method = ResearchMethod(
                id=method_id,
                name=name.strip(),
                category=category,
                aliases=aliases or [],
                description=description,
                applicable_scenarios=applicable_scenarios or [],
                advantages=advantages or [],
                disadvantages=disadvantages or [],
                steps=steps or [],
                parameters=parameters or {},
                applicable_disciplines=applicable_disciplines or [],
                data_types=data_types or [],
                tools=tools or [],
                difficulty=max(1, min(5, difficulty)),
                time_cost=time_cost,
                cost_level=cost_level,
                keywords=keywords or [],
                related_methods=related_methods or [],
                metadata=metadata or {},
            )
            self._add_method_internal(method)
            return method_id

    def get_method(self, method_id: str) -> Optional[ResearchMethod]:
        """按 ID 获取方法。"""
        with self._lock:
            return self._methods.get(method_id)

    def get_by_name(self, name: str) -> Optional[ResearchMethod]:
        """按名称或别名获取方法。"""
        with self._lock:
            method_id = self._name_index.get(name)
            if method_id:
                return self._methods.get(method_id)
            return None

    def update_method(self, method_id: str, **kwargs: Any) -> bool:
        """更新方法。

        Args:
            method_id: 方法 ID。
            **kwargs: 要更新的字段。

        Returns:
            是否更新成功。
        """
        with self._lock:
            method = self._methods.get(method_id)
            if method is None:
                return False
            # 移除旧索引
            self._name_index.pop(method.name, None)
            for alias in method.aliases:
                self._name_index.pop(alias, None)
            self._category_index[method.category].discard(method_id)
            for disc in method.applicable_disciplines:
                self._discipline_index[disc].discard(method_id)
            for kw in method.keywords:
                self._keyword_index[kw].discard(method_id)
            # 应用更新
            for key, value in kwargs.items():
                if hasattr(method, key):
                    setattr(method, key, value)
            # 重建索引
            self._name_index[method.name] = method_id
            for alias in method.aliases:
                self._name_index[alias] = method_id
            self._category_index[method.category].add(method_id)
            for disc in method.applicable_disciplines:
                self._discipline_index[disc].add(method_id)
            for kw in method.keywords:
                self._keyword_index[kw].add(method_id)
            # 失效组合缓存
            self._combination_cache.clear()
            return True

    def delete_method(self, method_id: str) -> bool:
        """删除方法。"""
        with self._lock:
            method = self._methods.get(method_id)
            if method is None:
                return False
            # 清理索引
            self._name_index.pop(method.name, None)
            for alias in method.aliases:
                self._name_index.pop(alias, None)
            self._category_index[method.category].discard(method_id)
            for disc in method.applicable_disciplines:
                self._discipline_index[disc].discard(method_id)
            for kw in method.keywords:
                self._keyword_index[kw].discard(method_id)
            del self._methods[method_id]
            self._combination_cache.clear()
            return True

    # ===== 分类查询 =====

    def list_by_category(self, category: str) -> list[ResearchMethod]:
        """按分类列出方法。"""
        with self._lock:
            ids = self._category_index.get(category, set())
            return [self._methods[mid] for mid in ids if mid in self._methods]

    def list_all(self) -> list[ResearchMethod]:
        """列出所有方法。"""
        with self._lock:
            return list(self._methods.values())

    def list_by_discipline(self, discipline_code: str) -> list[ResearchMethod]:
        """按学科列出适用方法。"""
        with self._lock:
            ids = self._discipline_index.get(discipline_code, set())
            return [self._methods[mid] for mid in ids if mid in self._methods]

    def list_by_difficulty(self, max_difficulty: int) -> list[ResearchMethod]:
        """列出难度不超过指定级别的方法。"""
        with self._lock:
            return [m for m in self._methods.values() if m.difficulty <= max_difficulty]

    def list_by_data_type(self, data_type: str) -> list[ResearchMethod]:
        """按数据类型列出方法。"""
        with self._lock:
            return [m for m in self._methods.values() if data_type in m.data_types]

    # ===== 方法对比 =====

    def compare_methods(self, method_ids: list[str]) -> dict[str, Any]:
        """对比多个方法。

        Args:
            method_ids: 方法 ID 列表。

        Returns:
            对比结果字典。
        """
        with self._lock:
            methods = [self._methods.get(mid) for mid in method_ids]
            methods = [m for m in methods if m is not None]
            if len(methods) < 2:
                return {"error": "至少需要两个有效方法"}
            return {
                "methods": [m.to_dict() for m in methods],
                "comparison": {
                    "difficulty": {m.name: m.difficulty for m in methods},
                    "time_cost": {m.name: m.time_cost for m in methods},
                    "cost_level": {m.name: m.cost_level for m in methods},
                    "advantages_count": {m.name: len(m.advantages) for m in methods},
                    "disadvantages_count": {m.name: len(m.disadvantages) for m in methods},
                    "steps_count": {m.name: len(m.steps) for m in methods},
                    "disciplines_count": {m.name: len(m.applicable_disciplines) for m in methods},
                },
                "common_advantages": self._find_common(methods, "advantages"),
                "common_disadvantages": self._find_common(methods, "disadvantages"),
                "common_disciplines": self._find_common(methods, "applicable_disciplines"),
            }

    def _find_common(self, methods: list[ResearchMethod], attr: str) -> list[str]:
        """找出多个方法共有的属性值。"""
        if not methods:
            return []
        sets = [set(getattr(m, attr)) for m in methods]
        common = sets[0]
        for s in sets[1:]:
            common = common & s
        return list(common)

    # ===== 方法组合推荐 =====

    def recommend_combination(self, research_topic: str,
                              discipline_code: str = "",
                              max_methods: int = 3) -> list[dict[str, Any]]:
        """推荐方法组合。

        基于研究主题与学科，推荐互补的方法组合。

        Args:
            research_topic: 研究主题。
            discipline_code: 学科代码。
            max_methods: 最多推荐方法数。

        Returns:
            推荐组合列表，每项包含方法、角色、理由。
        """
        cache_key = f"{research_topic}:{discipline_code}:{max_methods}"
        with self._lock:
            if cache_key in self._combination_cache:
                return self._combination_cache[cache_key]
            # 匹配候选方法
            candidates = self._match_methods_by_text(research_topic)
            if discipline_code:
                # 优先学科匹配的方法
                disc_methods = self.list_by_discipline(discipline_code)
                disc_ids = {m.id for m in disc_methods}
                candidates.sort(key=lambda x: (0 if x[0] in disc_ids else 1, -x[1]))
            if not candidates:
                return []
            results: list[dict[str, Any]] = []
            used_categories: set[str] = set()
            for method_id, score in candidates:
                method = self._methods.get(method_id)
                if method is None:
                    continue
                # 优先不同分类的方法（互补）
                if method.category in used_categories and len(results) >= 1:
                    continue
                used_categories.add(method.category)
                role = self._determine_method_role(method, results)
                results.append({
                    "method": method.to_dict(),
                    "role": role,
                    "match_score": round(score, 4),
                    "reason": self._generate_combination_reason(method, role, research_topic),
                })
                if len(results) >= max_methods:
                    break
            self._combination_cache[cache_key] = results
            return results

    def _match_methods_by_text(self, text: str) -> list[tuple[str, float]]:
        """通过文本匹配方法。

        Returns:
            (method_id, score) 元组列表，按分数降序。
        """
        text_tokens = set(_tokenize(text))
        if not text_tokens:
            return []
        scores: list[tuple[str, float]] = []
        for method_id, method in self._methods.items():
            score = 0.0
            # 名称匹配
            if method.name in text:
                score += 3.0
            # 别名匹配
            for alias in method.aliases:
                if alias in text:
                    score += 2.0
            # 关键词重叠
            method_kw_set = set(method.keywords)
            overlap = text_tokens & method_kw_set
            score += len(overlap) * 1.0
            # 适用场景匹配
            for scenario in method.applicable_scenarios:
                scenario_tokens = set(_tokenize(scenario))
                scenario_overlap = text_tokens & scenario_tokens
                score += len(scenario_overlap) * 0.5
            if score > 0:
                scores.append((method_id, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _determine_method_role(self, method: ResearchMethod,
                               existing: list[dict[str, Any]]) -> str:
        """确定方法在组合中的角色。"""
        if not existing:
            return "primary"
        existing_categories = {e["method"]["category"] for e in existing}
        if method.category == MethodCategory.QUANTITATIVE:
            if MethodCategory.QUALITATIVE in existing_categories:
                return "validation"
            return "primary"
        elif method.category == MethodCategory.QUALITATIVE:
            if MethodCategory.QUANTITATIVE in existing_categories:
                return "explanation"
            return "exploratory"
        elif method.category == MethodCategory.MIXED:
            return "integration"
        elif method.category == MethodCategory.THEORETICAL:
            return "foundation"
        else:
            return "supplementary"

    def _generate_combination_reason(self, method: ResearchMethod,
                                     role: str, topic: str) -> str:
        """生成组合推荐理由。"""
        role_names = {
            "primary": "主要方法",
            "validation": "验证方法",
            "explanation": "解释方法",
            "exploratory": "探索方法",
            "integration": "整合方法",
            "foundation": "理论基础",
            "supplementary": "补充方法",
        }
        role_name = role_names.get(role, "辅助方法")
        return (
            f"{method.name}作为{role_name}，"
            f"适合{method.applicable_scenarios[0] if method.applicable_scenarios else '该研究主题'}，"
            f"难度{DIFFICULTY_LEVELS.get(method.difficulty, '中等')}，"
            f"时间成本{method.time_cost}。"
        )

    # ===== 方法-论题匹配 =====

    def match_topic(self, topic: str, discipline_code: str = "",
                    top_k: int = 5) -> list[dict[str, Any]]:
        """匹配研究主题的方法。

        Args:
            topic: 研究主题。
            discipline_code: 学科代码。
            top_k: 返回数量。

        Returns:
            匹配结果列表。
        """
        with self._lock:
            candidates = self._match_methods_by_text(topic)
            if not candidates:
                return []
            results: list[dict[str, Any]] = []
            max_score = candidates[0][1] if candidates else 1.0
            if max_score == 0:
                return []
            for method_id, score in candidates[:top_k]:
                method = self._methods.get(method_id)
                if method is None:
                    continue
                normalized = score / max_score
                # 学科匹配加分
                discipline_match = (
                    discipline_code in method.applicable_disciplines
                    if discipline_code else False
                )
                if discipline_match:
                    normalized = min(1.0, normalized + 0.2)
                results.append({
                    "method": method.to_dict(),
                    "match_score": round(normalized, 4),
                    "discipline_match": discipline_match,
                    "match_reasons": self._generate_match_reasons(method, topic),
                })
            return results

    def _generate_match_reasons(self, method: ResearchMethod, topic: str) -> list[str]:
        """生成匹配理由。"""
        reasons: list[str] = []
        if method.name in topic:
            reasons.append(f"主题直接提及方法名「{method.name}」")
        for alias in method.aliases:
            if alias in topic:
                reasons.append(f"主题包含方法别名「{alias}」")
                break
        # 关键词匹配
        topic_tokens = set(_tokenize(topic))
        matched_kw = topic_tokens & set(method.keywords)
        if matched_kw:
            reasons.append(f"关键词匹配：{', '.join(list(matched_kw)[:3])}")
        # 场景匹配
        for scenario in method.applicable_scenarios:
            scenario_tokens = set(_tokenize(scenario))
            if topic_tokens & scenario_tokens:
                reasons.append(f"适用场景：{scenario}")
                break
        if not reasons:
            reasons.append("基于方法描述的语义相关性")
        return reasons

    # ===== 方法迁移建议 =====

    def suggest_method_transfer(self, source_method_id: str,
                                target_discipline_code: str) -> dict[str, Any]:
        """建议方法迁移。

        分析某方法在原学科的应用，建议如何迁移到目标学科。

        Args:
            source_method_id: 源方法 ID。
            target_discipline_code: 目标学科代码。

        Returns:
            迁移建议字典。
        """
        with self._lock:
            method = self._methods.get(source_method_id)
            if method is None:
                return {"error": "方法不存在"}
            # 检查是否已适用
            already_applicable = target_discipline_code in method.applicable_disciplines
            # 分析迁移可行性
            feasibility = self._assess_transfer_feasibility(method, target_discipline_code)
            # 生成调整建议
            adjustments = self._generate_transfer_adjustments(method, target_discipline_code)
            # 查找目标学科已有方法
            existing_methods = self.list_by_discipline(target_discipline_code)
            return {
                "method": method.to_dict(),
                "target_discipline": target_discipline_code,
                "already_applicable": already_applicable,
                "feasibility_score": feasibility["score"],
                "feasibility_level": feasibility["level"],
                "feasibility_reasons": feasibility["reasons"],
                "adjustments": adjustments,
                "existing_methods_in_discipline": [
                    {"id": m.id, "name": m.name} for m in existing_methods
                ],
                "potential_advantages": self._transfer_advantages(method, target_discipline_code),
                "potential_challenges": self._transfer_challenges(method, target_discipline_code),
            }

    def _assess_transfer_feasibility(self, method: ResearchMethod,
                                      target_discipline: str) -> dict[str, Any]:
        """评估方法迁移可行性。"""
        score = 50  # 基础分
        reasons: list[str] = []
        # 方法的通用性
        if len(method.applicable_disciplines) >= 5:
            score += 20
            reasons.append("方法适用学科广泛，通用性强")
        elif len(method.applicable_disciplines) >= 3:
            score += 10
            reasons.append("方法适用多学科，有一定通用性")
        # 难度
        if method.difficulty <= 2:
            score += 15
            reasons.append("方法难度较低，易于迁移")
        elif method.difficulty >= 4:
            score -= 10
            reasons.append("方法难度较高，迁移需较多培训")
        # 数据类型通用性
        if "文本数据" in method.data_types or "截面数据" in method.data_types:
            score += 10
            reasons.append("方法所需数据类型常见，易获取")
        # 工具可获得性
        if any(tool in ["R", "Python", "SPSS"] for tool in method.tools):
            score += 5
            reasons.append("方法工具开源易得")
        score = max(0, min(100, score))
        if score >= 80:
            level = "high"
        elif score >= 60:
            level = "medium"
        else:
            level = "low"
        return {"score": score, "level": level, "reasons": reasons}

    def _generate_transfer_adjustments(self, method: ResearchMethod,
                                       target_discipline: str) -> list[str]:
        """生成迁移调整建议。"""
        adjustments: list[str] = []
        # 基于学科差异的建议
        if method.category == MethodCategory.QUANTITATIVE:
            adjustments.append("需根据目标学科特点调整测量量表与指标")
            adjustments.append("建议先进行小范围预测试，验证方法适用性")
        elif method.category == MethodCategory.QUALITATIVE:
            adjustments.append("需调整访谈提纲以符合目标学科话语体系")
            adjustments.append("建议邀请目标学科专家参与研究设计")
        elif method.category == MethodCategory.MIXED:
            adjustments.append("需重新平衡定量与定性部分的比例")
            adjustments.append("建议根据目标学科研究范式调整整合策略")
        # 基于难度的建议
        if method.difficulty >= 4:
            adjustments.append("建议组建跨学科团队，弥补方法经验不足")
        # 基于工具的建议
        if method.tools:
            adjustments.append(f"推荐使用工具：{', '.join(method.tools[:3])}")
        return adjustments

    def _transfer_advantages(self, method: ResearchMethod,
                             target_discipline: str) -> list[str]:
        """迁移潜在优势。"""
        advantages: list[str] = []
        advantages.append(f"为{target_discipline}引入新研究视角")
        if method.category == MethodCategory.QUANTITATIVE:
            advantages.append("增强目标学科研究的量化严谨性")
        elif method.category == MethodCategory.QUALITATIVE:
            advantages.append("丰富目标学科的深度理解能力")
        advantages.append("促进跨学科交流与方法创新")
        return advantages

    def _transfer_challenges(self, method: ResearchMethod,
                             target_discipline: str) -> list[str]:
        """迁移潜在挑战。"""
        challenges: list[str] = []
        if method.difficulty >= 4:
            challenges.append("方法学习曲线陡峭，需投入较多时间")
        if method.time_cost in ["高", "极高"]:
            challenges.append("方法实施耗时较长，需合理规划")
        if method.cost_level == "高":
            challenges.append("方法实施成本较高，需确保经费支持")
        challenges.append("可能面临目标学科同行的方法接受度问题")
        return challenges

    # ===== 方法评估 =====

    def evaluate_method(self, method_id: str, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """评估方法在特定情境下的适用性。

        Args:
            method_id: 方法 ID。
            context: 评估情境（可包含 discipline, time_constraint, budget, sample_size 等）。

        Returns:
            评估结果字典。
        """
        with self._lock:
            method = self._methods.get(method_id)
            if method is None:
                return {"error": "方法不存在"}
            context = context or {}
            scores: dict[str, float] = {}
            # 适用性评分
            scores["applicability"] = self._score_applicability(method, context)
            # 可行性评分
            scores["feasibility"] = self._score_feasibility(method, context)
            # 严谨性评分
            scores["rigor"] = self._score_rigor(method, context)
            # 效率评分
            scores["efficiency"] = self._score_efficiency(method, context)
            # 创新性评分
            scores["innovation"] = self._score_innovation(method, context)
            # 综合评分
            weights = {
                "applicability": 0.3,
                "feasibility": 0.25,
                "rigor": 0.2,
                "efficiency": 0.15,
                "innovation": 0.1,
            }
            overall = sum(scores[k] * weights[k] for k in scores)
            return {
                "method_id": method.id,
                "method_name": method.name,
                "scores": {k: round(v, 2) for k, v in scores.items()},
                "overall_score": round(overall, 2),
                "recommendation": self._score_to_recommendation(overall),
                "notes": self._generate_evaluation_notes(method, scores, context),
            }

    def _score_applicability(self, method: ResearchMethod, context: dict[str, Any]) -> float:
        """适用性评分。"""
        score = 50.0
        discipline = context.get("discipline", "")
        if discipline and discipline in method.applicable_disciplines:
            score += 30
        elif discipline:
            score -= 10
        # 场景匹配
        topic = context.get("topic", "")
        if topic:
            for scenario in method.applicable_scenarios:
                if any(kw in topic for kw in _tokenize(scenario)):
                    score += 10
                    break
        return max(0, min(100, score))

    def _score_feasibility(self, method: ResearchMethod, context: dict[str, Any]) -> float:
        """可行性评分。"""
        score = 70.0
        # 时间约束
        time_constraint = context.get("time_constraint", "")
        if time_constraint == "tight":
            if method.time_cost in ["高", "极高"]:
                score -= 25
            elif method.time_cost == "中":
                score -= 10
        # 预算约束
        budget = context.get("budget", "")
        if budget == "low":
            if method.cost_level == "高":
                score -= 20
            elif method.cost_level == "中":
                score -= 10
        # 难度
        researcher_level = context.get("researcher_level", "intermediate")
        if researcher_level == "beginner" and method.difficulty >= 4:
            score -= 20
        elif researcher_level == "beginner" and method.difficulty == 3:
            score -= 10
        return max(0, min(100, score))

    def _score_rigor(self, method: ResearchMethod, context: dict[str, Any]) -> float:
        """严谨性评分。"""
        score = 50.0
        if method.category == MethodCategory.QUANTITATIVE:
            score += 25
        elif method.category == MethodCategory.MIXED:
            score += 20
        elif method.category == MethodCategory.QUALITATIVE:
            score += 15
        # 步骤完整性
        if len(method.steps) >= 8:
            score += 15
        elif len(method.steps) >= 5:
            score += 10
        # 参数规范性
        if method.parameters:
            score += 10
        return max(0, min(100, score))

    def _score_efficiency(self, method: ResearchMethod, context: dict[str, Any]) -> float:
        """效率评分。"""
        score = 50.0
        time_map = {"低": 30, "中": 20, "高": 10, "极高": 0}
        cost_map = {"低": 20, "中": 10, "高": 0}
        score += time_map.get(method.time_cost, 20)
        score += cost_map.get(method.cost_level, 10)
        # 难度越高效率越低
        score -= (method.difficulty - 1) * 5
        return max(0, min(100, score))

    def _score_innovation(self, method: ResearchMethod, context: dict[str, Any]) -> float:
        """创新性评分。"""
        score = 50.0
        # 混合方法创新性较高
        if method.category == MethodCategory.MIXED:
            score += 20
        # 难度高的方法可能更创新
        if method.difficulty >= 4:
            score += 15
        # 适用学科少的方法在跨学科应用时更创新
        if len(method.applicable_disciplines) <= 3:
            score += 15
        return max(0, min(100, score))

    def _score_to_recommendation(self, score: float) -> str:
        """分数转推荐等级。"""
        if score >= 80:
            return "强烈推荐"
        elif score >= 65:
            return "推荐"
        elif score >= 50:
            return "可考虑"
        elif score >= 35:
            return "需谨慎"
        else:
            return "不推荐"

    def _generate_evaluation_notes(self, method: ResearchMethod,
                                   scores: dict[str, float],
                                   context: dict[str, Any]) -> list[str]:
        """生成评估备注。"""
        notes: list[str] = []
        # 低分项警告
        for dim, score in scores.items():
            if score < 40:
                dim_names = {
                    "applicability": "适用性",
                    "feasibility": "可行性",
                    "rigor": "严谨性",
                    "efficiency": "效率",
                    "innovation": "创新性",
                }
                notes.append(f"⚠ {dim_names.get(dim, dim)}评分较低（{score:.1f}），需重点关注")
        # 优势提示
        for dim, score in scores.items():
            if score >= 80:
                dim_names = {
                    "applicability": "适用性",
                    "feasibility": "可行性",
                    "rigor": "严谨性",
                    "efficiency": "效率",
                    "innovation": "创新性",
                }
                notes.append(f"✓ {dim_names.get(dim, dim)}表现优异（{score:.1f}）")
        return notes

    # ===== 智能推荐 =====

    def recommend_for_research(self, topic: str, discipline_code: str = "",
                               constraints: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """为研究综合推荐方法。

        Args:
            topic: 研究主题。
            discipline_code: 学科代码。
            constraints: 约束条件（time, budget, level 等）。

        Returns:
            综合推荐结果。
        """
        with self._lock:
            constraints = constraints or {}
            # 单方法匹配
            matches = self.match_topic(topic, discipline_code, top_k=10)
            # 组合推荐
            combinations = self.recommend_combination(topic, discipline_code, max_methods=3)
            # 评估每个匹配方法
            evaluations: list[dict[str, Any]] = []
            context = {
                "topic": topic,
                "discipline": discipline_code,
                "time_constraint": constraints.get("time", ""),
                "budget": constraints.get("budget", ""),
                "researcher_level": constraints.get("level", "intermediate"),
            }
            for match in matches[:5]:
                method = ResearchMethod.from_dict(match["method"])
                evaluation = self.evaluate_method(method.id, context)
                evaluations.append({
                    "method": match["method"],
                    "match_score": match["match_score"],
                    "evaluation": evaluation,
                })
            return {
                "topic": topic,
                "discipline": discipline_code,
                "constraints": constraints,
                "single_method_recommendations": evaluations,
                "combination_recommendations": combinations,
                "summary": self._generate_recommendation_summary(evaluations, combinations),
            }

    def _generate_recommendation_summary(self, evaluations: list[dict[str, Any]],
                                         combinations: list[dict[str, Any]]) -> str:
        """生成推荐摘要。"""
        if not evaluations and not combinations:
            return "未找到匹配的研究方法，建议调整研究主题或学科。"
        parts: list[str] = []
        if evaluations:
            best = evaluations[0]
            parts.append(
                f"首选方法：{best['method']['name']}"
                f"（综合评分{best['evaluation']['overall_score']}，"
                f"{best['evaluation']['recommendation']}）"
            )
        if combinations:
            combo_names = " + ".join(c["method"]["name"] for c in combinations)
            parts.append(f"推荐方法组合：{combo_names}")
        return "；".join(parts) + "。"

    # ===== 统计 =====

    def stats(self) -> dict[str, Any]:
        """返回方法库统计信息。"""
        with self._lock:
            category_counts: dict[str, int] = defaultdict(int)
            for method in self._methods.values():
                category_counts[method.category] += 1
            difficulty_counts: dict[int, int] = defaultdict(int)
            for method in self._methods.values():
                difficulty_counts[method.difficulty] += 1
            return {
                "total_methods": len(self._methods),
                "category_distribution": dict(category_counts),
                "difficulty_distribution": dict(difficulty_counts),
                "total_disciplines_covered": len(self._discipline_index),
                "total_keywords": len(self._keyword_index),
            }

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        with self._lock:
            return {
                "methods": [m.to_dict() for m in self._methods.values()],
            }


# ===== 模块级单例 =====


_global_instance: Optional[MethodLibrary] = None
_global_lock = threading.Lock()


def get_method_library() -> MethodLibrary:
    """获取全局研究方法库单例。"""
    global _global_instance
    if _global_instance is None:
        with _global_lock:
            if _global_instance is None:
                _global_instance = MethodLibrary()
    return _global_instance


def reset_method_library() -> None:
    """重置全局单例（主要用于测试）。"""
    global _global_instance
    with _global_lock:
        _global_instance = None
