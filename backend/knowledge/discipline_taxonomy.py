"""学科分类体系模块

提供完整的学科分类体系实现，包括：
    - 一级/二级/三级学科分类树管理
    - 教育部学科代码体系映射
    - 交叉学科识别
    - 学科相似度计算（基于关键词与结构）
    - 学科聚类（基于相似度矩阵）
    - 学科趋势分析
    - 学科关键词提取
    - 学科画像生成
    - 学科推荐

数据来源：教育部《学位授予和人才培养学科目录》
设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可扩展：支持动态添加学科节点
"""
from __future__ import annotations

import math
import re
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Iterable, Optional


# ===== 枚举与常量 =====


class DisciplineLevel:
    """学科层级常量。"""

    FIRST = 1   # 学科门类
    SECOND = 2  # 一级学科
    THIRD = 3   # 二级学科


# 教育部学科门类（一级）代码与名称
DISCIPLINE_GATE_CATEGORIES = {
    "01": "哲学",
    "02": "经济学",
    "03": "法学",
    "04": "教育学",
    "05": "文学",
    "06": "历史学",
    "07": "理学",
    "08": "工学",
    "09": "农学",
    "10": "医学",
    "11": "军事学",
    "12": "管理学",
    "13": "艺术学",
    "14": "交叉学科",
}

# 学科门类 -> 典型一级学科示例（用于初始化）
TYPICAL_FIRST_LEVEL_DISCIPLINES = {
    "01": [
        ("0101", "哲学"),
        ("0102", "逻辑学"),
        ("0103", "宗教学"),
        ("0104", "伦理学"),
    ],
    "02": [
        ("0201", "理论经济学"),
        ("0202", "应用经济学"),
        ("0203", "金融学"),
        ("0204", "统计学"),
    ],
    "03": [
        ("0301", "法学"),
        ("0302", "政治学"),
        ("0303", "社会学"),
        ("0304", "民族学"),
        ("0305", "马克思主义理论"),
        ("0306", "公安学"),
    ],
    "04": [
        ("0401", "教育学"),
        ("0402", "心理学"),
        ("0403", "体育学"),
    ],
    "05": [
        ("0501", "中国语言文学"),
        ("0502", "外国语言文学"),
        ("0503", "新闻传播学"),
    ],
    "06": [
        ("0601", "考古学"),
        ("0602", "中国史"),
        ("0603", "世界史"),
    ],
    "07": [
        ("0701", "数学"),
        ("0702", "物理学"),
        ("0703", "化学"),
        ("0704", "天文学"),
        ("0705", "地理学"),
        ("0706", "大气科学"),
        ("0707", "海洋科学"),
        ("0708", "地球物理学"),
        ("0709", "地质学"),
        ("0710", "生物学"),
        ("0711", "系统科学"),
        ("0712", "科学技术史"),
        ("0713", "生态学"),
        ("0714", "统计学"),
    ],
    "08": [
        ("0801", "力学"),
        ("0802", "机械工程"),
        ("0803", "光学工程"),
        ("0804", "仪器科学与技术"),
        ("0805", "材料科学与工程"),
        ("0806", "冶金工程"),
        ("0807", "动力工程及工程热物理"),
        ("0808", "电气工程"),
        ("0809", "电子科学与技术"),
        ("0810", "信息与通信工程"),
        ("0811", "控制科学与工程"),
        ("0812", "计算机科学与技术"),
        ("0813", "建筑学"),
        ("0814", "土木工程"),
        ("0815", "水利工程"),
        ("0816", "测绘科学与技术"),
        ("0817", "化学工程与技术"),
        ("0818", "地质资源与地质工程"),
        ("0819", "矿业工程"),
        ("0820", "石油与天然气工程"),
        ("0821", "纺织科学与工程"),
        ("0822", "轻工技术与工程"),
        ("0823", "交通运输工程"),
        ("0824", "船舶与海洋工程"),
        ("0825", "航空宇航科学与技术"),
        ("0826", "兵器科学与技术"),
        ("0827", "核科学与技术"),
        ("0828", "农业工程"),
        ("0829", "林业工程"),
        ("0830", "环境科学与工程"),
        ("0831", "生物医学工程"),
        ("0832", "食品科学与工程"),
        ("0833", "城乡规划学"),
        ("0834", "软件工程"),
        ("0835", "网络空间安全"),
    ],
    "09": [
        ("0901", "作物学"),
        ("0902", "园艺学"),
        ("0903", "农业资源与环境"),
        ("0904", "植物保护"),
        ("0905", "畜牧学"),
        ("0906", "兽医学"),
        ("0907", "林学"),
        ("0908", "水产"),
        ("0909", "草学"),
    ],
    "10": [
        ("1001", "基础医学"),
        ("1002", "临床医学"),
        ("1003", "口腔医学"),
        ("1004", "公共卫生与预防医学"),
        ("1005", "中医学"),
        ("1006", "中西医结合"),
        ("1007", "药学"),
        ("1008", "中药学"),
        ("1009", "特种医学"),
        ("1010", "医学技术"),
        ("1011", "护理学"),
    ],
    "11": [
        ("1101", "军事思想及军事历史"),
        ("1102", "战略学"),
        ("1103", "战役学"),
        ("1104", "战术学"),
        ("1105", "军队指挥学"),
        ("1106", "军制学"),
        ("1107", "军队政治工作学"),
        ("1108", "军事后勤学"),
        ("1109", "军事装备学"),
    ],
    "12": [
        ("1201", "管理科学与工程"),
        ("1202", "工商管理"),
        ("1203", "农林经济管理"),
        ("1204", "公共管理"),
        ("1205", "图书情报与档案管理"),
    ],
    "13": [
        ("1301", "艺术学理论"),
        ("1302", "音乐与舞蹈学"),
        ("1303", "戏剧与影视学"),
        ("1304", "美术学"),
        ("1305", "设计学"),
    ],
    "14": [
        ("1401", "集成电路科学与工程"),
        ("1402", "国家安全学"),
        ("1403", "人工智能"),
        ("1404", "遥感科学与技术"),
        ("1405", "智能科学与技术"),
    ],
}

