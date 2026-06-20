"""学脉图谱样本数据

提供 50+ 节点的学脉图谱样本，包含节点、边与元数据，
供集成测试、E2E 测试与压测使用。

节点类型覆盖：
- paper: 论文节点
- topic: 论题节点
- method: 方法节点
- author: 作者节点
- concept: 概念节点
- dataset: 数据集节点

关系类型覆盖：
- cites: 引用关系
- derives: 衍生关系
- advises: 指导关系
- related: 关联关系
- derived_from: 衍生自
- cited_by: 被引用
- advised_by: 被指导
"""
from typing import Optional


# ===== 50+ 学脉节点样本 =====
SAMPLE_LINEAGE_NODES: list[dict] = [
    # 论文节点（15个）
    {"id": "n_paper_001", "node_type": "paper", "title": "Graph Neural Networks for Vulnerability Detection",
     "abstract": "GNN-based vulnerability detection survey.", "metadata": {"year": 2024, "venue": "ACM CSUR", "citations": 156}},
    {"id": "n_paper_002", "node_type": "paper", "title": "Efficient Container Scheduling for Edge Computing",
     "abstract": "Multi-agent RL for edge container scheduling.", "metadata": {"year": 2024, "venue": "IEEE TEC", "citations": 89}},
    {"id": "n_paper_003", "node_type": "paper", "title": "RAG for Domain-Specific QA",
     "abstract": "Retrieval-augmented generation framework.", "metadata": {"year": 2024, "venue": "ACL", "citations": 312}},
    {"id": "n_paper_004", "node_type": "paper", "title": "MetaDiff: Few-Shot Image Generation",
     "abstract": "Meta-learning + diffusion models.", "metadata": {"year": 2025, "venue": "CVPR", "citations": 78}},
    {"id": "n_paper_005", "node_type": "paper", "title": "Federated Learning for Medical Imaging",
     "abstract": "Privacy-preserving multi-modal diagnosis.", "metadata": {"year": 2025, "venue": "Nature MI", "citations": 145}},
    {"id": "n_paper_006", "node_type": "paper", "title": "End-to-End Decision Transformer for Autonomous Driving",
     "abstract": "E2E transformer for driving decisions.", "metadata": {"year": 2025, "venue": "NeurIPS", "citations": 67}},
    {"id": "n_paper_007", "node_type": "paper", "title": "Contrastive Learning for Cross-Lingual Representation",
     "abstract": "Cross-lingual text representation.", "metadata": {"year": 2024, "venue": "EMNLP", "citations": 203}},
    {"id": "n_paper_008", "node_type": "paper", "title": "Blockchain Supply Chain Traceability",
     "abstract": "ZKP-based supply chain system.", "metadata": {"year": 2024, "venue": "IEEE Blockchain", "citations": 56}},
    {"id": "n_paper_009", "node_type": "paper", "title": "Differential Privacy for Location Services",
     "abstract": "Utility-privacy tradeoff for LBS.", "metadata": {"year": 2025, "venue": "IEEE TMC", "citations": 91}},
    {"id": "n_paper_010", "node_type": "paper", "title": "Multi-Agent RL for Traffic Signal Control",
     "abstract": "MARL with graph attention.", "metadata": {"year": 2026, "venue": "TRC", "citations": 34}},
    {"id": "n_paper_011", "node_type": "paper", "title": "Modernity and Anxiety in Lu Xun's Fiction",
     "abstract": "Narrative analysis of Lu Xun.", "metadata": {"year": 2024, "venue": "MCLC", "citations": 28}},
    {"id": "n_paper_012", "node_type": "paper", "title": "Female Writing in Song Dynasty Ci",
     "abstract": "Gender consciousness in Song ci.", "metadata": {"year": 2024, "venue": "JCL", "citations": 45}},
    {"id": "n_paper_013", "node_type": "paper", "title": "Web Novel IP Adaptations",
     "abstract": "Narrative transformation in adaptations.", "metadata": {"year": 2025, "venue": "CCL", "citations": 62}},
    {"id": "n_paper_014", "node_type": "paper", "title": "Gig Workers Labor Rights",
     "abstract": "Platform economy labor study.", "metadata": {"year": 2024, "venue": "CSR", "citations": 134}},
    {"id": "n_paper_015", "node_type": "paper", "title": "Digital Economy Spillover Effects",
     "abstract": "Spatial spillover of digital economy.", "metadata": {"year": 2024, "venue": "CER", "citations": 187}},

    # 论题节点（10个）
    {"id": "n_topic_001", "node_type": "topic", "title": "基于图神经网络的代码漏洞检测方法研究",
     "abstract": "GNN应用于代码漏洞检测。", "metadata": {"discipline": "computer_science", "degree": "master"}},
    {"id": "n_topic_002", "node_type": "topic", "title": "面向边缘计算的轻量级容器调度算法研究",
     "abstract": "边缘容器调度优化。", "metadata": {"discipline": "computer_science", "degree": "master"}},
    {"id": "n_topic_003", "node_type": "topic", "title": "基于大语言模型的领域知识问答系统研究",
     "abstract": "LLM+RAG问答系统。", "metadata": {"discipline": "artificial_intelligence", "degree": "master"}},
    {"id": "n_topic_004", "node_type": "topic", "title": "基于扩散模型的少样本图像生成与增强研究",
     "abstract": "扩散模型少样本生成。", "metadata": {"discipline": "artificial_intelligence", "degree": "doctor"}},
    {"id": "n_topic_005", "node_type": "topic", "title": "面向多模态医学影像的联邦学习诊断方法",
     "abstract": "联邦学习医学诊断。", "metadata": {"discipline": "artificial_intelligence", "degree": "doctor"}},
    {"id": "n_topic_006", "node_type": "topic", "title": "鲁迅小说中的现代性焦虑叙事研究",
     "abstract": "鲁迅小说现代性叙事。", "metadata": {"discipline": "literature", "degree": "doctor"}},
    {"id": "n_topic_007", "node_type": "topic", "title": "平台经济背景下灵活就业者的劳动权益保障研究",
     "abstract": "灵活就业权益保障。", "metadata": {"discipline": "sociology", "degree": "master"}},
    {"id": "n_topic_008", "node_type": "topic", "title": "数字经济对区域创新效率的溢出效应研究",
     "abstract": "数字经济空间溢出。", "metadata": {"discipline": "economics", "degree": "master"}},
    {"id": "n_topic_009", "node_type": "topic", "title": "CRISPR-Cas9系统在作物性状改良中的应用研究",
     "abstract": "CRISPR作物改良。", "metadata": {"discipline": "biology", "degree": "doctor"}},
    {"id": "n_topic_010", "node_type": "topic", "title": "肠道菌群与代谢综合征关联性的机制研究",
     "abstract": "肠道菌群代谢研究。", "metadata": {"discipline": "biology", "degree": "doctor"}},

    # 方法节点（10个）
    {"id": "n_method_001", "node_type": "method", "title": "图神经网络（GNN）",
     "abstract": "图结构数据的神经网络方法。", "metadata": {"category": "deep_learning"}},
    {"id": "n_method_002", "node_type": "method", "title": "强化学习（RL）",
     "abstract": "通过环境交互学习最优策略。", "metadata": {"category": "deep_learning"}},
    {"id": "n_method_003", "node_type": "method", "title": "检索增强生成（RAG）",
     "abstract": "结合检索与生成的混合范式。", "metadata": {"category": "llm"}},
    {"id": "n_method_004", "node_type": "method", "title": "扩散模型（Diffusion）",
     "abstract": "基于去噪过程的生成模型。", "metadata": {"category": "generative"}},
    {"id": "n_method_005", "node_type": "method", "title": "联邦学习（Federated Learning）",
     "abstract": "隐私保护的分布式训练。", "metadata": {"category": "distributed"}},
    {"id": "n_method_006", "node_type": "method", "title": "Transformer 架构",
     "abstract": "基于自注意力的序列建模。", "metadata": {"category": "deep_learning"}},
    {"id": "n_method_007", "node_type": "method", "title": "对比学习（Contrastive Learning）",
     "abstract": "通过对比正负样本学习表征。", "metadata": {"category": "self_supervised"}},
    {"id": "n_method_008", "node_type": "method", "title": "区块链（Blockchain）",
     "abstract": "去中心化分布式账本技术。", "metadata": {"category": "distributed"}},
    {"id": "n_method_009", "node_type": "method", "title": "差分隐私（Differential Privacy）",
     "abstract": "形式化的隐私保护框架。", "metadata": {"category": "privacy"}},
    {"id": "n_method_010", "node_type": "method", "title": "CRISPR-Cas9 基因编辑",
     "abstract": "精准基因编辑技术。", "metadata": {"category": "biotech"}},

    # 作者节点（8个）
    {"id": "n_author_001", "node_type": "author", "title": "张伟 教授",
     "abstract": "清华大学计算机系，研究方向：软件安全与GNN。", "metadata": {"affiliation": "清华大学", "field": "software_security"}},
    {"id": "n_author_002", "node_type": "author", "title": "王磊 副教授",
     "abstract": "上海交通大学，研究方向：边缘计算与RL。", "metadata": {"affiliation": "上海交通大学", "field": "edge_computing"}},
    {"id": "n_author_003", "node_type": "author", "title": "孙静 研究员",
     "abstract": "中科院自动化所，研究方向：NLP与RAG。", "metadata": {"affiliation": "中科院", "field": "nlp"}},
    {"id": "n_author_004", "node_type": "author", "title": "陈希 教授",
     "abstract": "北京大学，研究方向：CV与扩散模型。", "metadata": {"affiliation": "北京大学", "field": "computer_vision"}},
    {"id": "n_author_005", "node_type": "author", "title": "王晓敏 教授",
     "abstract": "北京大学中文系，研究方向：现代文学。", "metadata": {"affiliation": "北京大学", "field": "modern_literature"}},
    {"id": "n_author_006", "node_type": "author", "title": "周晓虹 教授",
     "abstract": "南京大学社会学院，研究方向：平台经济。", "metadata": {"affiliation": "南京大学", "field": "sociology"}},
    {"id": "n_author_007", "node_type": "author", "title": "林毅夫 教授",
     "abstract": "北京大学国发院，研究方向：数字经济。", "metadata": {"affiliation": "北京大学", "field": "economics"}},
    {"id": "n_author_008", "node_type": "author", "title": "李家洋 院士",
     "abstract": "中科院遗传发育所，研究方向：CRISPR与作物改良。", "metadata": {"affiliation": "中科院", "field": "plant_biology"}},

    # 概念节点（5个）
    {"id": "n_concept_001", "node_type": "concept", "title": "现代性焦虑",
     "abstract": "现代性转型中的精神不安。", "metadata": {"discipline": "literature"}},
    {"id": "n_concept_002", "node_type": "concept", "title": "平台资本主义",
     "abstract": "平台经济下的资本积累模式。", "metadata": {"discipline": "sociology"}},
    {"id": "n_concept_003", "node_type": "concept", "title": "数字鸿沟",
     "abstract": "数字技术接入与使用的不平等。", "metadata": {"discipline": "sociology"}},
    {"id": "n_concept_004", "node_type": "concept", "title": "幻觉检测",
     "abstract": "LLM生成内容的真实性验证。", "metadata": {"discipline": "ai"}},
    {"id": "n_concept_005", "node_type": "concept", "title": "提示缓存",
     "abstract": "通过前缀复用降低LLM调用成本。", "metadata": {"discipline": "ai"}},

    # 数据集节点（5个）
    {"id": "n_dataset_001", "node_type": "dataset", "title": "Devign",
     "abstract": "C/C++漏洞检测数据集。", "metadata": {"size": 27618, "language": "C/C++"}},
    {"id": "n_dataset_002", "node_type": "dataset", "title": "Big-Vul",
     "abstract": "大规模漏洞数据集。", "metadata": {"size": 188951, "language": "C/C++"}},
    {"id": "n_dataset_003", "node_type": "dataset", "title": "CMBQA",
     "abstract": "中文医疗问答基准。", "metadata": {"size": 25000, "domain": "medical"}},
    {"id": "n_dataset_004", "node_type": "dataset", "title": "MVTec AD",
     "abstract": "工业异常检测数据集。", "metadata": {"size": 5354, "domain": "industrial"}},
    {"id": "n_dataset_005", "node_type": "dataset", "title": "CARLA Simulator",
     "abstract": "自动驾驶仿真平台。", "metadata": {"type": "simulator", "domain": "autonomous_driving"}},
]


