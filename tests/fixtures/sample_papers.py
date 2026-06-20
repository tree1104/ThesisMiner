"""学术论文样本数据

提供 30+ 跨学科、跨年份（2024-2026）的学术论文样本，
供集成测试、E2E 测试与压测使用。每篇论文包含：
- title: 标题
- authors: 作者列表
- year: 发表年份
- venue: 发表期刊/会议
- abstract: 摘要
- discipline: 所属学科
- doi: DOI 标识
- keywords: 关键词列表
- citations: 被引次数
"""
from typing import Optional


# ===== 30+ 学术论文样本 =====
SAMPLE_PAPERS: list[dict] = [
    # ===== 计算机科学 / 人工智能（10篇）=====
    {
        "id": "paper_001",
        "title": "Graph Neural Networks for Software Vulnerability Detection: A Survey",
        "authors": ["Zhang Wei", "Li Ming", "Chen Yu"],
        "year": 2024,
        "venue": "ACM Computing Surveys",
        "discipline": "computer_science",
        "doi": "10.1145/3697.2024.001",
        "keywords": ["graph neural networks", "vulnerability detection", "software security"],
        "citations": 156,
        "abstract": (
            "Software vulnerability detection has become a critical research area "
            "with the increasing frequency of security incidents. "
            "Graph Neural Networks (GNNs) have emerged as a promising approach "
            "by modeling source code as graph structures. "
            "This survey provides a comprehensive review of GNN-based vulnerability "
            "detection methods, covering code graph construction, "
            "GNN architecture design, and evaluation methodologies. "
            "We identify key challenges including cross-project generalization, "
            "interpretability, and scalability, and propose future research directions."
        ),
    },
    {
        "id": "paper_002",
        "title": "Efficient Container Scheduling for Edge Computing via Multi-Agent Reinforcement Learning",
        "authors": ["Wang Lei", "Liu Hong", "Zhao Qiang"],
        "year": 2024,
        "venue": "IEEE Transactions on Edge Computing",
        "discipline": "computer_science",
        "doi": "10.1109/TEC.2024.002",
        "keywords": ["edge computing", "container scheduling", "reinforcement learning"],
        "citations": 89,
        "abstract": (
            "Edge computing brings computation closer to data sources, "
            "enabling latency-sensitive applications. "
            "However, resource-constrained edge nodes and fluctuating workloads "
            "pose significant challenges for container scheduling. "
            "We propose a multi-agent reinforcement learning framework "
            "that jointly optimizes latency, resource utilization, and load balance. "
            "Experiments on a real testbed show 32% latency reduction "
            "compared to Kubernetes default scheduler."
        ),
    },
    {
        "id": "paper_003",
        "title": "Retrieval-Augmented Generation for Domain-Specific Question Answering",
        "authors": ["Sun Jing", "Hu Yang", "Lin Tao"],
        "year": 2024,
        "venue": "ACL 2024",
        "discipline": "artificial_intelligence",
        "doi": "10.18653/v1/2024.acl-long.003",
        "keywords": ["RAG", "question answering", "large language models"],
        "citations": 312,
        "abstract": (
            "Large Language Models (LLMs) demonstrate remarkable capabilities "
            "in general question answering but suffer from hallucinations "
            "and outdated knowledge in domain-specific scenarios. "
            "We propose a Retrieval-Augmented Generation (RAG) framework "
            "with a three-stage prompt caching mechanism to reduce API costs. "
            "Our system achieves 87.6% expert-validated accuracy "
            "on a Chinese medical QA benchmark, significantly outperforming vanilla LLMs."
        ),
    },
    {
        "id": "paper_004",
        "title": "MetaDiff: Few-Shot Image Generation via Meta-Learning and Diffusion Models",
        "authors": ["Chen Xi", "Wu Jie", "Yang Fan"],
        "year": 2025,
        "venue": "CVPR 2025",
        "discipline": "artificial_intelligence",
        "doi": "10.1109/CVPR.2025.004",
        "keywords": ["diffusion models", "few-shot learning", "image generation"],
        "citations": 78,
        "abstract": (
            "Diffusion models have achieved breakthrough performance in image generation "
            "but typically require large-scale training data. "
            "We propose MetaDiff, a framework that fuses meta-learning with diffusion models "
            "for few-shot image generation. "
            "By meta-learning the initialization of the denoising network "
            "and injecting class prototypes as conditional signals, "
            "MetaDiff achieves 24.7% FID reduction in 5-shot settings "
            "on medical imaging and industrial defect datasets."
        ),
    },
    {
        "id": "paper_005",
        "title": "Federated Learning for Multi-Modal Medical Image Diagnosis with Privacy Preservation",
        "authors": ["Liu Yan", "Zhang Hua", "Wang Bin"],
        "year": 2025,
        "venue": "Nature Machine Intelligence",
        "discipline": "artificial_intelligence",
        "doi": "10.1038/s42256-025-005",
        "keywords": ["federated learning", "medical imaging", "privacy"],
        "citations": 145,
        "abstract": (
            "Multi-modal medical image diagnosis faces challenges in data privacy "
            "and institutional silos. "
            "We propose a federated learning framework that enables collaborative training "
            "across hospitals without sharing raw data. "
            "Our method employs cross-modal attention and differential privacy "
            "to achieve 92.3% diagnostic accuracy on a multi-center dataset "
            "while preserving patient privacy."
        ),
    },
    {
        "id": "paper_006",
        "title": "End-to-End Decision Transformer for Autonomous Driving",
        "authors": ["Park Sangwoo", "Kim Minjoon", "Lee Jieun"],
        "year": 2025,
        "venue": "NeurIPS 2025",
        "discipline": "artificial_intelligence",
        "doi": "10.48550/arXiv.2025.006",
        "keywords": ["autonomous driving", "transformer", "decision making"],
        "citations": 67,
        "abstract": (
            "End-to-end learning for autonomous driving has gained significant attention. "
            "We propose an End-to-End Decision Transformer architecture "
            "that directly maps sensor inputs to driving actions. "
            "Our model handles multi-modal sensor fusion and long-horizon planning "
            "within a unified transformer framework. "
            "Experiments on CARLA simulator demonstrate 18% improvement "
            "in driving success rate over prior methods."
        ),
    },
    {
        "id": "paper_007",
        "title": "Contrastive Learning for Cross-Lingual Text Representation",
        "authors": ["Garcia Maria", "Schmidt Hans", "Rossi Elena"],
        "year": 2024,
        "venue": "EMNLP 2024",
        "discipline": "artificial_intelligence",
        "doi": "10.18653/v1/2024.emnlp-main.007",
        "keywords": ["contrastive learning", "cross-lingual", "text representation"],
        "citations": 203,
        "abstract": (
            "Cross-lingual text representation is fundamental for multilingual NLP. "
            "We propose a contrastive learning framework that aligns representations "
            "across languages without parallel data. "
            "Our method leverages back-translation and momentum contrast "
            "to learn language-invariant features. "
            "On XNLI and XTREME benchmarks, our approach outperforms "
            "supervised baselines by 4.2% on average."
        ),
    },
    {
        "id": "paper_008",
        "title": "Blockchain-Based Supply Chain Traceability with Zero-Knowledge Proofs",
        "authors": ["Tanaka Yuki", "Suzuki Ken", "Yamada Akira"],
        "year": 2024,
        "venue": "IEEE Blockchain 2024",
        "discipline": "computer_science",
        "doi": "10.1109/Blockchain.2024.008",
        "keywords": ["blockchain", "supply chain", "zero-knowledge proofs"],
        "citations": 56,
        "abstract": (
            "Supply chain traceability requires transparency and privacy simultaneously. "
            "We propose a blockchain-based traceability system "
            "that employs zero-knowledge proofs to verify product authenticity "
            "without revealing sensitive business data. "
            "Our implementation on Ethereum testnet achieves "
            "sub-second verification time with 40% gas cost reduction."
        ),
    },
    {
        "id": "paper_009",
        "title": "Differential Privacy for Location-Based Services: A Utility-Privacy Tradeoff",
        "authors": ["Anderson James", "Brown Sarah", "Clark David"],
        "year": 2025,
        "venue": "IEEE Transactions on Mobile Computing",
        "discipline": "computer_science",
        "doi": "10.1109/TMC.2025.009",
        "keywords": ["differential privacy", "location services", "privacy"],
        "citations": 91,
        "abstract": (
            "Location-based services collect vast amounts of user location data, "
            "raising serious privacy concerns. "
            "We propose a differential privacy mechanism "
            "that achieves optimal utility-privacy tradeoff for location queries. "
            "Our method adapts the privacy budget based on query sensitivity "
            "and user mobility patterns, providing 35% utility improvement "
            "over baseline mechanisms at the same privacy guarantee."
        ),
    },
    {
        "id": "paper_010",
        "title": "Multi-Agent Reinforcement Learning for Traffic Signal Control",
        "authors": ["Mohamed Ahmed", "Fatima Hassan", "Omar Khalid"],
        "year": 2026,
        "venue": "Transportation Research Part C",
        "discipline": "artificial_intelligence",
        "doi": "10.1016/j.trc.2026.010",
        "keywords": ["multi-agent RL", "traffic signal", "smart transportation"],
        "citations": 34,
        "abstract": (
            "Traffic signal control is a complex multi-agent decision problem. "
            "We propose a multi-agent reinforcement learning framework "
            "with graph attention communication for urban traffic signal control. "
            "Our method learns cooperative policies across intersections "
            "and adapts to varying traffic conditions. "
            "Experiments on SUMO simulator show 22% travel time reduction "
            "compared to fixed-time and actuated controllers."
        ),
    },
    # ===== 文学（5篇）=====
    {
        "id": "paper_011",
        "title": "Modernity and Anxiety in Lu Xun's Fiction: A Narrative Analysis",
        "authors": ["Wang Xiaoming", "Zhang Ling"],
        "year": 2024,
        "venue": "Modern Chinese Literature and Culture",
        "discipline": "literature",
        "doi": "10.1086/mclc.2024.011",
        "keywords": ["Lu Xun", "modernity", "anxiety", "narrative"],
        "citations": 28,
        "abstract": (
            "This paper examines the narrative strategies of modernity anxiety "
            "in Lu Xun's fiction collections Call to Arms and Wandering. "
            "Through close reading of representative stories, "
            "we identify three narrative patterns: the gaze structure, "
            "repetition and delay, and irony and paradox. "
            "These strategies not only construct a unique aesthetic of anxiety "
            "but also reveal the spiritual predicament of modern Chinese intellectuals."
        ),
    },
    {
        "id": "paper_012",
        "title": "Female Writing and Gender Consciousness in Song Dynasty Ci Poetry",
        "authors": ["Li Hua", "Chen Mei"],
        "year": 2024,
        "venue": "Journal of Chinese Literature",
        "discipline": "literature",
        "doi": "10.1086/jcl.2024.012",
        "keywords": ["Song Dynasty", "ci poetry", "gender", "female writing"],
        "citations": 45,
        "abstract": (
            "Song Dynasty ci poetry witnessed a flourishing of female voices. "
            "This paper examines the gender consciousness in female-authored ci, "
            "focusing on Li Qingzhao, Zhu Shuzhen, and Zhang Yuniang. "
            "We argue that these poets developed a distinct feminine poetics "
            "that challenged patriarchal literary conventions "
            "and articulated women's emotional and intellectual experiences."
        ),
    },
    {
        "id": "paper_013",
        "title": "Narrative Transformation in Web Novel IP Adaptations",
        "authors": ["Zhao Wei", "Sun Li"],
        "year": 2025,
        "venue": "Contemporary Chinese Literature",
        "discipline": "literature",
        "doi": "10.1086/ccl.2025.013",
        "keywords": ["web novel", "IP adaptation", "narrative", "cultural reconstruction"],
        "citations": 62,
        "abstract": (
            "The adaptation of web novels into films and TV dramas "
            "involves complex narrative transformations. "
            "This paper analyzes 50 adaptations from 2020-2024, "
            "identifying key strategies: condensation, expansion, and transposition. "
            "We argue that successful adaptations balance fidelity to the source "
            "with the affordances of the target medium."
        ),
    },
    {
        "id": "paper_014",
        "title": "Urban Space in Ming-Qing Vernacular Fiction",
        "authors": ["Liu Peng", "Wang Hong"],
        "year": 2024,
        "venue": "Chinese Literature: Essays, Articles, Reviews",
        "discipline": "literature",
        "doi": "10.1086/clear.2024.014",
        "keywords": ["Ming-Qing fiction", "urban space", "vernacular literature"],
        "citations": 19,
        "abstract": (
            "Ming-Qing vernacular fiction represents a rich archive "
            "of urban spatial imagination. "
            "This paper examines the representation of cities in Jinpingmei, "
            "Sanyan, and Erpai, arguing that urban spaces serve as both "
            "settings and symbolic structures that shape narrative meaning. "
            "We identify four spatial types: marketplace, garden, brothel, and yamen."
        ),
    },
    {
        "id": "paper_015",
        "title": "Technological Imagination and Humanistic Reflection in Contemporary Chinese Science Fiction",
        "authors": ["Chen Si", "Wu Yan"],
        "year": 2025,
        "venue": "Science Fiction Studies",
        "discipline": "literature",
        "doi": "10.1086/sfs.2025.015",
        "keywords": ["science fiction", "technology", "humanism", "Liu Cixin"],
        "citations": 87,
        "abstract": (
            "Contemporary Chinese science fiction, represented by Liu Cixin, "
            "Hao Jingfang, and Baoshu, exhibits a distinctive technological imagination "
            "inflected by humanistic concerns. "
            "This paper analyzes how these authors negotiate the tension "
            "between technological optimism and humanistic anxiety, "
            "offering a unique Chinese perspective on global SF."
        ),
    },
    # ===== 社会学（5篇）=====
    {
        "id": "paper_016",
        "title": "Labor Rights of Gig Workers in Platform Economy: A Comparative Study",
        "authors": ["Zhou Xiaohong", "Li Peilin"],
        "year": 2024,
        "venue": "Chinese Sociological Review",
        "discipline": "sociology",
        "doi": "10.1080/csr.2024.016",
        "keywords": ["gig economy", "labor rights", "platform capitalism"],
        "citations": 134,
        "abstract": (
            "The platform economy has created a large population of gig workers "
            "who face precarious labor conditions. "
            "Based on surveys of 1,200 gig workers in Beijing, Shanghai, and Shenzhen, "
            "this paper examines labor rights deficits in劳动关系认定, "
            "social insurance, and collective bargaining. "
            "We propose a \"third-category worker\" framework "
            "to extend labor protections to gig workers."
        ),
    },
    {
        "id": "paper_017",
        "title": "Reconstruction of Rural Public Cultural Space under Rural Revitalization",
        "authors": ["Fei Xiaotong", "Wang Mingming"],
        "year": 2024,
        "venue": "Sociological Studies",
        "discipline": "sociology",
        "doi": "10.1080/ss.2024.017",
        "keywords": ["rural revitalization", "cultural space", "community"],
        "citations": 76,
        "abstract": (
            "Rural revitalization strategy emphasizes cultural revitalization. "
            "This paper examines the reconstruction of rural public cultural spaces "
            "in three villages in Zhejiang Province. "
            "We identify three models: state-led, community-driven, and market-oriented, "
            "and analyze their implications for rural cultural governance."
        ),
    },
    {
        "id": "paper_018",
        "title": "Social Media Use and Adolescent Identity Formation: An Empirical Study",
        "authors": ["Zhang Wen", "Li Jing"],
        "year": 2025,
        "venue": "Journal of Youth Studies",
        "discipline": "sociology",
        "doi": "10.1080/jys.2025.018",
        "keywords": ["social media", "adolescent", "identity", "empirical study"],
        "citations": 98,
        "abstract": (
            "Social media has become integral to adolescent identity formation. "
            "Based on a survey of 3,000 adolescents aged 13-18, "
            "this paper examines how social media use patterns "
            "relate to identity dimensions: personal, social, and moral. "
            "We find that active content creation positively predicts identity clarity, "
            "while passive scrolling is associated with identity confusion."
        ),
    },
    {
        "id": "paper_019",
        "title": "Community Home-Based Elderly Care Services under Population Aging",
        "authors": ["Wang Sibin", "Liu Yuzhi"],
        "year": 2024,
        "venue": "Population Research",
        "discipline": "sociology",
        "doi": "10.1080/pr.2024.019",
        "keywords": ["aging", "community care", "elderly services"],
        "citations": 112,
        "abstract": (
            "Population aging poses significant challenges for elderly care. "
            "This paper examines the development of community home-based care "
            "in 15 Chinese cities. "
            "We identify key challenges: service fragmentation, workforce shortage, "
            "and funding sustainability. "
            "We propose an integrated care model combining medical, social, "
            "and smart technology services."
        ),
    },
    {
        "id": "paper_020",
        "title": "Affective Labor of Food Delivery Riders: A Sociological Analysis",
        "authors": ["Shen Yuan", "Guo Yuhua"],
        "year": 2025,
        "venue": "Sociological Review",
        "discipline": "sociology",
        "doi": "10.1080/sr.2025.020",
        "keywords": ["affective labor", "food delivery", "algorithmic management"],
        "citations": 67,
        "abstract": (
            "Food delivery riders perform significant affective labor "
            "beyond physical delivery. "
            "Based on ethnographic fieldwork with 60 riders in Beijing, "
            "this paper examines how algorithmic management shapes "
            "riders' emotional labor with customers, merchants, and platforms. "
            "We argue that affective labor is a hidden dimension "
            "of platform exploitation."
        ),
    },
    # ===== 经济学（5篇）=====
    {
        "id": "paper_021",
        "title": "Spillover Effects of Digital Economy on Regional Innovation Efficiency",
        "authors": ["Lin Yifu", "Cai Fang"],
        "year": 2024,
        "venue": "China Economic Review",
        "discipline": "economics",
        "doi": "10.1016/j.chieco.2024.021",
        "keywords": ["digital economy", "innovation efficiency", "spatial spillover"],
        "citations": 187,
        "abstract": (
            "Using panel data of 281 Chinese cities from 2013-2023, "
            "this paper examines the spillover effects of digital economy "
            "on regional innovation efficiency. "
            "Through spatial Durbin model analysis, we find significant positive "
            "direct and spillover effects. "
            "Human capital and industrial upgrading serve as mediating channels. "
            "Heterogeneity analysis reveals stronger effects in eastern regions."
        ),
    },
    {
        "id": "paper_022",
        "title": "ESG Performance and Corporate Financing Costs: Evidence from China",
        "authors": ["Zhang Weiying", "Zhou Qiren"],
        "year": 2024,
        "venue": "Journal of Corporate Finance",
        "discipline": "economics",
        "doi": "10.1016/j.jcorpfin.2024.022",
        "keywords": ["ESG", "financing cost", "corporate governance"],
        "citations": 156,
        "abstract": (
            "This paper examines the impact of ESG performance on corporate financing costs "
            "using A-share listed companies from 2015-2023. "
            "We find that firms with better ESG performance enjoy lower "
            "debt and equity financing costs. "
            "The effect is more pronounced for firms in heavily polluting industries "
            "and those with weaker governance. "
            "Mechanism analysis suggests reduced information asymmetry "
            "and lower risk premiums as key channels."
        ),
    },
    {
        "id": "paper_023",
        "title": "Green Finance and Industrial Structure Upgrading under Dual Carbon Goals",
        "authors": ["Li Yang", "Zhang Xiaojing"],
        "year": 2025,
        "venue": "Energy Economics",
        "discipline": "economics",
        "doi": "10.1016/j.eneco.2025.023",
        "keywords": ["green finance", "industrial upgrading", "dual carbon"],
        "citations": 89,
        "abstract": (
            "Under China's dual carbon goals, green finance plays a crucial role "
            "in industrial transformation. "
            "Using provincial panel data from 2010-2023, "
            "we examine the impact of green finance on industrial structure upgrading. "
            "Results show that green credit and green bonds significantly promote "
            "industrial rationalization and advancement. "
            "Technological innovation serves as a key mediator."
        ),
    },
    {
        "id": "paper_024",
        "title": "Digital Inclusive Finance and Urban-Rural Income Gap",
        "authors": ["Guo Feng", "Wang Jing"],
        "year": 2024,
        "venue": "World Development",
        "discipline": "economics",
        "doi": "10.1016/j.worlddev.2024.024",
        "keywords": ["digital finance", "income gap", "inclusive growth"],
        "citations": 234,
        "abstract": (
            "Digital inclusive finance may help narrow urban-rural income disparities. "
            "Using Peking University Digital Financial Inclusion Index "
            "and city-level data from 2011-2022, "
            "we find that digital finance significantly reduces the urban-rural income gap. "
            "The effect is stronger in central and western regions "
            "and for low-income groups. "
            "Rural entrepreneurship and human capital investment are key mechanisms."
        ),
    },
    {
        "id": "paper_025",
        "title": "Data Factor Marketization: Pricing Mechanisms and Governance",
        "authors": ["Xu Xianchun", "Liu Shijin"],
        "year": 2025,
        "venue": "Economic Research Journal",
        "discipline": "economics",
        "doi": "10.1080/erj.2025.025",
        "keywords": ["data factor", "marketization", "pricing", "governance"],
        "citations": 78,
        "abstract": (
            "Data has become a new factor of production, "
            "but its marketization faces unique challenges. "
            "This paper examines pricing mechanisms for data factors, "
            "including cost-based, market-based, and value-based approaches. "
            "We propose a hybrid pricing framework that accounts for "
            "data scarcity, quality, and usage scenarios. "
            "Governance implications for data trading platforms are discussed."
        ),
    },
    # ===== 生物学（5篇）=====
    {
        "id": "paper_026",
        "title": "CRISPR-Cas9 for Crop Trait Improvement: Recent Advances and Future Prospects",
        "authors": ["Li Jiayang", "Zhang Qifa"],
        "year": 2024,
        "venue": "Nature Biotechnology",
        "discipline": "biology",
        "doi": "10.1038/nbt.2024.026",
        "keywords": ["CRISPR", "crop improvement", "genome editing"],
        "citations": 412,
        "abstract": (
            "CRISPR-Cas9 has revolutionized crop improvement. "
            "This review covers recent advances in CRISPR-based editing "
            "for yield, disease resistance, and stress tolerance traits. "
            "We discuss base editing, prime editing, and multiplexed editing strategies, "
            "and examine regulatory frameworks for CRISPR-edited crops. "
            "Future directions include improving editing efficiency "
            "and expanding crop range."
        ),
    },
    {
        "id": "paper_027",
        "title": "Gut Microbiota and Metabolic Syndrome: Mechanistic Insights",
        "authors": ["Zhao Liping", "Wang Aiming"],
        "year": 2024,
        "venue": "Cell Metabolism",
        "discipline": "biology",
        "doi": "10.1016/j.cmet.2024.027",
        "keywords": ["gut microbiota", "metabolic syndrome", "microbiome"],
        "citations": 287,
        "abstract": (
            "Gut microbiota plays a critical role in metabolic syndrome. "
            "Using multi-omics analysis of 500 fecal samples, "
            "we identify microbial signatures associated with obesity, "
            "diabetes, and hypertension. "
            "Mechanistic studies reveal that specific bacterial metabolites "
            "modulate host metabolism through bile acid signaling "
            "and short-chain fatty acid production. "
            "Fecal microbiota transplantation shows therapeutic potential."
        ),
    },
    {
        "id": "paper_028",
        "title": "Single-Cell Sequencing Reveals Tumor Heterogeneity Landscape",
        "authors": ["Shao Feng", "Zhang Zemin"],
        "year": 2025,
        "venue": "Cancer Cell",
        "discipline": "biology",
        "doi": "10.1016/j.ccell.2025.028",
        "keywords": ["single-cell sequencing", "tumor heterogeneity", "cancer"],
        "citations": 198,
        "abstract": (
            "Tumor heterogeneity drives cancer progression and treatment resistance. "
            "We performed single-cell RNA sequencing on 50 tumor samples "
            "across five cancer types. "
            "Our analysis reveals conserved programs of tumor cell states "
            "and identifies rare drug-resistant subpopulations. "
            "Spatial transcriptomics further maps these states "
            "within tumor microenvironments, providing insights "
            "for combination therapy design."
        ),
    },
    {
        "id": "paper_029",
        "title": "Ecotoxicological Effects of Microplastics on Marine Plankton Communities",
        "authors": ["Wang You", "Sun Song"],
        "year": 2024,
        "venue": "Environmental Science & Technology",
        "discipline": "biology",
        "doi": "10.1021/est.2024.029",
        "keywords": ["microplastics", "marine plankton", "ecotoxicology"],
        "citations": 134,
        "abstract": (
            "Microplastic pollution poses growing threats to marine ecosystems. "
            "We conducted mesocosm experiments exposing plankton communities "
            "to environmentally relevant microplastic concentrations. "
            "Results show reduced plankton diversity and altered community structure. "
            "Copepods exhibit reduced feeding and reproduction, "
            "while cyanobacteria show paradoxical growth promotion. "
            "These findings highlight complex ecosystem-level effects."
        ),
    },
    {
        "id": "paper_030",
        "title": "Deep Learning for Protein Structure Prediction: From AlphaFold to Beyond",
        "authors": ["Zhang Yang", "Baker David"],
        "year": 2025,
        "venue": "Nature Methods",
        "discipline": "biology",
        "doi": "10.1038/nmeth.2025.030",
        "keywords": ["protein structure", "deep learning", "AlphaFold"],
        "citations": 356,
        "abstract": (
            "AlphaFold revolutionized protein structure prediction, "
            "but challenges remain for protein complexes, "
            "conformational ensembles, and protein-ligand interactions. "
            "We review recent advances including AlphaFold-Multimer, "
            "RoseTTAFold-AllAtom, and diffusion-based methods. "
            "We discuss applications in drug discovery, enzyme engineering, "
            "and protein design, and identify future directions."
        ),
    },
    {
        "id": "paper_031",
        "title": "Wetland Ecosystem Carbon Sinks and Climate Change Response",
        "authors": ["Yu Guirui", "Zhang Lei"],
        "year": 2025,
        "venue": "Global Change Biology",
        "discipline": "biology",
        "doi": "10.1111/gcb.2025.031",
        "keywords": ["wetland", "carbon sink", "climate change"],
        "citations": 102,
        "abstract": (
            "Wetlands are critical carbon sinks but are vulnerable to climate change. "
            "We conducted eddy covariance measurements across 12 wetland sites "
            "in China from 2010-2023. "
            "Results show that wetland carbon uptake has declined 15% over the period, "
            "driven by warming-induced methane emissions and hydrological changes. "
            "We project further carbon sink weakening under future climate scenarios, "
            "highlighting the need for wetland conservation."
        ),
    },
    {
        "id": "paper_032",
        "title": "Antibiotic Resistance Gene Dissemination in the Environment",
        "authors": ["Zhu Yongguan", "Tiedje James"],
        "year": 2024,
        "venue": "ISME Journal",
        "discipline": "biology",
        "doi": "10.1038/ismej.2024.032",
        "keywords": ["antibiotic resistance", "environmental dissemination", "One Health"],
        "citations": 245,
        "abstract": (
            "Antibiotic resistance genes (ARGs) spread through environmental pathways. "
            "We analyzed ARG profiles in soil, water, and air samples "
            "from 30 sites across China. "
            "Results show widespread ARG contamination, "
            "with wastewater treatment plants as major hotspots. "
            "Horizontal gene transfer via plasmids and integrons "
            "drives ARG dissemination. "
            "We propose a One Health framework for ARG surveillance and control."
        ),
    },
]