# 交叉学科关键词映射（用于交叉学科识别）
CROSS_DISCIPLINE_KEYWORDS = {
    "生物信息学": ["生物学", "计算机科学"],
    "计算语言学": ["语言学", "计算机科学"],
    "金融工程": ["金融学", "数学"],
    "计量经济学": ["经济学", "数学", "统计学"],
    "环境工程": ["环境科学", "工程学"],
    "生物医学工程": ["生物学", "医学", "工程学"],
    "材料科学": ["化学", "物理学", "工程学"],
    "认知科学": ["心理学", "哲学", "神经科学", "计算机科学"],
    "社会心理学": ["社会学", "心理学"],
    "经济地理": ["经济学", "地理学"],
    "数字人文": ["人文学科", "计算机科学"],
    "数据科学": ["统计学", "计算机科学", "数学"],
    "人工智能": ["计算机科学", "数学", "统计学", "神经科学"],
    "网络空间安全": ["计算机科学", "密码学", "法学"],
    "量子信息": ["物理学", "计算机科学", "信息论"],
}


# ===== 数据结构 =====


@dataclass
class DisciplineNode:
    """学科分类节点。

    Attributes:
        code: 学科代码（如 "0812"）。
        name: 学科名称。
        level: 层级（1=门类, 2=一级学科, 3=二级学科）。
        parent_code: 父学科代码。
        keywords: 学科典型关键词。
        description: 学科描述。
        children: 子学科代码列表。
        aliases: 学科别名。
        related_codes: 相关学科代码。
        metadata: 扩展元数据。
    """

    code: str = ""
    name: str = ""
    level: int = DisciplineLevel.SECOND
    parent_code: str = ""
    keywords: list[str] = field(default_factory=list)
    description: str = ""
    children: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    related_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DisciplineNode":
        defaults = cls().__dict__
        merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        return cls(**merged)