# ===== 学脉边样本 =====
SAMPLE_LINEAGE_EDGES: list[dict] = [
    # 论文引用关系
    {"id": "e_001", "source_id": "n_paper_001", "target_id": "n_paper_007", "relation_type": "cites", "weight": 0.8},
    {"id": "e_002", "source_id": "n_paper_003", "target_id": "n_paper_007", "relation_type": "cites", "weight": 0.7},
    {"id": "e_003", "source_id": "n_paper_004", "target_id": "n_paper_003", "relation_type": "cites", "weight": 0.6},
    {"id": "e_004", "source_id": "n_paper_005", "target_id": "n_paper_003", "relation_type": "cites", "weight": 0.5},
    {"id": "e_005", "source_id": "n_paper_006", "target_id": "n_paper_002", "relation_type": "cites", "weight": 0.4},
    {"id": "e_006", "source_id": "n_paper_010", "target_id": "n_paper_002", "relation_type": "cites", "weight": 0.6},
    {"id": "e_007", "source_id": "n_paper_014", "target_id": "n_paper_015", "relation_type": "cites", "weight": 0.5},

    # 论题衍生自论文
    {"id": "e_008", "source_id": "n_topic_001", "target_id": "n_paper_001", "relation_type": "derived_from", "weight": 0.9},
    {"id": "e_009", "source_id": "n_topic_002", "target_id": "n_paper_002", "relation_type": "derived_from", "weight": 0.9},
    {"id": "e_010", "source_id": "n_topic_003", "target_id": "n_paper_003", "relation_type": "derived_from", "weight": 0.9},
    {"id": "e_011", "source_id": "n_topic_004", "target_id": "n_paper_004", "relation_type": "derived_from", "weight": 0.9},
    {"id": "e_012", "source_id": "n_topic_005", "target_id": "n_paper_005", "relation_type": "derived_from", "weight": 0.9},
    {"id": "e_013", "source_id": "n_topic_006", "target_id": "n_paper_011", "relation_type": "derived_from", "weight": 0.9},
    {"id": "e_014", "source_id": "n_topic_007", "target_id": "n_paper_014", "relation_type": "derived_from", "weight": 0.9},
    {"id": "e_015", "source_id": "n_topic_008", "target_id": "n_paper_015", "relation_type": "derived_from", "weight": 0.9},
    {"id": "e_016", "source_id": "n_topic_009", "target_id": "n_paper_026", "relation_type": "derived_from", "weight": 0.9},
    {"id": "e_017", "source_id": "n_topic_010", "target_id": "n_paper_027", "relation_type": "derived_from", "weight": 0.9},

    # 论题使用方法
    {"id": "e_018", "source_id": "n_topic_001", "target_id": "n_method_001", "relation_type": "related", "weight": 0.8},
    {"id": "e_019", "source_id": "n_topic_002", "target_id": "n_method_002", "relation_type": "related", "weight": 0.8},
    {"id": "e_020", "source_id": "n_topic_003", "target_id": "n_method_003", "relation_type": "related", "weight": 0.8},
    {"id": "e_021", "source_id": "n_topic_004", "target_id": "n_method_004", "relation_type": "related", "weight": 0.8},
    {"id": "e_022", "source_id": "n_topic_005", "target_id": "n_method_005", "relation_type": "related", "weight": 0.8},
    {"id": "e_023", "source_id": "n_topic_006", "target_id": "n_concept_001", "relation_type": "related", "weight": 0.7},
    {"id": "e_024", "source_id": "n_topic_007", "target_id": "n_concept_002", "relation_type": "related", "weight": 0.7},
    {"id": "e_025", "source_id": "n_topic_008", "target_id": "n_concept_003", "relation_type": "related", "weight": 0.7},

    # 作者指导论文
    {"id": "e_026", "source_id": "n_author_001", "target_id": "n_paper_001", "relation_type": "advises", "weight": 0.9},
    {"id": "e_027", "source_id": "n_author_002", "target_id": "n_paper_002", "relation_type": "advises", "weight": 0.9},
    {"id": "e_028", "source_id": "n_author_003", "target_id": "n_paper_003", "relation_type": "advises", "weight": 0.9},
    {"id": "e_029", "source_id": "n_author_004", "target_id": "n_paper_004", "relation_type": "advises", "weight": 0.9},
    {"id": "e_030", "source_id": "n_author_005", "target_id": "n_paper_011", "relation_type": "advises", "weight": 0.9},
    {"id": "e_031", "source_id": "n_author_006", "target_id": "n_paper_014", "relation_type": "advises", "weight": 0.9},
    {"id": "e_032", "source_id": "n_author_007", "target_id": "n_paper_015", "relation_type": "advises", "weight": 0.9},

    # 论文使用数据集
    {"id": "e_033", "source_id": "n_paper_001", "target_id": "n_dataset_001", "relation_type": "related", "weight": 0.6},
    {"id": "e_034", "source_id": "n_paper_001", "target_id": "n_dataset_002", "relation_type": "related", "weight": 0.6},
    {"id": "e_035", "source_id": "n_paper_003", "target_id": "n_dataset_003", "relation_type": "related", "weight": 0.6},
    {"id": "e_036", "source_id": "n_paper_004", "target_id": "n_dataset_004", "relation_type": "related", "weight": 0.6},
    {"id": "e_037", "source_id": "n_paper_006", "target_id": "n_dataset_005", "relation_type": "related", "weight": 0.6},

    # 概念关联
    {"id": "e_038", "source_id": "n_concept_004", "target_id": "n_concept_005", "relation_type": "related", "weight": 0.5},
    {"id": "e_039", "source_id": "n_concept_002", "target_id": "n_concept_003", "relation_type": "related", "weight": 0.5},

    # 方法关联
    {"id": "e_040", "source_id": "n_method_001", "target_id": "n_method_006", "relation_type": "related", "weight": 0.4},
    {"id": "e_041", "source_id": "n_method_003", "target_id": "n_method_006", "relation_type": "related", "weight": 0.4},
    {"id": "e_042", "source_id": "n_method_004", "target_id": "n_method_006", "relation_type": "related", "weight": 0.4},

    # 反向引用
    {"id": "e_043", "source_id": "n_paper_007", "target_id": "n_paper_001", "relation_type": "cited_by", "weight": 0.3},
    {"id": "e_044", "source_id": "n_paper_015", "target_id": "n_paper_014", "relation_type": "cited_by", "weight": 0.3},

    # 反向指导
    {"id": "e_045", "source_id": "n_paper_001", "target_id": "n_author_001", "relation_type": "advised_by", "weight": 0.9},
    {"id": "e_046", "source_id": "n_paper_003", "target_id": "n_author_003", "relation_type": "advised_by", "weight": 0.9},
]