# 按学科分组的论文索引
PAPERS_BY_DISCIPLINE: dict[str, list[dict]] = {}
for _p in SAMPLE_PAPERS:
    PAPERS_BY_DISCIPLINE.setdefault(_p["discipline"], []).append(_p)


# 按年份分组的论文索引
PAPERS_BY_YEAR: dict[int, list[dict]] = {}
for _p in SAMPLE_PAPERS:
    PAPERS_BY_YEAR.setdefault(_p["year"], []).append(_p)


def get_papers_for_query(query: str, limit: int = 10) -> list[dict]:
    """根据查询关键词检索论文样本

    Args:
        query: 检索关键词。
        limit: 返回条数上限，默认 10。

    Returns:
        匹配的论文列表（按相关度排序，标题匹配优先）。
    """
    query_lower = query.lower()
    title_matches = []
    keyword_matches = []
    abstract_matches = []
    for paper in SAMPLE_PAPERS:
        if query_lower in paper["title"].lower():
            title_matches.append(paper)
        elif any(query_lower in kw.lower() for kw in paper.get("keywords", [])):
            keyword_matches.append(paper)
        elif query_lower in paper["abstract"].lower():
            abstract_matches.append(paper)
    results = title_matches + keyword_matches + abstract_matches
    return results[:limit]


# 模块导入时断言样本数量满足要求
assert len(SAMPLE_PAPERS) >= 30, f"论文样本不足30篇，当前 {len(SAMPLE_PAPERS)}"
assert len(PAPERS_BY_DISCIPLINE) >= 5, "学科覆盖不足5个"
assert all(y in PAPERS_BY_YEAR for y in [2024, 2025, 2026]), "年份覆盖不足"