@dataclass
class DisciplineProfile:
    """学科画像。

    Attributes:
        code: 学科代码。
        name: 学科名称。
        keyword_weights: 关键词及其权重。
        hot_topics: 热门研究方向。
        typical_methods: 典型研究方法。
        output_types: 典型成果形式。
        difficulty: 研究难度（1-5）。
        popularity: 热门程度（1-5）。
        trend: 发展趋势（rising/stable/declining）。
    """

    code: str = ""
    name: str = ""
    keyword_weights: dict[str, float] = field(default_factory=dict)
    hot_topics: list[str] = field(default_factory=list)
    typical_methods: list[str] = field(default_factory=list)
    output_types: list[str] = field(default_factory=list)
    difficulty: int = 3
    popularity: int = 3
    trend: str = "stable"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DisciplineTrend:
    """学科趋势数据。

    Attributes:
        code: 学科代码。
        name: 学科名称。
        year: 年份。
        paper_count: 论文数量。
        citation_count: 引用次数。
        growth_rate: 增长率。
        emerging_topics: 新兴主题。
    """

    code: str = ""
    name: str = ""
    year: int = 0
    paper_count: int = 0
    citation_count: int = 0
    growth_rate: float = 0.0
    emerging_topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ===== 工具函数 =====


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串。"""
    return datetime.now().isoformat()


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


def _jaccard_similarity(set1: set[str], set2: set[str]) -> float:
    """计算两个集合的 Jaccard 相似度。"""
    if not set1 and not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union) if union else 0.0


def _cosine_similarity(vec1: dict[str, float], vec2: dict[str, float]) -> float:
    """计算两个向量的余弦相似度。"""
    if not vec1 or not vec2:
        return 0.0
    common_keys = set(vec1.keys()) & set(vec2.keys())
    if not common_keys:
        return 0.0
    dot = sum(vec1[k] * vec2[k] for k in common_keys)
    norm1 = math.sqrt(sum(v * v for v in vec1.values()))
    norm2 = math.sqrt(sum(v * v for v in vec2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


# ===== 学科分类体系主类 =====


class DisciplineTaxonomy:
    """学科分类体系主类。

    管理完整的学科分类树，提供：
        - 学科节点 CRUD
        - 多层级分类查询
        - 交叉学科识别
        - 学科相似度计算
        - 学科聚类
        - 学科趋势分析
        - 学科画像生成
        - 学科推荐

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self) -> None:
        """初始化学科分类体系，自动加载教育部学科目录。"""
        self._lock = threading.RLock()
        # code -> DisciplineNode
        self._nodes: dict[str, DisciplineNode] = {}
        # name -> code（名称索引）
        self._name_index: dict[str, str] = {}
        # alias -> code（别名索引）
        self._alias_index: dict[str, str] = {}
        # keyword -> set of code（关键词索引）
        self._keyword_index: dict[str, set[str]] = defaultdict(set)
        # 学科画像缓存
        self._profiles: dict[str, DisciplineProfile] = {}
        # 趋势数据：code -> list of DisciplineTrend
        self._trends: dict[str, list[DisciplineTrend]] = defaultdict(list)
        # 初始化默认学科目录
        self._init_default_taxonomy()

    def _init_default_taxonomy(self) -> None:
        """初始化教育部学科目录。"""
        # 添加门类
        for gate_code, gate_name in DISCIPLINE_GATE_CATEGORIES.items():
            self._add_node_internal(
                DisciplineNode(
                    code=gate_code,
                    name=gate_name,
                    level=DisciplineLevel.FIRST,
                    parent_code="",
                    keywords=self._extract_gate_keywords(gate_name),
                    description=f"{gate_name}学科门类",
                )
            )
        # 添加一级学科
        for gate_code, disciplines in TYPICAL_FIRST_LEVEL_DISCIPLINES.items():
            for disc_code, disc_name in disciplines:
                self._add_node_internal(
                    DisciplineNode(
                        code=disc_code,
                        name=disc_name,
                        level=DisciplineLevel.SECOND,
                        parent_code=gate_code,
                        keywords=self._extract_discipline_keywords(disc_name),
                        description=f"{disc_name}（一级学科）",
                    )
                )
                # 在父节点添加 children
                if gate_code in self._nodes:
                    if disc_code not in self._nodes[gate_code].children:
                        self._nodes[gate_code].children.append(disc_code)

    def _extract_gate_keywords(self, gate_name: str) -> list[str]:
        """提取门类关键词。"""
        # 简单实现：去除"学"后缀
        base = gate_name.replace("学", "").strip()
        return [gate_name, base] if base else [gate_name]

    def _extract_discipline_keywords(self, disc_name: str) -> list[str]:
        """提取学科关键词。"""
        keywords = [disc_name]
        # 去除常见后缀
        for suffix in ["科学与技术", "科学与工程", "工程", "科学", "学", "技术"]:
            if disc_name.endswith(suffix) and len(disc_name) > len(suffix):
                base = disc_name[: -len(suffix)]
                if base and base not in keywords:
                    keywords.append(base)
        return keywords

    def _add_node_internal(self, node: DisciplineNode) -> None:
        """内部添加节点（不加锁）。"""
        self._nodes[node.code] = node
        self._name_index[node.name] = node.code
        for alias in node.aliases:
            self._alias_index[alias] = node.code
        for kw in node.keywords:
            self._keyword_index[kw].add(node.code)

    # ===== 节点 CRUD =====

    def add_discipline(self, code: str, name: str, level: int,
                       parent_code: str = "", keywords: Optional[list[str]] = None,
                       description: str = "", aliases: Optional[list[str]] = None,
                       related_codes: Optional[list[str]] = None) -> str:
        """添加学科节点。

        Args:
            code: 学科代码（唯一）。
            name: 学科名称。
            level: 层级（1/2/3）。
            parent_code: 父学科代码。
            keywords: 关键词列表。
            description: 描述。
            aliases: 别名列表。
            related_codes: 相关学科代码列表。

        Returns:
            学科代码。

        Raises:
            ValueError: 代码已存在或父学科不存在。
        """
        if not code or not name:
            raise ValueError("学科代码和名称不能为空")
        with self._lock:
            if code in self._nodes:
                raise ValueError(f"学科代码已存在: {code}")
            if parent_code and parent_code not in self._nodes:
                raise ValueError(f"父学科不存在: {parent_code}")
            node = DisciplineNode(
                code=code,
                name=name,
                level=level,
                parent_code=parent_code,
                keywords=keywords or [],
                description=description,
                aliases=aliases or [],
                related_codes=related_codes or [],
            )
            self._add_node_internal(node)
            # 更新父节点的 children
            if parent_code and parent_code in self._nodes:
                if code not in self._nodes[parent_code].children:
                    self._nodes[parent_code].children.append(code)
            return code

    def get_discipline(self, code: str) -> Optional[DisciplineNode]:
        """按代码获取学科。"""
        with self._lock:
            return self._nodes.get(code)

    def get_by_name(self, name: str) -> Optional[DisciplineNode]:
        """按名称获取学科。"""
        with self._lock:
            code = self._name_index.get(name)
            if code:
                return self._nodes.get(code)
            # 尝试别名
            code = self._alias_index.get(name)
            if code:
                return self._nodes.get(code)
            return None

    def update_discipline(self, code: str, name: Optional[str] = None,
                          keywords: Optional[list[str]] = None,
                          description: Optional[str] = None,
                          aliases: Optional[list[str]] = None,
                          related_codes: Optional[list[str]] = None) -> bool:
        """更新学科节点。"""
        with self._lock:
            node = self._nodes.get(code)
            if node is None:
                return False
            # 移除旧索引
            self._name_index.pop(node.name, None)
            for alias in node.aliases:
                self._alias_index.pop(alias, None)
            for kw in node.keywords:
                self._keyword_index[kw].discard(code)
            # 应用更新
            if name is not None:
                node.name = name
            if keywords is not None:
                node.keywords = keywords
            if description is not None:
                node.description = description
            if aliases is not None:
                node.aliases = aliases
            if related_codes is not None:
                node.related_codes = related_codes
            # 重建索引
            self._name_index[node.name] = code
            for alias in node.aliases:
                self._alias_index[alias] = code
            for kw in node.keywords:
                self._keyword_index[kw].add(code)
            return True

    def delete_discipline(self, code: str, recursive: bool = False) -> bool:
        """删除学科节点。"""
        with self._lock:
            node = self._nodes.get(code)
            if node is None:
                return False
            if node.children and not recursive:
                raise ValueError("学科下有子学科，请先删除子学科或使用递归模式")
            # 递归删除子学科
            for child_code in list(node.children):
                self.delete_discipline(child_code, recursive=True)
            # 从父节点的 children 中移除
            if node.parent_code and node.parent_code in self._nodes:
                parent = self._nodes[node.parent_code]
                if code in parent.children:
                    parent.children.remove(code)
            # 清理索引
            self._name_index.pop(node.name, None)
            for alias in node.aliases:
                self._alias_index.pop(alias, None)
            for kw in node.keywords:
                self._keyword_index[kw].discard(code)
            del self._nodes[code]
            return True

    # ===== 分类查询 =====

    def list_by_level(self, level: int) -> list[DisciplineNode]:
        """按层级列出学科。"""
        with self._lock:
            return [n for n in self._nodes.values() if n.level == level]

    def list_children(self, parent_code: str) -> list[DisciplineNode]:
        """列出子学科。"""
        with self._lock:
            parent = self._nodes.get(parent_code)
            if parent is None:
                return []
            return [self._nodes[c] for c in parent.children if c in self._nodes]

    def get_ancestors(self, code: str) -> list[DisciplineNode]:
        """获取所有祖先学科（从父到根）。"""
        with self._lock:
            result: list[DisciplineNode] = []
            current = self._nodes.get(code)
            while current and current.parent_code:
                parent = self._nodes.get(current.parent_code)
                if parent is None:
                    break
                result.append(parent)
                current = parent
            return result

    def get_descendants(self, code: str) -> list[DisciplineNode]:
        """获取所有后代学科。"""
        with self._lock:
            result: list[DisciplineNode] = []
            stack = [code]
            while stack:
                current_code = stack.pop()
                node = self._nodes.get(current_code)
                if node is None:
                    continue
                for child_code in node.children:
                    child = self._nodes.get(child_code)
                    if child:
                        result.append(child)
                        stack.append(child_code)
            return result

    def get_path(self, code: str) -> list[DisciplineNode]:
        """获取从根到当前节点的路径。"""
        with self._lock:
            ancestors = self.get_ancestors(code)
            ancestors.reverse()
            current = self._nodes.get(code)
            if current:
                ancestors.append(current)
            return ancestors

    def get_tree(self, root_code: Optional[str] = None,
                 max_depth: int = 3) -> dict[str, Any]:
        """获取学科树结构。

        Args:
            root_code: 根节点代码。None 表示所有门类。
            max_depth: 最大深度。

        Returns:
            嵌套的树结构。
        """
        with self._lock:
            if root_code is None:
                # 返回所有门类作为根
                roots = [n for n in self._nodes.values() if n.level == DisciplineLevel.FIRST]
                return {
                    "roots": [self._build_tree_node(r.code, max_depth) for r in roots]
                }
            return self._build_tree_node(root_code, max_depth)

    def _build_tree_node(self, code: str, max_depth: int) -> dict[str, Any]:
        """递归构建树节点。"""
        node = self._nodes.get(code)
        if node is None:
            return {}
        children: list[dict[str, Any]] = []
        if max_depth > 0:
            for child_code in node.children:
                children.append(self._build_tree_node(child_code, max_depth - 1))
        return {
            "code": node.code,
            "name": node.name,
            "level": node.level,
            "description": node.description,
            "keywords": node.keywords,
            "children": children,
        }

    # ===== 交叉学科识别 =====

    def identify_cross_discipline(self, text: str) -> list[dict[str, Any]]:
        """识别文本涉及的交叉学科。

        Args:
            text: 待分析文本（如论题标题、摘要）。

        Returns:
            交叉学科识别结果列表，每项包含名称、涉及学科、置信度。
        """
        with self._lock:
            results: list[dict[str, Any]] = []
            text_lower = text.lower()
            # 基于预定义交叉学科关键词
            for cross_name, involved in CROSS_DISCIPLINE_KEYWORDS.items():
                if cross_name in text:
                    # 查找涉及的学科代码
                    involved_codes: list[str] = []
                    for disc_name in involved:
                        node = self.get_by_name(disc_name)
                        if node:
                            involved_codes.append(node.code)
                    results.append({
                        "name": cross_name,
                        "involved_disciplines": involved,
                        "involved_codes": involved_codes,
                        "confidence": 0.9,
                        "source": "keyword_match",
                    })
            # 基于关键词匹配多个学科
            matched_disciplines = self._match_disciplines_by_keywords(text)
            if len(matched_disciplines) >= 2:
                # 检查这些学科是否属于不同门类
                gate_codes = set()
                for code, _ in matched_disciplines[:5]:
                    ancestors = self.get_ancestors(code)
                    if ancestors:
                        gate_codes.add(ancestors[-1].code)
                if len(gate_codes) >= 2:
                    cross_name = "/".join(
                        self._nodes[c].name for c, _ in matched_disciplines[:3]
                    )
                    results.append({
                        "name": f"跨学科研究({cross_name})",
                        "involved_disciplines": [
                            self._nodes[c].name for c, _ in matched_disciplines[:5]
                        ],
                        "involved_codes": [c for c, _ in matched_disciplines[:5]],
                        "confidence": 0.7,
                        "source": "keyword_inference",
                    })
            return results

    def _match_disciplines_by_keywords(self, text: str) -> list[tuple[str, float]]:
        """通过关键词匹配学科。

        Returns:
            (code, score) 元组列表，按分数降序。
        """
        text_tokens = set(_tokenize(text))
        if not text_tokens:
            return []
        scores: list[tuple[str, float]] = []
        for code, node in self._nodes.items():
            if not node.keywords:
                continue
            node_kw_set = set(node.keywords)
            # 直接名称匹配加分
            score = 0.0
            if node.name in text:
                score += 2.0
            # 关键词重叠
            overlap = text_tokens & node_kw_set
            score += len(overlap)
            # 别名匹配
            for alias in node.aliases:
                if alias in text:
                    score += 1.5
            if score > 0:
                scores.append((code, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def is_cross_discipline(self, code1: str, code2: str) -> bool:
        """判断两个学科是否构成交叉学科（不同门类）。"""
        with self._lock:
            ancestors1 = self.get_ancestors(code1)
            ancestors2 = self.get_ancestors(code2)
            gate1 = ancestors1[-1].code if ancestors1 else code1
            gate2 = ancestors2[-1].code if ancestors2 else code2
            return gate1 != gate2

    # ===== 学科相似度 =====

    def compute_similarity(self, code1: str, code2: str) -> float:
        """计算两个学科的相似度。

        综合考虑：
            - 关键词重叠（Jaccard）
            - 分类树距离
            - 是否同门类

        Args:
            code1: 学科1代码。
            code2: 学科2代码。

        Returns:
            相似度（0-1）。
        """
        with self._lock:
            node1 = self._nodes.get(code1)
            node2 = self._nodes.get(code2)
            if node1 is None or node2 is None:
                return 0.0
            if code1 == code2:
                return 1.0
            # 关键词相似度
            kw_sim = _jaccard_similarity(set(node1.keywords), set(node2.keywords))
            # 分类树距离
            tree_sim = self._compute_tree_similarity(code1, code2)
            # 名称相似度
            name_sim = _jaccard_similarity(
                set(_tokenize(node1.name)), set(_tokenize(node2.name))
            )
            # 加权融合
            similarity = 0.4 * kw_sim + 0.4 * tree_sim + 0.2 * name_sim
            return round(similarity, 4)

    def _compute_tree_similarity(self, code1: str, code2: str) -> float:
        """基于分类树距离计算相似度。"""
        path1 = [n.code for n in self.get_path(code1)]
        path2 = [n.code for n in self.get_path(code2)]
        if not path1 or not path2:
            return 0.0
        # 找最近公共祖先
        lca_index = -1
        for i, (c1, c2) in enumerate(zip(path1, path2)):
            if c1 != c2:
                break
            lca_index = i
        if lca_index < 0:
            return 0.0
        # 距离 = 两个节点到 LCA 的距离之和
        dist1 = len(path1) - 1 - lca_index
        dist2 = len(path2) - 1 - lca_index
        total_dist = dist1 + dist2
        # 相似度 = 1 / (1 + distance)
        return 1.0 / (1.0 + total_dist)

    def find_similar_disciplines(self, code: str, top_k: int = 10) -> list[tuple[str, float]]:
        """查找相似学科。

        Args:
            code: 学科代码。
            top_k: 返回数量。

        Returns:
            (code, similarity) 元组列表。
        """
        with self._lock:
            if code not in self._nodes:
                return []
            results: list[tuple[str, float]] = []
            for other_code in self._nodes:
                if other_code == code:
                    continue
                sim = self.compute_similarity(code, other_code)
                if sim > 0:
                    results.append((other_code, sim))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]

    def find_similar_by_text(self, text: str, top_k: int = 10) -> list[tuple[str, float]]:
        """根据文本查找相似学科。"""
        with self._lock:
            matched = self._match_disciplines_by_keywords(text)
            if not matched:
                return []
            # 归一化分数
            max_score = matched[0][1] if matched else 1.0
            if max_score == 0:
                return []
            normalized = [(c, s / max_score) for c, s in matched[:top_k]]
            return normalized

    # ===== 学科聚类 =====

    def cluster_disciplines(self, level: int = DisciplineLevel.SECOND,
                            threshold: float = 0.3) -> list[list[str]]:
        """对同学科层级的学科进行聚类。

        基于相似度矩阵的简单层次聚类。

        Args:
            level: 学科层级。
            threshold: 聚类阈值（相似度低于此值不合并）。

        Returns:
            聚类结果，每个簇为学科代码列表。
        """
        with self._lock:
            disciplines = [n.code for n in self.list_by_level(level)]
            if len(disciplines) < 2:
                return [[c] for c in disciplines]
            # 初始化：每个学科自成一簇
            clusters: list[set[str]] = [{c} for c in disciplines]
            # 计算所有两两相似度
            sim_cache: dict[tuple[str, str], float] = {}
            for i, c1 in enumerate(disciplines):
                for c2 in disciplines[i + 1:]:
                    sim = self.compute_similarity(c1, c2)
                    sim_cache[(c1, c2)] = sim
                    sim_cache[(c2, c1)] = sim
            # 层次聚类（贪心合并）
            changed = True
            while changed and len(clusters) > 1:
                changed = False
                best_sim = threshold
                best_pair: Optional[tuple[int, int]] = None
                for i in range(len(clusters)):
                    for j in range(i + 1, len(clusters)):
                        # 计算簇间平均相似度
                        total = 0.0
                        count = 0
                        for c1 in clusters[i]:
                            for c2 in clusters[j]:
                                total += sim_cache.get((c1, c2), 0.0)
                                count += 1
                        avg_sim = total / count if count > 0 else 0.0
                        if avg_sim > best_sim:
                            best_sim = avg_sim
                            best_pair = (i, j)
                if best_pair:
                    i, j = best_pair
                    clusters[i] = clusters[i] | clusters[j]
                    clusters.pop(j)
                    changed = True
            return [list(c) for c in clusters]

    # ===== 学科趋势分析 =====

    def add_trend_data(self, code: str, year: int, paper_count: int,
                       citation_count: int = 0,
                       emerging_topics: Optional[list[str]] = None) -> None:
        """添加学科趋势数据。"""
        with self._lock:
            node = self._nodes.get(code)
            name = node.name if node else code
            trend = DisciplineTrend(
                code=code,
                name=name,
                year=year,
                paper_count=paper_count,
                citation_count=citation_count,
                emerging_topics=emerging_topics or [],
            )
            # 计算增长率
            trends = self._trends[code]
            if trends:
                last = trends[-1]
                if last.paper_count > 0:
                    trend.growth_rate = (
                        (paper_count - last.paper_count) / last.paper_count
                    )
            trends.append(trend)

    def get_trend(self, code: str) -> list[DisciplineTrend]:
        """获取学科趋势数据。"""
        with self._lock:
            return list(self._trends.get(code, []))

    def analyze_trend(self, code: str) -> dict[str, Any]:
        """分析学科趋势。

        Args:
            code: 学科代码。

        Returns:
            趋势分析结果，包含总体趋势、增长率、热门主题等。
        """
        with self._lock:
            trends = self._trends.get(code, [])
            if not trends:
                return {
                    "code": code,
                    "name": self._nodes.get(code, DisciplineNode()).name,
                    "trend": "unknown",
                    "avg_growth_rate": 0.0,
                    "total_papers": 0,
                    "emerging_topics": [],
                }
            total_papers = sum(t.paper_count for t in trends)
            avg_growth = sum(t.growth_rate for t in trends) / len(trends)
            # 判断趋势
            if len(trends) >= 2:
                recent_growth = trends[-1].growth_rate
                if recent_growth > 0.1:
                    trend_direction = "rising"
                elif recent_growth < -0.1:
                    trend_direction = "declining"
                else:
                    trend_direction = "stable"
            else:
                trend_direction = "stable"
            # 收集新兴主题
            all_topics: list[str] = []
            for t in trends:
                all_topics.extend(t.emerging_topics)
            # 统计主题频率
            topic_freq: dict[str, int] = defaultdict(int)
            for topic in all_topics:
                topic_freq[topic] += 1
            top_topics = sorted(topic_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            return {
                "code": code,
                "name": trends[0].name,
                "trend": trend_direction,
                "avg_growth_rate": round(avg_growth, 4),
                "recent_growth_rate": round(trends[-1].growth_rate, 4),
                "total_papers": total_papers,
                "total_citations": sum(t.citation_count for t in trends),
                "years_covered": len(trends),
                "emerging_topics": [t for t, _ in top_topics],
                "yearly_data": [t.to_dict() for t in trends],
            }

    def get_hot_disciplines(self, top_k: int = 10) -> list[dict[str, Any]]:
        """获取热门学科（基于趋势数据）。"""
        with self._lock:
            results: list[dict[str, Any]] = []
            for code, trends in self._trends.items():
                if not trends:
                    continue
                analysis = self.analyze_trend(code)
                results.append({
                    "code": code,
                    "name": analysis["name"],
                    "trend": analysis["trend"],
                    "avg_growth_rate": analysis["avg_growth_rate"],
                    "total_papers": analysis["total_papers"],
                })
            results.sort(key=lambda x: x["avg_growth_rate"], reverse=True)
            return results[:top_k]

    # ===== 学科画像 =====

    def build_profile(self, code: str) -> Optional[DisciplineProfile]:
        """构建学科画像。

        Args:
            code: 学科代码。

        Returns:
            学科画像，或 None（学科不存在）。
        """
        with self._lock:
            node = self._nodes.get(code)
            if node is None:
                return None
            # 检查缓存
            if code in self._profiles:
                return self._profiles[code]
            # 构建关键词权重
            keyword_weights: dict[str, float] = {}
            for kw in node.keywords:
                keyword_weights[kw] = 1.0
            # 从子学科收集关键词
            for child in self.get_descendants(code):
                for kw in child.keywords:
                    keyword_weights[kw] = keyword_weights.get(kw, 0.0) + 0.5
            # 推断典型方法
            typical_methods = self._infer_typical_methods(node)
            # 推断成果形式
            output_types = self._infer_output_types(node)
            # 推断难度与热门度
            difficulty = self._infer_difficulty(node)
            popularity = self._infer_popularity(node)
            # 趋势
            trend_data = self._trends.get(code, [])
            if trend_data:
                recent_growth = trend_data[-1].growth_rate if trend_data else 0.0
                if recent_growth > 0.1:
                    trend = "rising"
                elif recent_growth < -0.1:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "stable"
            # 热门主题
            hot_topics: list[str] = []
            for t in trend_data:
                hot_topics.extend(t.emerging_topics)
            profile = DisciplineProfile(
                code=code,
                name=node.name,
                keyword_weights=keyword_weights,
                hot_topics=list(set(hot_topics))[:10],
                typical_methods=typical_methods,
                output_types=output_types,
                difficulty=difficulty,
                popularity=popularity,
                trend=trend,
            )
            self._profiles[code] = profile
            return profile

    def _infer_typical_methods(self, node: DisciplineNode) -> list[str]:
        """推断学科典型研究方法。"""
        # 基于学科门类的默认方法
        gate_code = node.code[:2] if len(node.code) >= 2 else node.code
        method_map = {
            "01": ["文献研究法", "思辨研究", "概念分析", "历史研究法"],
            "02": ["计量分析", "实证研究", "案例分析", "数理建模"],
            "03": ["规范分析", "实证研究", "案例分析", "比较研究"],
            "04": ["实验研究", "问卷调查", "观察法", "行动研究"],
            "05": ["文本分析", "比较文学", "语料库方法", "田野调查"],
            "06": ["文献考证", "考古发掘", "口述史", "比较研究"],
            "07": ["实验研究", "理论建模", "数值模拟", "观测研究"],
            "08": ["实验研究", "仿真模拟", "工程设计", "原型验证"],
            "09": ["田间试验", "实验室研究", "观测研究", "统计分析"],
            "10": ["临床试验", "基础实验", "流行病学调查", "病例研究"],
            "11": ["战略分析", "案例研究", "模拟推演", "实证研究"],
            "12": ["实证研究", "案例分析", "数理建模", "问卷调查"],
            "13": ["创作实践", "理论研究", "案例分析", "比较研究"],
            "14": ["交叉研究", "实验研究", "理论建模", "仿真模拟"],
        }
        return method_map.get(gate_code, ["文献研究法", "实证研究"])

    def _infer_output_types(self, node: DisciplineNode) -> list[str]:
        """推断学科典型成果形式。"""
        gate_code = node.code[:2] if len(node.code) >= 2 else node.code
        output_map = {
            "01": ["论文", "专著", "评论"],
            "02": ["论文", "研究报告", "政策建议"],
            "03": ["论文", "案例分析", "法律评论"],
            "04": ["论文", "实验报告", "教学设计"],
            "05": ["论文", "译著", "文学评论"],
            "06": ["论文", "专著", "史料整理"],
            "07": ["论文", "实验报告", "数据集"],
            "08": ["论文", "专利", "工程实现", "原型系统"],
            "09": ["论文", "实验报告", "品种培育"],
            "10": ["论文", "临床报告", "专利", "诊疗指南"],
            "11": ["论文", "战略报告", "推演方案"],
            "12": ["论文", "案例分析", "管理建议"],
            "13": ["作品", "论文", "创作报告"],
            "14": ["论文", "专利", "系统原型", "数据集"],
        }
        return output_map.get(gate_code, ["论文", "研究报告"])

    def _infer_difficulty(self, node: DisciplineNode) -> int:
        """推断学科研究难度（1-5）。"""
        gate_code = node.code[:2] if len(node.code) >= 2 else node.code
        difficulty_map = {
            "01": 4, "02": 3, "03": 3, "04": 2, "05": 3,
            "06": 4, "07": 5, "08": 4, "09": 3, "10": 5,
            "11": 4, "12": 3, "13": 3, "14": 5,
        }
        return difficulty_map.get(gate_code, 3)

    def _infer_popularity(self, node: DisciplineNode) -> int:
        """推断学科热门程度（1-5）。"""
        # 基于趋势数据
        trends = self._trends.get(node.code, [])
        if not trends:
            # 默认基于学科代码
            popular_codes = {"0812", "0835", "1403", "1002", "0203", "1202"}
            if node.code in popular_codes:
                return 5
            return 3
        recent_growth = trends[-1].growth_rate if trends else 0.0
        if recent_growth > 0.3:
            return 5
        elif recent_growth > 0.1:
            return 4
        elif recent_growth > 0:
            return 3
        elif recent_growth > -0.1:
            return 2
        else:
            return 1

    # ===== 学科推荐 =====

    def recommend_disciplines(self, text: str, top_k: int = 5,
                              level: int = DisciplineLevel.SECOND) -> list[dict[str, Any]]:
        """根据文本推荐学科。

        Args:
            text: 输入文本（如研究兴趣、论题）。
            top_k: 返回数量。
            level: 推荐学科层级。

        Returns:
            推荐结果列表，每项包含学科信息与匹配分数。
        """
        with self._lock:
            # 关键词匹配
            matched = self._match_disciplines_by_keywords(text)
            if not matched:
                return []
            # 过滤层级
            filtered = [
                (c, s) for c, s in matched
                if self._nodes.get(c) and self._nodes[c].level == level
            ]
            if not filtered:
                # 退而求其次，返回任意层级
                filtered = matched
            # 归一化
            max_score = filtered[0][1] if filtered else 1.0
            if max_score == 0:
                return []
            results: list[dict[str, Any]] = []
            for code, score in filtered[:top_k]:
                node = self._nodes.get(code)
                if node is None:
                    continue
                normalized_score = score / max_score
                results.append({
                    "code": node.code,
                    "name": node.name,
                    "level": node.level,
                    "description": node.description,
                    "keywords": node.keywords,
                    "match_score": round(normalized_score, 4),
                    "is_cross_discipline": len(self.identify_cross_discipline(text)) > 0,
                })
            return results

    def recommend_cross_disciplines(self, code: str, top_k: int = 5) -> list[dict[str, Any]]:
        """推荐交叉学科组合。

        Args:
            code: 学科代码。
            top_k: 返回数量。

        Returns:
            推荐的交叉学科组合列表。
        """
        with self._lock:
            node = self._nodes.get(code)
            if node is None:
                return []
            # 查找不同门类的相似学科
            similar = self.find_similar_disciplines(code, top_k * 3)
            results: list[dict[str, Any]] = []
            for other_code, sim in similar:
                if self.is_cross_discipline(code, other_code):
                    other = self._nodes.get(other_code)
                    if other is None:
                        continue
                    # 查找预定义交叉学科
                    cross_names: list[str] = []
                    for cross_name, involved in CROSS_DISCIPLINE_KEYWORDS.items():
                        if node.name in involved and other.name in involved:
                            cross_names.append(cross_name)
                    results.append({
                        "primary_discipline": {
                            "code": node.code,
                            "name": node.name,
                        },
                        "secondary_discipline": {
                            "code": other.code,
                            "name": other.name,
                        },
                        "similarity": sim,
                        "cross_discipline_names": cross_names,
                        "potential_topics": self._generate_cross_topics(node, other),
                    })
                    if len(results) >= top_k:
                        break
            return results

    def _generate_cross_topics(self, node1: DisciplineNode,
                               node2: DisciplineNode) -> list[str]:
        """生成交叉学科研究主题建议。"""
        topics: list[str] = []
        # 基于关键词组合
        for kw1 in node1.keywords[:3]:
            for kw2 in node2.keywords[:3]:
                if kw1 != kw2:
                    topics.append(f"基于{kw2}的{kw1}研究")
                    topics.append(f"{kw1}与{kw2}的交叉应用")
        return topics[:5]

    # ===== 学科关键词提取 =====

    def extract_discipline_keywords(self, code: str, text: str,
                                    top_k: int = 10) -> list[tuple[str, float]]:
        """从文本中提取与指定学科相关的关键词。

        Args:
            code: 学科代码。
            text: 待分析文本。
            top_k: 返回数量。

        Returns:
            (keyword, weight) 元组列表。
        """
        with self._lock:
            node = self._nodes.get(code)
            if node is None:
                return []
            text_tokens = _tokenize(text)
            if not text_tokens:
                return []
            # 统计词频
            freq: dict[str, int] = defaultdict(int)
            for t in text_tokens:
                freq[t] += 1
            # 计算与学科关键词的相关性
            node_kw_set = set(node.keywords)
            results: list[tuple[str, float]] = []
            for token, count in freq.items():
                weight = float(count)
                if token in node_kw_set:
                    weight *= 2.0  # 学科关键词加权
                # 检查是否是别名
                for alias in node.aliases:
                    if token in alias:
                        weight *= 1.5
                results.append((token, weight))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]

    # ===== 统计 =====

    def stats(self) -> dict[str, Any]:
        """返回分类体系统计信息。"""
        with self._lock:
            level_counts: dict[int, int] = defaultdict(int)
            for node in self._nodes.values():
                level_counts[node.level] += 1
            return {
                "total_disciplines": len(self._nodes),
                "level_distribution": dict(level_counts),
                "gate_categories": len(DISCIPLINE_GATE_CATEGORIES),
                "cross_discipline_types": len(CROSS_DISCIPLINE_KEYWORDS),
                "profiles_built": len(self._profiles),
                "trend_records": sum(len(v) for v in self._trends.values()),
            }

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        with self._lock:
            return {
                "nodes": [n.to_dict() for n in self._nodes.values()],
                "profiles": [p.to_dict() for p in self._profiles.values()],
                "trends": {
                    code: [t.to_dict() for t in trends]
                    for code, trends in self._trends.items()
                },
            }


# ===== 模块级单例 =====


_global_instance: Optional[DisciplineTaxonomy] = None
_global_lock = threading.Lock()


def get_discipline_taxonomy() -> DisciplineTaxonomy:
    """获取全局学科分类体系单例。"""
    global _global_instance
    if _global_instance is None:
        with _global_lock:
            if _global_instance is None:
                _global_instance = DisciplineTaxonomy()
    return _global_instance


def reset_discipline_taxonomy() -> None:
    """重置全局单例（主要用于测试）。"""
    global _global_instance
    with _global_lock:
        _global_instance = None