# ===== 学脉元数据样本 =====
SAMPLE_LINEAGE_METADATA: dict = {
    "graph_stats": {
        "total_nodes": len(SAMPLE_LINEAGE_NODES),
        "total_edges": len(SAMPLE_LINEAGE_EDGES),
        "node_types": {
            "paper": sum(1 for n in SAMPLE_LINEAGE_NODES if n["node_type"] == "paper"),
            "topic": sum(1 for n in SAMPLE_LINEAGE_NODES if n["node_type"] == "topic"),
            "method": sum(1 for n in SAMPLE_LINEAGE_NODES if n["node_type"] == "method"),
            "author": sum(1 for n in SAMPLE_LINEAGE_NODES if n["node_type"] == "author"),
            "concept": sum(1 for n in SAMPLE_LINEAGE_NODES if n["node_type"] == "concept"),
            "dataset": sum(1 for n in SAMPLE_LINEAGE_NODES if n["node_type"] == "dataset"),
        },
        "relation_types": {
            "cites": sum(1 for e in SAMPLE_LINEAGE_EDGES if e["relation_type"] == "cites"),
            "derived_from": sum(1 for e in SAMPLE_LINEAGE_EDGES if e["relation_type"] == "derived_from"),
            "related": sum(1 for e in SAMPLE_LINEAGE_EDGES if e["relation_type"] == "related"),
            "advises": sum(1 for e in SAMPLE_LINEAGE_EDGES if e["relation_type"] == "advises"),
            "cited_by": sum(1 for e in SAMPLE_LINEAGE_EDGES if e["relation_type"] == "cited_by"),
            "advised_by": sum(1 for e in SAMPLE_LINEAGE_EDGES if e["relation_type"] == "advised_by"),
        },
    },
    "type_colors": {
        "paper": "#F59E0B",
        "topic": "#3B82F6",
        "method": "#10B981",
        "author": "#8B5CF6",
        "concept": "#EC4899",
        "dataset": "#6B7280",
    },
    "type_labels": {
        "paper": "文献",
        "topic": "论题",
        "method": "方法",
        "author": "导师",
        "concept": "概念",
        "dataset": "数据",
    },
}


def build_lineage_graph() -> dict:
    """构建完整的学脉图谱数据

    Returns:
        包含 nodes、edges、stats 的图谱字典。
    """
    return {
        "nodes": SAMPLE_LINEAGE_NODES,
        "edges": SAMPLE_LINEAGE_EDGES,
        "stats": SAMPLE_LINEAGE_METADATA["graph_stats"],
    }


def get_nodes_by_type(node_type: str) -> list[dict]:
    """按类型获取节点

    Args:
        node_type: 节点类型（paper/topic/method/author/concept/dataset）。

    Returns:
        匹配类型的节点列表。
    """
    return [n for n in SAMPLE_LINEAGE_NODES if n["node_type"] == node_type]


def get_edges_by_relation(relation_type: str) -> list[dict]:
    """按关系类型获取边

    Args:
        relation_type: 关系类型（cites/derived_from/related/advises 等）。

    Returns:
        匹配关系类型的边列表。
    """
    return [e for e in SAMPLE_LINEAGE_EDGES if e["relation_type"] == relation_type]


def get_node_by_id(node_id: str) -> Optional[dict]:
    """按 ID 获取单个节点

    Args:
        node_id: 节点 ID。

    Returns:
        匹配的节点字典，未找到时返回 None。
    """
    for node in SAMPLE_LINEAGE_NODES:
        if node["id"] == node_id:
            return node
    return None


def get_neighbors(node_id: str) -> list[dict]:
    """获取与指定节点直接相连的邻居节点

    Args:
        node_id: 目标节点 ID。

    Returns:
        邻居节点列表（包含 source 和 target 两个方向的邻居）。
    """
    neighbor_ids = set()
    for edge in SAMPLE_LINEAGE_EDGES:
        if edge["source_id"] == node_id:
            neighbor_ids.add(edge["target_id"])
        elif edge["target_id"] == node_id:
            neighbor_ids.add(edge["source_id"])
    return [n for n in SAMPLE_LINEAGE_NODES if n["id"] in neighbor_ids]


def get_node_type_distribution() -> dict[str, int]:
    """获取节点类型分布统计

    Returns:
        节点类型到数量的映射字典。
    """
    distribution: dict[str, int] = {}
    for node in SAMPLE_LINEAGE_NODES:
        node_type = node["node_type"]
        distribution[node_type] = distribution.get(node_type, 0) + 1
    return distribution


# 模块导入时断言样本数量满足要求
assert len(SAMPLE_LINEAGE_NODES) >= 50, f"节点样本不足50个，当前 {len(SAMPLE_LINEAGE_NODES)}"
assert len(SAMPLE_LINEAGE_EDGES) >= 30, f"边样本不足30条，当前 {len(SAMPLE_LINEAGE_EDGES)}"
assert len(SAMPLE_LINEAGE_METADATA["graph_stats"]["node_types"]) == 6, "节点类型不足6种"
