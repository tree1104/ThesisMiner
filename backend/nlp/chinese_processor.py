"""中文文本处理器模块

提供面向中文学术文本的深度处理能力，包括：
    - 中文分词（基于词典 + 双向最大匹配 + 字符级降级）
    - 词性标注（基于规则与词典的隐式标注）
    - 命名实体识别（人名/地名/机构/术语/时间/数字）
    - 中文句子分割（按。！？等标点感知）
    - 段落识别（按空行与缩进）
    - 中英文混合文本处理
    - 繁简转换（基于内置映射表）
    - 全半角转换
    - 中文关键词提取（TF-IDF / TextRank）
    - 中文摘要生成（基于 TextRank 与频率）
    - 中文情感分析（基于词典与规则）
    - 学术中文文本特殊处理（术语识别/公式识别/引用识别）
    - 中文文本去重（基于 SimHash 与 MinHash）
    - 中文相似度计算（余弦/Jaccard/编辑距离）

仅使用 Python 标准库实现，可选依赖 jieba（中文分词），
缺失时自动降级为字符级处理与内置词典的双向最大匹配算法。

典型用法：
    processor = ChineseProcessor()
    tokens = processor.tokenize("深度学习在自然语言处理中的应用研究")
    keywords = processor.extract_keywords(text, top_k=10, method="tfidf")
    summary = processor.generate_summary(text, ratio=0.3)
    entities = processor.ner(text)
    similarity = processor.compute_similarity(text1, text2, method="cosine")
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# 尝试导入可选依赖 jieba（中文分词）
try:
    import jieba  # type: ignore
    import jieba.posseg as pseg  # type: ignore

    _HAS_JIEBA = True
except ImportError:  # pragma: no cover - 降级处理
    jieba = None  # type: ignore
    pseg = None  # type: ignore
    _HAS_JIEBA = False

# 尝试导入项目内日志
try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


# ===== 常量定义 =====

# 中文标点集合
CHINESE_PUNCTUATIONS = "，。！？；：、""''（）《》【】「」『』…—·～·"

# 英文标点集合
ENGLISH_PUNCTUATIONS = ",.!?;:\"'()[]{}<>-~"

# 句子结束符（中英文）
SENTENCE_ENDINGS = "。！？!?；;\n\r"

# 段落分隔符
PARAGRAPH_SEPARATORS = "\n\r"

# 中文字符正则（基本汉字 + 扩展A + 兼容汉字）
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")

# 中文字符范围（用于逐字判断）
CJK_RANGES = [
    (0x4E00, 0x9FFF),    # CJK 统一汉字
    (0x3400, 0x4DBF),    # CJK 扩展 A
    (0xF900, 0xFAFF),    # CJK 兼容汉字
    (0x20000, 0x2A6DF),  # CJK 扩展 B
    (0x2A700, 0x2B73F),  # CJK 扩展 C
    (0x2B740, 0x2B81F),  # CJK 扩展 D
]

# 英文单词正则
ENGLISH_WORD_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z'-]*")

# 数字正则
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")

# 引用模式（如 [1] / (Smith, 2020) / 张三（2020））
CITATION_PATTERNS = [
    re.compile(r"\[\d+(?:[-,]\s*\d+)*\]"),  # [1] / [1,2,3] / [1-3]
    re.compile(r"\(\s*[A-Z][a-zA-Z]+(?:\s+et\s+al\.?)?\s*,\s*\d{4}\s*\)"),  # (Smith, 2020)
    re.compile(r"\(\s*[A-Z][a-zA-Z]+(?:\s+(?:and|&)\s+[A-Z][a-zA-Z]+)?\s*,\s*\d{4}\s*\)"),
    re.compile(r"[\u4e00-\u9fff]{2,4}（\d{4}）"),  # 张三（2020）
    re.compile(r"[\u4e00-\u9fff]{2,4}等（\d{4}）"),  # 张三等（2020）
]

# 公式模式（简化识别）
FORMULA_PATTERNS = [
    re.compile(r"\$\$[^$]+\$\$"),  # $$...$$ 块级公式
    re.compile(r"\$[^$]+\$"),  # $...$ 行内公式
    re.compile(r"\\\([^)]+\\\)"),  # \(...\)
    re.compile(r"\\\[[^\]]+\\\]"),  # \[...\]
    re.compile(r"\\begin\{equation\}.*?\\end\{equation\}", re.DOTALL),  # LaTeX equation
]

# 章节标题模式
SECTION_TITLE_PATTERNS = [
    re.compile(r"^第[一二三四五六七八九十百千零\d]+[章节部分篇][\s　]*(.+)$"),  # 第一章 标题
    re.compile(r"^([一二三四五六七八九十百千零]+)[、.\s　]+(.+)$"),  # 一、标题
    re.compile(r"^(\d+(?:\.\d+)*)[\s　]+(.+)$"),  # 1. 标题 / 1.1 标题
    re.compile(r"^#+\s+(.+)$"),  # Markdown 标题
]

# 默认停用词表（中文常见停用词）
DEFAULT_STOPWORDS = {
    # 代词
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "它", "他", "她", "们", "我们", "你们", "他们", "这个", "那个",
    "这些", "那些", "什么", "怎么", "为什么", "哪里", "哪个", "哪些", "谁", "哪",
    # 介词与连词
    "把", "被", "让", "使", "对", "向", "从", "跟", "和", "与", "及", "或", "但",
    "但是", "然而", "虽然", "尽管", "因为", "所以", "因此", "于是", "如果", "假如",
    "只要", "只有", "除非", "除了", "由于", "由", "于", "对于", "关于", "至于",
    # 助词与语气词
    "吗", "呢", "吧", "啊", "哦", "嗯", "呀", "哇", "哈", "嘛", "哎", "唉",
    "得", "地", "之", "其", "所", "以", "若", "如", "且", "并", "并且", "而且",
    # 量词与副词
    "个", "只", "条", "本", "篇", "种", "类", "样", "些", "点", "下", "次",
    "很", "非常", "十分", "特别", "尤其", "格外", "相当", "比较", "颇", "挺",
    "更", "最", "极", "太", "过于", "稍微", "略", "几乎", "差不多", "大约",
    # 时间与方位
    "现在", "以前", "以后", "之前", "之后", "当时", "同时", "马上", "立刻",
    "里", "外", "中", "内", "旁", "前", "后", "左", "右", "上", "下",
    # 学术文本常见冗词
    "进行", "通过", "可以", "能够", "需要", "应该", "必须", "可能", "或者",
    "本文", "本研究", "本论文", "本工作", "本研究中", "如图", "如表", "所示",
    "根据", "按照", "依据", "基于", "鉴于", "由于", "出于",
}

# 默认情感词典（正面词与负面词）
POSITIVE_WORDS = {
    "好", "优秀", "卓越", "杰出", "出色", "突出", "显著", "明显", "成功", "有效",
    "高效", "快速", "准确", "精确", "正确", "完善", "完美", "完整", "全面", "充分",
    "稳定", "可靠", "可信", "可行", "可用", "实用", "先进", "创新", "新颖", "独特",
    "优势", "优点", "益处", "好处", "利益", "价值", "意义", "重要", "关键", "核心",
    "提升", "提高", "改善", "优化", "增强", "加强", "促进", "推动", "支持", "帮助",
    "满意", "满意", "喜欢", "赞同", "认可", "接受", "采纳", "推荐", "赞同",
    "突破", "进展", "成就", "成果", "收获", "胜利", "赢", "胜", "优", "良",
}

NEGATIVE_WORDS = {
    "差", "坏", "劣", "糟糕", "失败", "无效", "低效", "缓慢", "错误", "不准确",
    "不精确", "不正确", "缺陷", "缺点", "不足", "缺乏", "缺失", "不完整", "不全面",
    "不稳定", "不可靠", "不可信", "不可行", "不可用", "落后", "陈旧", "过时", "普通",
    "劣势", "弱点", "弊端", "问题", "困难", "障碍", "阻碍", "限制", "约束", "瓶颈",
    "下降", "降低", "恶化", "退化", "减弱", "削弱", "阻碍", "妨碍", "干扰", "破坏",
    "不满", "失望", "讨厌", "反对", "拒绝", "否定", "排斥", "拒绝", "批评", "指责",
    "错误", "失误", "偏差", "漏洞", "风险", "威胁", "危机", "灾难", "损失", "损害",
    "复杂", "繁琐", "困难", "艰难", "棘手", "麻烦", "混乱", "无序", "矛盾", "冲突",
}

# 程度副词（用于情感强度调节）
DEGREE_WORDS = {
    "极其": 2.0, "非常": 1.8, "十分": 1.8, "特别": 1.7, "尤其": 1.6, "格外": 1.6,
    "相当": 1.5, "比较": 1.3, "颇": 1.4, "挺": 1.3, "更": 1.4, "最": 2.0,
    "极": 2.0, "太": 1.8, "过于": 1.7, "稍微": 0.6, "略": 0.7, "几乎": 0.9,
    "差不多": 0.85, "大约": 0.8, "有些": 0.8, "有点": 0.7, "一点": 0.6,
}

# 否定词（用于情感极性反转）
NEGATION_WORDS = {
    "不", "没", "没有", "无", "非", "未", "别", "莫", "勿", "毋",
    "毫不", "并不", "并不", "从不", "从未", "绝非", "并不", "并不",
}

# 内置中文词典（常见学术词汇，用于分词与术语识别）
BUILTIN_DICTIONARY = {
    # 学科领域
    "计算机", "人工智能", "机器学习", "深度学习", "神经网络", "自然语言处理",
    "计算机视觉", "数据挖掘", "模式识别", "信号处理", "图像处理", "语音识别",
    "知识图谱", "强化学习", "迁移学习", "联邦学习", "监督学习", "无监督学习",
    "半监督学习", "自监督学习", "表示学习", "特征工程", "特征提取", "特征选择",
    "数学", "物理学", "化学", "生物学", "医学", "工程学", "经济学", "社会学",
    "心理学", "哲学", "文学", "历史学", "法学", "管理学", "教育学",
    # 方法与技术
    "算法", "模型", "框架", "架构", "系统", "平台", "工具", "方法", "技术",
    "理论", "假设", "定理", "公理", "推论", "证明", "推导", "计算", "仿真",
    "实验", "测试", "验证", "评估", "分析", "研究", "调查", "观察", "测量",
    "卷积神经网络", "循环神经网络", "生成对抗网络", "变换器", "注意力机制",
    "支持向量机", "决策树", "随机森林", "梯度提升", "贝叶斯网络", "马尔可夫",
    "梯度下降", "反向传播", "随机梯度下降", "批量归一化", "丢弃", "正则化",
    # 学术文本结构词
    "摘要", "引言", "绪论", "方法", "结果", "讨论", "结论", "参考文献",
    "致谢", "附录", "图表", "目录", "标题", "章节", "段落", "句子",
    "研究背景", "研究目的", "研究方法", "研究结果", "研究结论", "研究意义",
    "相关工作", "文献综述", "实验设计", "实验结果", "结果分析", "讨论分析",
    # 评价指标
    "准确率", "精确率", "召回率", "F1值", "准确度", "精度", "误差", "损失",
    "收敛", "发散", "过拟合", "欠拟合", "泛化", "鲁棒性", "稳定性", "可靠性",
    "有效性", "可行性", "可扩展性", "可解释性", "可复现性", "可维护性",
}

# 繁简转换映射表（简化版，包含常见繁简差异字）
TRADITIONAL_TO_SIMPLIFIED = {
    "國": "国", "學": "学", "業": "业", "東": "东", "南": "南", "北": "北",
    "西": "西", "電": "电", "車": "车", "馬": "马", "鳥": "鸟", "魚": "鱼",
    "蟲": "虫", "龍": "龙", "龜": "龟", "貝": "贝", "見": "见", "觀": "观",
    "論": "论", "語": "语", "說": "说", "話": "话", "請": "请", "謝": "谢",
    "謝": "谢", "謝": "谢", "開": "开", "關": "关", "門": "门", "窗": "窗",
    "書": "书", "畫": "画", "圖": "图", "圖": "图", "場": "场", "廠": "厂",
    "廣": "广", "慶": "庆", "縣": "县", "鄉": "乡", "銀": "银", "鐵": "铁",
    "銅": "铜", "金": "金", "錢": "钱", "鍾": "钟", "鍵": "键", "鍵": "键",
    "長": "长", "短": "短", "大": "大", "小": "小", "多": "多", "少": "少",
    "高": "高", "低": "低", "新": "新", "舊": "旧", "好": "好", "壞": "坏",
    "實": "实", "虛": "虚", "真": "真", "假": "假", "對": "对", "錯": "错",
    "與": "与", "或": "或", "及": "及", "和": "和", "同": "同", "異": "异",
    "時": "时", "間": "间", "日": "日", "月": "月", "年": "年", "歲": "岁",
    "點": "点", "線": "线", "面": "面", "體": "体", "形": "形", "狀": "状",
    "動": "动", "靜": "静", "快": "快", "慢": "慢", "強": "强", "弱": "弱",
    "進": "进", "退": "退", "上": "上", "下": "下", "內": "内", "外": "外",
    "來": "来", "去": "去", "前": "前", "後": "后", "左": "左", "右": "右",
    "個": "个", "們": "们", "這": "这", "那": "那", "哪": "哪", "什": "什",
    "麼": "么", "嗎": "吗", "呢": "呢", "吧": "吧", "啊": "啊", "哦": "哦",
    "應": "应", "當": "当", "然": "然", "雖": "虽", "但": "但", "是": "是",
    "為": "为", "以": "以", "於": "于", "由": "由", "從": "从", "向": "向",
    "機": "机", "器": "器", "物": "物", "質": "质", "量": "量", "數": "数",
    "據": "据", "資": "资", "料": "料", "訊": "讯", "息": "息", "號": "号",
    "碼": "码", "字": "字", "詞": "词", "句": "句", "段": "段", "篇": "篇",
    "章": "章", "節": "节", "卷": "卷", "冊": "册", "頁": "页", "行": "行",
    "計": "计", "算": "算", "測": "测", "量": "量", "評": "评", "估": "估",
    "驗": "验", "證": "证", "實": "实", "驗": "验", "結": "结", "果": "果",
    "論": "论", "文": "文", "題": "题", "目": "目", "綱": "纲", "要": "要",
    "點": "点", "線": "线", "圖": "图", "表": "表", "格": "格", "式": "式",
    "樣": "样", "本": "本", "件": "件", "項": "项", "目": "目", "條": "条",
    "類": "类", "種": "种", "型": "型", "號": "号", "碼": "码", "級": "级",
    "層": "层", "次": "次", "階": "阶", "段": "段", "步": "步", "驟": "骤",
    "過": "过", "程": "程", "序": "序", "流": "流", "向": "向", "路": "路",
    "徑": "径", "途": "途", "法": "法", "則": "则", "律": "律", "規": "规",
    "定": "定", "義": "义", "意": "意", "思": "思", "想": "想", "念": "念",
    "觀": "观", "點": "点", "見": "见", "解": "解", "釋": "释", "說": "说",
    "明": "明", "白": "白", "清": "清", "楚": "楚", "詳": "详", "細": "细",
    "簡": "简", "略": "略", "繁": "繁", "雜": "杂", "複": "复", "雜": "杂",
    "難": "难", "易": "易", "簡": "简", "單": "单", "複": "复", "雜": "杂",
    "習": "习", "華": "华", "聯": "联", "網": "网", "絡": "络", "資": "资",
    "訊": "讯", "術": "术", "構": "构", "構": "构", "產": "产", "業": "业",
    "場": "场", "員": "员", "區": "区", "動": "动", "態": "态", "環": "环",
    "境": "境", "營": "营", "運": "运", "系": "系", "統": "统", "節": "节",
    "點": "点", "線": "线", "號": "号", "碼": "码", "詞": "词", "計": "计",
}

# 全角到半角映射（除 ASCII 范围外）
FULLWIDTH_TO_HALFWIDTH = {}
for _i in range(0xFF01, 0xFF5E + 1):
    FULLWIDTH_TO_HALFWIDTH[chr(_i)] = chr(_i - 0xFEE0)
# 全角空格单独处理
FULLWIDTH_TO_HALFWIDTH["\u3000"] = " "

# 命名实体识别词典（简化版）
# 人名姓氏（常见中文姓氏）
COMMON_SURNAMES = {
    "赵", "钱", "孙", "李", "周", "吴", "郑", "王", "冯", "陈", "褚", "卫", "蒋",
    "沈", "韩", "杨", "朱", "秦", "尤", "许", "何", "吕", "施", "张", "孔", "曹",
    "严", "华", "金", "魏", "陶", "姜", "戚", "谢", "邹", "喻", "柏", "水", "窦",
    "章", "云", "苏", "潘", "葛", "奚", "范", "彭", "郎", "鲁", "韦", "昌", "马",
    "苗", "凤", "花", "方", "俞", "任", "袁", "柳", "酆", "鲍", "史", "唐", "费",
    "廉", "岑", "薛", "雷", "贺", "倪", "汤", "滕", "殷", "罗", "毕", "郝", "邬",
    "安", "常", "乐", "于", "时", "傅", "皮", "卞", "齐", "康", "伍", "余", "元",
    "卜", "顾", "孟", "平", "黄", "和", "穆", "萧", "尹", "姚", "邵", "湛", "汪",
    "祁", "毛", "禹", "狄", "米", "贝", "明", "臧", "计", "伏", "成", "戴", "谈",
    "宋", "茅", "庞", "熊", "纪", "舒", "屈", "项", "祝", "董", "梁", "杜", "阮",
    "蓝", "闵", "席", "季", "麻", "强", "贾", "路", "娄", "危", "江", "童", "颜",
    "郭", "梅", "盛", "林", "刁", "钟", "徐", "邱", "骆", "高", "夏", "蔡", "田",
    "樊", "胡", "凌", "霍", "虞", "万", "支", "柯", "昝", "管", "卢", "莫", "经",
    "房", "裘", "缪", "干", "解", "应", "宗", "丁", "宣", "贲", "邓", "郁", "单",
    "杭", "洪", "包", "诸", "左", "石", "崔", "吉", "钮", "龚", "程", "嵇", "邢",
    "滑", "裴", "陆", "荣", "翁", "荀", "羊", "於", "惠", "甄", "麴", "家", "封",
    "芮", "羿", "储", "靳", "汲", "邴", "糜", "松", "井", "段", "富", "巫", "乌",
    "焦", "巴", "弓", "牧", "隗", "山", "谷", "车", "侯", "宓", "蓬", "全", "郗",
    "班", "仰", "秋", "仲", "伊", "宫", "宁", "仇", "栾", "暴", "甘", "钭", "厉",
    "戎", "祖", "武", "符", "刘", "景", "詹", "束", "龙", "叶", "幸", "司", "韶",
    "郜", "黎", "蓟", "薄", "印", "宿", "白", "怀", "蒲", "邰", "从", "鄂", "索",
    "咸", "籍", "赖", "卓", "蔺", "屠", "蒙", "池", "乔", "阴", "鬱", "胥", "能",
    "苍", "双", "闻", "莘", "党", "翟", "谭", "贡", "劳", "逄", "姬", "申", "扶",
    "堵", "冉", "宰", "郦", "雍", "却", "璩", "桑", "桂", "濮", "牛", "寿", "通",
    "边", "扈", "燕", "冀", "郏", "浦", "尚", "农", "温", "别", "庄", "晏", "柴",
    "瞿", "阎", "充", "慕", "连", "茹", "习", "宦", "艾", "鱼", "容", "向", "古",
    "易", "慎", "戈", "廖", "庾", "终", "暨", "居", "衡", "步", "都", "耿", "满",
    "弘", "匡", "国", "文", "寇", "广", "禄", "阙", "东", "欧", "殳", "沃", "利",
    "蔚", "越", "夔", "隆", "师", "巩", "厍", "聂", "晁", "勾", "敖", "融", "冷",
    "訾", "辛", "阚", "那", "简", "饶", "空", "曾", "毋", "沙", "乜", "养", "鞠",
    "须", "丰", "巢", "关", "蒯", "相", "查", "后", "荆", "红", "游", "竺", "权",
    "逯", "盖", "益", "桓", "公", "欧阳", "司马", "诸葛", "上官", "夏侯", "闻人",
}

# 常见地名关键词
PLACE_KEYWORDS = {
    "中国", "北京", "上海", "广州", "深圳", "杭州", "南京", "武汉", "成都", "重庆",
    "天津", "苏州", "西安", "长沙", "沈阳", "青岛", "郑州", "大连", "东莞", "宁波",
    "厦门", "福州", "无锡", "合肥", "昆明", "哈尔滨", "济南", "佛山", "长春", "温州",
    "石家庄", "南宁", "常州", "泉州", "南昌", "贵阳", "太原", "烟台", "嘉兴", "南通",
    "金华", "珠海", "惠州", "徐州", "海口", "乌鲁木齐", "绍兴", "中山", "台州", "兰州",
    "亚洲", "欧洲", "美洲", "非洲", "大洋洲", "北美", "南美", "东亚", "西亚", "南亚",
    "美国", "英国", "法国", "德国", "日本", "韩国", "俄罗斯", "加拿大", "澳大利亚",
    "印度", "巴西", "意大利", "西班牙", "荷兰", "瑞典", "瑞士", "挪威", "芬兰",
}

# 常见机构关键词
ORG_KEYWORDS = {
    "大学", "学院", "研究所", "研究院", "实验室", "研究中心", "学院", "学校",
    "公司", "集团", "有限", "股份", "科技", "技术", "工业", "实业", "控股",
    "科学院", "工程院", "社会科学院", "科学院", "研究院", "研究中心", "实验室",
    "医院", "中心", "部门", "局", "厅", "处", "科", "室", "部", "委", "办",
    "委员会", "联合会", "协会", "学会", "基金会", "组织", "机构", "团体",
}

# 学术术语后缀（用于术语边界识别）
TERM_SUFFIXES = {
    "方法", "算法", "模型", "理论", "技术", "系统", "框架", "架构", "机制",
    "策略", "方案", "协议", "标准", "规范", "准则", "原则", "定律", "定理",
    "效应", "现象", "过程", "流程", "阶段", "步骤", "操作", "动作", "行为",
    "结构", "组织", "形态", "形式", "类型", "种类", "类别", "分类", "分级",
    "指标", "参数", "变量", "常量", "系数", "因子", "因素", "元素", "成分",
    "网络", "图", "树", "矩阵", "向量", "张量", "序列", "集合", "空间",
    "函数", "方程", "公式", "表达式", "算子", "变换", "映射", "关系",
}


# ===== 数据类定义 =====

@dataclass
class Token:
    """词法单元。

    Attributes:
        text: 词元文本。
        pos: 词性标签。
        offset: 在原文中的字符偏移。
        length: 词元长度。
        is_chinese: 是否为中文词元。
        is_stopword: 是否为停用词。
        entity_type: 命名实体类型（若有）。
    """
    text: str
    pos: str = "x"
    offset: int = 0
    length: int = 0
    is_chinese: bool = False
    is_stopword: bool = False
    entity_type: Optional[str] = None

    def __post_init__(self) -> None:
        if self.length == 0:
            self.length = len(self.text)
        if self.is_chinese is False:
            self.is_chinese = bool(CJK_PATTERN.search(self.text))


@dataclass
class Sentence:
    """句子。

    Attributes:
        text: 句子文本。
        start: 在原文中的起始偏移。
        end: 在原文中的结束偏移。
        tokens: 句子的词元列表。
    """
    text: str
    start: int = 0
    end: int = 0
    tokens: List[Token] = field(default_factory=list)


@dataclass
class Paragraph:
    """段落。

    Attributes:
        text: 段落文本。
        start: 在原文中的起始偏移。
        end: 在原文中的结束偏移。
        sentences: 段落包含的句子列表。
    """
    text: str
    start: int = 0
    end: int = 0
    sentences: List[Sentence] = field(default_factory=list)


@dataclass
class Entity:
    """命名实体。

    Attributes:
        text: 实体文本。
        entity_type: 实体类型（PERSON/LOCATION/ORGANIZATION/TERM/TIME/NUMBER）。
        start: 起始偏移。
        end: 结束偏移。
        confidence: 置信度（0-1）。
    """
    text: str
    entity_type: str
    start: int = 0
    end: int = 0
    confidence: float = 1.0


@dataclass
class Keyword:
    """关键词。

    Attributes:
        text: 关键词文本。
        score: 关键词权重分数。
        frequency: 出现频次。
        pos: 词性。
    """
    text: str
    score: float = 0.0
    frequency: int = 0
    pos: str = "n"


@dataclass
class SentimentResult:
    """情感分析结果。

    Attributes:
        score: 情感分数（-1 到 1，负为负面，正为正面）。
        label: 情感标签（positive/negative/neutral）。
        positive_count: 正面词计数。
        negative_count: 负面词计数。
        confidence: 置信度。
    """
    score: float = 0.0
    label: str = "neutral"
    positive_count: int = 0
    negative_count: int = 0
    confidence: float = 0.0


@dataclass
class FormulaInfo:
    """公式信息。

    Attributes:
        text: 公式文本。
        formula_type: 公式类型（inline/block/latex）。
        start: 起始偏移。
        end: 结束偏移。
    """
    text: str
    formula_type: str = "inline"
    start: int = 0
    end: int = 0


@dataclass
class CitationInfo:
    """引用信息。

    Attributes:
        text: 引用文本。
        citation_type: 引用类型（numeric/author_year/chinese）。
        start: 起始偏移。
        end: 结束偏移。
        ref_id: 解析出的引用编号或标识。
    """
    text: str
    citation_type: str = "numeric"
    start: int = 0
    end: int = 0
    ref_id: Optional[str] = None


# ===== 工具函数 =====

def _is_cjk_char(ch: str) -> bool:
    """判断单个字符是否为 CJK 汉字。

    Args:
        ch: 待判断的字符。

    Returns:
        若为 CJK 汉字返回 True，否则返回 False。
    """
    if not ch:
        return False
    code = ord(ch)
    for start, end in CJK_RANGES:
        if start <= code <= end:
            return True
    return False


def _is_chinese_punct(ch: str) -> bool:
    """判断字符是否为中文标点。"""
    return ch in CHINESE_PUNCTUATIONS


def _is_punct(ch: str) -> bool:
    """判断字符是否为标点（中英文）。"""
    return ch in CHINESE_PUNCTUATIONS or ch in ENGLISH_PUNCTUATIONS


def _is_letter(ch: str) -> bool:
    """判断字符是否为字母（中英文）。"""
    return _is_cjk_char(ch) or ch.isalpha()


def _is_digit(ch: str) -> bool:
    """判断字符是否为数字。"""
    return ch.isdigit() or ch in "零一二三四五六七八九十百千万亿"


def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为 float。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _now_ts() -> float:
    """获取当前时间戳。"""
    import time
    return time.time()


# ===== 主类：中文文本处理器 =====

class ChineseProcessor:
    """中文文本处理器。

    提供完整的中文文本处理能力，包括分词、词性标注、命名实体识别、
    句子分割、段落识别、关键词提取、摘要生成、情感分析、术语/公式/引用识别、
    文本去重与相似度计算。

    线程安全说明：本类为无状态处理器，可在多线程环境共享实例。
    若需自定义词典或停用词，建议为每个线程创建独立实例。

    Attributes:
        stopwords: 停用词集合。
        dictionary: 自定义词典集合。
        use_jieba: 是否使用 jieba 分词。
    """

    # 单例实例
    _instance: Optional["ChineseProcessor"] = None

    def __init__(
        self,
        stopwords: Optional[Set[str]] = None,
        dictionary: Optional[Set[str]] = None,
        use_jieba: bool = True,
    ) -> None:
        """初始化中文处理器。

        Args:
            stopwords: 自定义停用词集合，为 None 时使用默认停用词。
            dictionary: 自定义词典集合，为 None 时使用内置词典。
            use_jieba: 是否优先使用 jieba 分词（若可用）。
        """
        # 停用词集合
        self.stopwords: Set[str] = set(stopwords) if stopwords else set(DEFAULT_STOPWORDS)
        # 词典集合（用于双向最大匹配分词）
        self.dictionary: Set[str] = set(dictionary) if dictionary else set(BUILTIN_DICTIONARY)
        # 将地名、机构、姓氏加入词典，确保分词时能识别这些词
        self.dictionary.update(PLACE_KEYWORDS)
        self.dictionary.update(ORG_KEYWORDS)
        # 是否使用 jieba
        self.use_jieba: bool = use_jieba and _HAS_JIEBA
        # 情感词典
        self.positive_words: Set[str] = set(POSITIVE_WORDS)
        self.negative_words: Set[str] = set(NEGATIVE_WORDS)
        # 程度副词与否定词
        self.degree_words: Dict[str, float] = dict(DEGREE_WORDS)
        self.negation_words: Set[str] = set(NEGATION_WORDS)
        # 繁简转换表
        self.t2s_table: Dict[str, str] = dict(TRADITIONAL_TO_SIMPLIFIED)
        # 全半角转换表
        self.f2h_table: Dict[str, str] = dict(FULLWIDTH_TO_HALFWIDTH)
        # 姓氏、地名、机构词典（用于 NER）
        self.surnames: Set[str] = set(COMMON_SURNAMES)
        self.place_keywords: Set[str] = set(PLACE_KEYWORDS)
        self.org_keywords: Set[str] = set(ORG_KEYWORDS)
        self.term_suffixes: Set[str] = set(TERM_SUFFIXES)
        # 最大词典词长（用于最大匹配分词）
        self._max_word_len: int = max((len(w) for w in self.dictionary), default=8)
        # 若使用 jieba，将自定义词典加入
        if self.use_jieba and self.dictionary:
            for word in self.dictionary:
                try:
                    jieba.add_word(word)  # type: ignore
                except Exception:  # pragma: no cover
                    pass
        _logger.debug(
            "ChineseProcessor 初始化完成，词典大小=%d，停用词=%d，use_jieba=%s",
            len(self.dictionary), len(self.stopwords), self.use_jieba,
        )

    @classmethod
    def get_instance(cls) -> "ChineseProcessor":
        """获取全局单例实例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ===== 文本归一化 =====

    def normalize(
        self,
        text: str,
        to_simplified: bool = True,
        to_halfwidth: bool = True,
        trim: bool = True,
    ) -> str:
        """文本归一化处理。

        依次执行：Unicode NFC 归一化、繁简转换、全半角转换、空白符规整。

        Args:
            text: 原始文本。
            to_simplified: 是否繁转简。
            to_halfwidth: 是否全角转半角（仅针对 ASCII 范围）。
            trim: 是否去除首尾空白。

        Returns:
            归一化后的文本。
        """
        if not text:
            return ""
        # Unicode NFC 归一化
        result = unicodedata.normalize("NFC", text)
        # 全角转半角
        if to_halfwidth:
            result = "".join(self.f2h_table.get(ch, ch) for ch in result)
        # 繁转简
        if to_simplified:
            result = "".join(self.t2s_table.get(ch, ch) for ch in result)
        # 空白符规整：连续空白压缩为单个空格（保留换行）
        result = re.sub(r"[^\S\n]+", " ", result)
        # 多个连续换行压缩为两个
        result = re.sub(r"\n{3,}", "\n\n", result)
        # 去除首尾空白
        if trim:
            result = result.strip()
        return result

    def traditional_to_simplified(self, text: str) -> str:
        """繁体转简体。

        Args:
            text: 繁体文本。

        Returns:
            简体文本。
        """
        if not text:
            return ""
        return "".join(self.t2s_table.get(ch, ch) for ch in text)

    def simplified_to_traditional(self, text: str) -> str:
        """简体转繁体（基于反向映射表）。

        Args:
            text: 简体文本。

        Returns:
            繁体文本。
        """
        if not text:
            return ""
        # 构建反向映射（懒加载）
        if not hasattr(self, "_s2t_table"):
            self._s2t_table: Dict[str, str] = {v: k for k, v in self.t2s_table.items()}
        return "".join(self._s2t_table.get(ch, ch) for ch in text)

    def fullwidth_to_halfwidth(self, text: str) -> str:
        """全角转半角。

        Args:
            text: 含全角字符的文本。

        Returns:
            半角文本。
        """
        if not text:
            return ""
        return "".join(self.f2h_table.get(ch, ch) for ch in text)

    def halfwidth_to_fullwidth(self, text: str) -> str:
        """半角转全角（仅针对 ASCII 可打印字符）。

        Args:
            text: 半角文本。

        Returns:
            含全角字符的文本。
        """
        if not text:
            return ""
        result_chars: List[str] = []
        for ch in text:
            code = ord(ch)
            if 0x21 <= code <= 0x7E:
                result_chars.append(chr(code + 0xFEE0))
            elif ch == " ":
                result_chars.append("\u3000")
            else:
                result_chars.append(ch)
        return "".join(result_chars)

    # ===== 分词 =====

    def tokenize(
        self,
        text: str,
        with_pos: bool = False,
        with_offset: bool = False,
    ) -> List[Token]:
        """中文分词。

        优先使用 jieba 分词（若可用），否则降级为双向最大匹配算法。
        支持中英文混合文本：中文按词切分，英文按单词切分，数字单独切分。

        Args:
            text: 待分词文本。
            with_pos: 是否同时进行词性标注。
            with_offset: 是否计算词元在原文中的偏移。

        Returns:
            词元列表。
        """
        if not text:
            return []
        tokens: List[Token] = []
        if self.use_jieba:
            tokens = self._tokenize_jieba(text, with_pos, with_offset)
        else:
            tokens = self._tokenize_bidirectional(text, with_pos, with_offset)
        # 标记停用词
        for token in tokens:
            token.is_stopword = token.text in self.stopwords
        return tokens

    def _tokenize_jieba(
        self,
        text: str,
        with_pos: bool,
        with_offset: bool,
    ) -> List[Token]:
        """使用 jieba 进行分词。"""
        tokens: List[Token] = []
        if with_pos and pseg is not None:
            # 带词性标注
            offset = 0
            for word, flag in pseg.cut(text):  # type: ignore
                if not word:
                    continue
                tok = Token(
                    text=word,
                    pos=flag or "x",
                    offset=offset if with_offset else 0,
                )
                tokens.append(tok)
                if with_offset:
                    offset += len(word)
        else:
            # 不带词性标注
            offset = 0
            for word in jieba.cut(text):  # type: ignore
                if not word:
                    continue
                tok = Token(
                    text=word,
                    pos="n",
                    offset=offset if with_offset else 0,
                )
                tokens.append(tok)
                if with_offset:
                    offset += len(word)
        return tokens

    def _tokenize_bidirectional(
        self,
        text: str,
        with_pos: bool,
        with_offset: bool,
    ) -> List[Token]:
        """双向最大匹配分词（jieba 不可用时的降级方案）。

        结合正向最大匹配（FMM）与逆向最大匹配（BMM），选择切分结果中
        单字词较少、词数较少的方向作为最终结果。
        """
        # 先按中英文边界切分为片段
        segments = self._split_by_script(text)
        tokens: List[Token] = []
        offset = 0
        for seg_text, seg_type in segments:
            if seg_type == "chinese":
                # 中文：双向最大匹配
                seg_tokens = self._bidirectional_match(seg_text)
                for w in seg_tokens:
                    tok = Token(
                        text=w,
                        pos=self._guess_pos(w) if with_pos else "n",
                        offset=offset if with_offset else 0,
                        is_chinese=True,
                    )
                    tokens.append(tok)
                    if with_offset:
                        offset += len(w)
            elif seg_type == "english":
                # 英文：按单词切分
                for m in ENGLISH_WORD_PATTERN.finditer(seg_text):
                    w = m.group()
                    tok = Token(
                        text=w,
                        pos="eng" if with_pos else "n",
                        offset=offset + m.start() if with_offset else 0,
                        is_chinese=False,
                    )
                    tokens.append(tok)
                if with_offset:
                    offset += len(seg_text)
            elif seg_type == "number":
                # 数字：整体作为一个词元
                tok = Token(
                    text=seg_text,
                    pos="m" if with_pos else "n",
                    offset=offset if with_offset else 0,
                    is_chinese=False,
                )
                tokens.append(tok)
                if with_offset:
                    offset += len(seg_text)
            else:
                # 标点或空白：跳过（但保留偏移）
                if with_offset:
                    offset += len(seg_text)
        return tokens

    def _split_by_script(self, text: str) -> List[Tuple[str, str]]:
        """按文字系统切分文本片段。

        将文本切分为连续的中文、英文、数字、标点片段。

        Returns:
            (片段文本, 片段类型) 列表，类型为 chinese/english/number/punct/space。
        """
        segments: List[Tuple[str, str]] = []
        if not text:
            return segments
        current_chars: List[str] = []
        current_type = ""
        for ch in text:
            ch_type = self._char_type(ch)
            if ch_type != current_type and current_chars:
                segments.append(("".join(current_chars), current_type))
                current_chars = []
            current_chars.append(ch)
            current_type = ch_type
        if current_chars:
            segments.append(("".join(current_chars), current_type))
        return segments

    def _char_type(self, ch: str) -> str:
        """判断字符类型。"""
        if _is_cjk_char(ch):
            return "chinese"
        if ch.isalpha():
            return "english"
        if ch.isdigit():
            return "number"
        if ch.isspace():
            return "space"
        return "punct"

    def _bidirectional_match(self, text: str) -> List[str]:
        """双向最大匹配分词。

        Args:
            text: 纯中文文本片段。

        Returns:
            切分后的词列表。
        """
        if not text:
            return []
        fmm_result = self._forward_max_match(text)
        bmm_result = self._backward_max_match(text)
        # 选择单字词较少的结果
        fmm_single = sum(1 for w in fmm_result if len(w) == 1)
        bmm_single = sum(1 for w in bmm_result if len(w) == 1)
        if fmm_single < bmm_single:
            return fmm_result
        elif bmm_single < fmm_single:
            return bmm_result
        # 单字词数相同时，选择词数较少的
        if len(fmm_result) <= len(bmm_result):
            return fmm_result
        return bmm_result

    def _forward_max_match(self, text: str) -> List[str]:
        """正向最大匹配（FMM）。"""
        result: List[str] = []
        i = 0
        n = len(text)
        while i < n:
            # 从最大词长开始尝试
            matched = False
            max_len = min(self._max_word_len, n - i)
            for length in range(max_len, 1, -1):
                word = text[i:i + length]
                if word in self.dictionary:
                    result.append(word)
                    i += length
                    matched = True
                    break
            if not matched:
                # 单字作为独立词
                result.append(text[i])
                i += 1
        return result

    def _backward_max_match(self, text: str) -> List[str]:
        """逆向最大匹配（BMM）。"""
        result: List[str] = []
        n = len(text)
        i = n
        while i > 0:
            matched = False
            max_len = min(self._max_word_len, i)
            for length in range(max_len, 1, -1):
                word = text[i - length:i]
                if word in self.dictionary:
                    result.append(word)
                    i -= length
                    matched = True
                    break
            if not matched:
                result.append(text[i - 1])
                i -= 1
        # 逆向结果需要反转
        result.reverse()
        return result

    def _guess_pos(self, word: str) -> str:
        """基于规则的词性猜测（jieba 不可用时使用）。"""
        if not word:
            return "x"
        if word in self.term_suffixes:
            return "n"
        if word.isdigit():
            return "m"
        if word in CHINESE_PUNCTUATIONS:
            return "w"
        if ENGLISH_WORD_PATTERN.fullmatch(word):
            return "eng"
        if word in self.surnames:
            return "nr"
        if word in self.place_keywords:
            return "ns"
        if word in self.org_keywords:
            return "nt"
        if word in self.dictionary:
            return "n"
        return "n"

    # ===== 词性标注 =====

    def pos_tag(self, tokens: List[Token]) -> List[Token]:
        """词性标注。

        若分词时未进行词性标注，可调用此方法补充标注。

        Args:
            tokens: 词元列表。

        Returns:
            带词性标注的词元列表（原地修改）。
        """
        for token in tokens:
            if token.pos in ("x", "n", ""):
                token.pos = self._guess_pos(token.text)
        return tokens

    # ===== 命名实体识别 =====

    def ner(self, text: str) -> List[Entity]:
        """命名实体识别。

        基于词典与规则识别人名、地名、机构、术语、时间、数字等实体。

        Args:
            text: 待识别文本。

        Returns:
            实体列表。
        """
        if not text:
            return []
        entities: List[Entity] = []
        # 先分词
        tokens = self.tokenize(text, with_pos=True, with_offset=True)
        # 基于词性与词典识别
        i = 0
        while i < len(tokens):
            token = tokens[i]
            # 人名识别：姓氏 + 1-2 个汉字
            if token.text in self.surnames and i + 1 < len(tokens):
                next_tok = tokens[i + 1]
                if (next_tok.is_chinese and len(next_tok.text) <= 2
                        and next_tok.text not in self.stopwords
                        and next_tok.pos not in ("w", "m")):
                    name = token.text + next_tok.text
                    start = token.offset
                    end = next_tok.offset + next_tok.length
                    entities.append(Entity(
                        text=name, entity_type="PERSON",
                        start=start, end=end, confidence=0.7,
                    ))
                    i += 2
                    continue
            # 地名识别
            if token.text in self.place_keywords:
                entities.append(Entity(
                    text=token.text, entity_type="LOCATION",
                    start=token.offset, end=token.offset + token.length,
                    confidence=0.9,
                ))
                i += 1
                continue
            # 机构识别：包含机构关键词的多词组合
            if token.text in self.org_keywords:
                # 向前回溯组合机构名
                j = i - 1
                org_parts: List[str] = [token.text]
                org_start = token.offset
                while j >= 0:
                    prev = tokens[j]
                    if (prev.is_chinese and prev.text not in self.stopwords
                            and prev.pos not in ("w",)):
                        org_parts.insert(0, prev.text)
                        org_start = prev.offset
                        j -= 1
                    else:
                        break
                    if len(org_parts) >= 5:  # 限制最大长度
                        break
                org_text = "".join(org_parts)
                if len(org_text) >= 3:
                    entities.append(Entity(
                        text=org_text, entity_type="ORGANIZATION",
                        start=org_start,
                        end=token.offset + token.length,
                        confidence=0.75,
                    ))
                i += 1
                continue
            # 时间识别（年份、日期）
            time_match = re.match(r"^\d{4}年$", token.text)
            if time_match:
                entities.append(Entity(
                    text=token.text, entity_type="TIME",
                    start=token.offset, end=token.offset + token.length,
                    confidence=0.95,
                ))
                i += 1
                continue
            # 数字识别
            if token.pos == "m" or token.text.isdigit():
                entities.append(Entity(
                    text=token.text, entity_type="NUMBER",
                    start=token.offset, end=token.offset + token.length,
                    confidence=0.95,
                ))
                i += 1
                continue
            # 术语识别：以术语后缀结尾的多字词
            if (token.is_chinese and len(token.text) >= 3
                    and any(token.text.endswith(suffix) for suffix in self.term_suffixes)):
                entities.append(Entity(
                    text=token.text, entity_type="TERM",
                    start=token.offset, end=token.offset + token.length,
                    confidence=0.7,
                ))
                i += 1
                continue
            i += 1
        # 基于正则补充识别时间与数字
        for pattern, etype in [
            (re.compile(r"\d{4}年\d{1,2}月\d{1,2}日"), "TIME"),
            (re.compile(r"\d{4}年\d{1,2}月"), "TIME"),
            (re.compile(r"\d{1,2}:\d{2}:\d{2}"), "TIME"),
            (re.compile(r"\d+(?:\.\d+)?%"), "NUMBER"),
            (re.compile(r"\d+(?:\.\d+)?(?:万|亿|千|百)?(?:元|个|条|篇|次)"), "NUMBER"),
        ]:
            for m in pattern.finditer(text):
                # 避免重复
                if not any(e.start == m.start() for e in entities):
                    entities.append(Entity(
                        text=m.group(), entity_type=etype,
                        start=m.start(), end=m.end(), confidence=0.95,
                    ))
        # 按位置排序
        entities.sort(key=lambda e: e.start)
        return entities

    # ===== 句子分割 =====

    def split_sentences(
        self,
        text: str,
        keep_punct: bool = True,
        min_length: int = 2,
    ) -> List[Sentence]:
        """中文句子分割。

        按中文句号、问号、叹号、分号、换行符进行切分，同时处理缩写与
        小数点等边界情况。

        Args:
            text: 待分割文本。
            keep_punct: 是否保留句子结束符。
            min_length: 最小句子长度（字符数），过短的片段合并到前一句。

        Returns:
            句子列表。
        """
        if not text:
            return []
        sentences: List[Sentence] = []
        current_start = 0
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch in SENTENCE_ENDINGS:
                # 找到句子结束符
                end = i + 1
                # 处理连续结束符（如 ！！！）
                while end < n and text[end] in SENTENCE_ENDINGS:
                    end += 1
                sent_text = text[current_start:end]
                if keep_punct or len(sent_text.rstrip("".join(set(SENTENCE_ENDINGS)))) > 0:
                    if sent_text.strip():
                        sentences.append(Sentence(
                            text=sent_text.strip(),
                            start=current_start,
                            end=end,
                        ))
                current_start = end
                i = end
            else:
                i += 1
        # 处理最后一段
        if current_start < n:
            sent_text = text[current_start:].strip()
            if sent_text:
                sentences.append(Sentence(
                    text=sent_text,
                    start=current_start,
                    end=n,
                ))
        # 合并过短句子
        if min_length > 0 and len(sentences) > 1:
            merged: List[Sentence] = []
            for sent in sentences:
                if merged and len(sent.text) < min_length:
                    # 合并到前一句
                    prev = merged[-1]
                    prev.text = prev.text + sent.text
                    prev.end = sent.end
                else:
                    merged.append(sent)
            sentences = merged
        # 为每个句子分词
        for sent in sentences:
            sent.tokens = self.tokenize(sent.text, with_pos=True)
        return sentences

    # ===== 段落识别 =====

    def split_paragraphs(
        self,
        text: str,
        min_length: int = 10,
    ) -> List[Paragraph]:
        """段落识别。

        按空行（连续换行）切分段落，同时支持按缩进识别段落。

        Args:
            text: 待分割文本。
            min_length: 最小段落长度。

        Returns:
            段落列表。
        """
        if not text:
            return []
        # 按连续换行切分
        raw_paragraphs = re.split(r"\n\s*\n", text)
        paragraphs: List[Paragraph] = []
        offset = 0
        for raw in raw_paragraphs:
            raw_stripped = raw.strip()
            if not raw_stripped:
                offset += len(raw) + 2  # 估算空行长度
                continue
            # 找到在原文中的实际位置
            start = text.find(raw_stripped, offset)
            if start < 0:
                start = offset
            end = start + len(raw_stripped)
            if len(raw_stripped) >= min_length:
                para = Paragraph(
                    text=raw_stripped,
                    start=start,
                    end=end,
                )
                para.sentences = self.split_sentences(raw_stripped)
                paragraphs.append(para)
            offset = end
        return paragraphs

    # ===== 关键词提取 =====

    def extract_keywords(
        self,
        text: str,
        top_k: int = 10,
        method: str = "tfidf",
        min_length: int = 2,
        remove_stopwords: bool = True,
    ) -> List[Keyword]:
        """中文关键词提取。

        支持两种方法：
            - tfidf: 基于 TF-IDF 的频率统计方法
            - textrank: 基于 TextRank 的图排序方法

        Args:
            text: 待提取文本。
            top_k: 返回的关键词数量。
            method: 提取方法，"tfidf" 或 "textrank"。
            min_length: 关键词最小长度。
            remove_stopwords: 是否去除停用词。

        Returns:
            关键词列表，按权重降序排列。
        """
        if not text:
            return []
        if method.lower() == "textrank":
            return self._keywords_textrank(text, top_k, min_length, remove_stopwords)
        return self._keywords_tfidf(text, top_k, min_length, remove_stopwords)

    def _keywords_tfidf(
        self,
        text: str,
        top_k: int,
        min_length: int,
        remove_stopwords: bool,
    ) -> List[Keyword]:
        """基于 TF-IDF 的关键词提取。"""
        tokens = self.tokenize(text, with_pos=True)
        # 过滤
        candidate_tokens = [
            t for t in tokens
            if len(t.text) >= min_length
            and not (remove_stopwords and t.is_stopword)
            and t.pos not in ("w", "x", "m", "p", "u", "c")
            and not _is_punct(t.text[0])
        ]
        if not candidate_tokens:
            # 降级：使用所有非停用词词元
            candidate_tokens = [
                t for t in tokens
                if not (remove_stopwords and t.is_stopword)
                and not _is_punct(t.text[0])
            ]
        if not candidate_tokens:
            return []
        # 计算词频
        word_freq: Counter = Counter(t.text for t in candidate_tokens)
        total = sum(word_freq.values())
        # 计算 TF
        tf: Dict[str, float] = {w: c / total for w, c in word_freq.items()}
        # 计算 IDF（使用内置文档频率近似）
        idf: Dict[str, float] = {}
        for word in word_freq:
            # 简化 IDF：词典中的词 IDF 较低，未登录词 IDF 较高
            if word in self.dictionary:
                idf[word] = math.log(10.0 / 1.0 + 1)  # 词典词
            else:
                idf[word] = math.log(10.0 / 0.1 + 1)  # 未登录词
        # 计算 TF-IDF
        scores: Dict[str, float] = {
            w: tf[w] * idf[w] for w in word_freq
        }
        # 排序
        sorted_words = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        # 构造结果
        keywords: List[Keyword] = []
        for word, score in sorted_words[:top_k]:
            pos = "n"
            for t in candidate_tokens:
                if t.text == word:
                    pos = t.pos
                    break
            keywords.append(Keyword(
                text=word, score=score,
                frequency=word_freq[word], pos=pos,
            ))
        return keywords

    def _keywords_textrank(
        self,
        text: str,
        top_k: int,
        min_length: int,
        remove_stopwords: bool,
    ) -> List[Keyword]:
        """基于 TextRank 的关键词提取。

        构建词共现图（窗口大小为 5），使用 PageRank 迭代计算节点权重。
        """
        tokens = self.tokenize(text, with_pos=True)
        # 过滤
        candidate_tokens = [
            t for t in tokens
            if len(t.text) >= min_length
            and not (remove_stopwords and t.is_stopword)
            and t.pos not in ("w", "x", "m", "p", "u", "c")
            and not _is_punct(t.text[0])
        ]
        if not candidate_tokens:
            candidate_tokens = [
                t for t in tokens
                if not (remove_stopwords and t.is_stopword)
                and not _is_punct(t.text[0])
            ]
        if not candidate_tokens:
            return []
        # 构建共现图
        window_size = 5
        word_set: Set[str] = {t.text for t in candidate_tokens}
        word_list = list(word_set)
        word_index: Dict[str, int] = {w: i for i, w in enumerate(word_list)}
        n = len(word_list)
        # 邻接矩阵（使用字典稀疏存储）
        graph: Dict[int, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
        token_texts = [t.text for t in candidate_tokens]
        for i in range(len(token_texts)):
            for j in range(i + 1, min(i + window_size, len(token_texts))):
                w1, w2 = token_texts[i], token_texts[j]
                if w1 != w2:
                    idx1, idx2 = word_index[w1], word_index[w2]
                    graph[idx1][idx2] += 1.0
                    graph[idx2][idx1] += 1.0
        # PageRank 迭代
        d = 0.85  # 阻尼系数
        scores = {i: 1.0 for i in range(n)}
        iterations = 50
        for _ in range(iterations):
            new_scores: Dict[int, float] = {}
            for i in range(n):
                in_sum = 0.0
                for j, weight in graph.get(i, {}).items():
                    out_weight_sum = sum(graph[j].values())
                    if out_weight_sum > 0:
                        in_sum += (weight / out_weight_sum) * scores[j]
                new_scores[i] = (1 - d) / n + d * in_sum
            # 检查收敛
            diff = sum(abs(new_scores[i] - scores[i]) for i in range(n))
            scores = new_scores
            if diff < 1e-6:
                break
        # 排序
        word_scores = [(word_list[i], scores[i]) for i in range(n)]
        word_scores.sort(key=lambda x: x[1], reverse=True)
        # 词频统计
        word_freq: Counter = Counter(token_texts)
        # 构造结果
        keywords: List[Keyword] = []
        for word, score in word_scores[:top_k]:
            pos = "n"
            for t in candidate_tokens:
                if t.text == word:
                    pos = t.pos
                    break
            keywords.append(Keyword(
                text=word, score=score,
                frequency=word_freq[word], pos=pos,
            ))
        return keywords

    # ===== 摘要生成 =====

    def generate_summary(
        self,
        text: str,
        ratio: float = 0.3,
        max_sentences: int = 10,
        method: str = "textrank",
    ) -> str:
        """中文摘要生成（抽取式）。

        基于句子权重排序，抽取 top-N 句子组成摘要。支持两种方法：
            - textrank: 基于 TextRank 的句子图排序
            - frequency: 基于词频的句子打分

        Args:
            text: 原始文本。
            ratio: 摘要占原文的比例（按句子数计）。
            max_sentences: 摘要最大句子数。
            method: 摘要方法。

        Returns:
            摘要文本。
        """
        if not text:
            return ""
        sentences = self.split_sentences(text, min_length=5)
        if len(sentences) <= 2:
            return text.strip()
        # 计算目标句子数
        target_count = max(1, min(max_sentences, int(len(sentences) * ratio)))
        # 句子打分
        if method.lower() == "frequency":
            scores = self._sentence_scores_frequency(sentences)
        else:
            scores = self._sentence_scores_textrank(sentences)
        # 选择 top-N 句子（保留原文顺序）
        ranked_indices = sorted(
            range(len(sentences)), key=lambda i: scores[i], reverse=True
        )[:target_count]
        selected_indices = sorted(ranked_indices)
        summary_sents = [sentences[i].text for i in selected_indices]
        return "".join(summary_sents)

    def _sentence_scores_frequency(self, sentences: List[Sentence]) -> List[float]:
        """基于词频的句子打分。"""
        # 统计全局词频
        word_freq: Counter = Counter()
        for sent in sentences:
            for token in sent.tokens:
                if (not token.is_stopword and len(token.text) >= 2
                        and token.pos not in ("w", "x", "m", "p", "u", "c")):
                    word_freq[token.text] += 1
        if not word_freq:
            return [1.0] * len(sentences)
        max_freq = max(word_freq.values())
        normalized_freq = {w: c / max_freq for w, c in word_freq.items()}
        # 句子打分
        scores: List[float] = []
        for sent in sentences:
            score = 0.0
            valid_tokens = 0
            for token in sent.tokens:
                if token.text in normalized_freq:
                    score += normalized_freq[token.text]
                    valid_tokens += 1
            # 归一化（按句子长度）
            if valid_tokens > 0:
                score = score / (math.log(valid_tokens + 2))
            # 位置加权：首句与末句加权
            scores.append(score)
        # 位置加权
        if len(scores) > 0:
            scores[0] *= 1.2
            scores[-1] *= 1.1
        return scores

    def _sentence_scores_textrank(self, sentences: List[Sentence]) -> List[float]:
        """基于 TextRank 的句子打分（句子相似度图）。"""
        n = len(sentences)
        if n == 0:
            return []
        # 构建句子词集合
        sent_word_sets: List[Set[str]] = []
        for sent in sentences:
            words = {
                token.text for token in sent.tokens
                if not token.is_stopword and len(token.text) >= 2
                and token.pos not in ("w", "x", "m", "p", "u", "c")
            }
            sent_word_sets.append(words)
        # 计算句子相似度（基于词重叠）
        similarity: List[List[float]] = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                s1, s2 = sent_word_sets[i], sent_word_sets[j]
                if not s1 or not s2:
                    sim = 0.0
                else:
                    # 余弦相似度（基于词集）
                    intersection = len(s1 & s2)
                    sim = intersection / (math.sqrt(len(s1)) * math.sqrt(len(s2)))
                similarity[i][j] = sim
                similarity[j][i] = sim
        # PageRank 迭代
        d = 0.85
        scores = [1.0] * n
        for _ in range(50):
            new_scores = [0.0] * n
            for i in range(n):
                in_sum = 0.0
                for j in range(n):
                    if i != j and similarity[j][i] > 0:
                        out_sum = sum(similarity[j])
                        if out_sum > 0:
                            in_sum += (similarity[j][i] / out_sum) * scores[j]
                new_scores[i] = (1 - d) / n + d * in_sum
            diff = sum(abs(new_scores[i] - scores[i]) for i in range(n))
            scores = new_scores
            if diff < 1e-6:
                break
        return scores

    # ===== 情感分析 =====

    def analyze_sentiment(self, text: str) -> SentimentResult:
        """中文情感分析。

        基于情感词典与规则的情感分析，考虑否定词与程度副词的修饰作用。

        Args:
            text: 待分析文本。

        Returns:
            情感分析结果。
        """
        if not text:
            return SentimentResult()
        tokens = self.tokenize(text, with_pos=True)
        if not tokens:
            return SentimentResult()
        score = 0.0
        positive_count = 0
        negative_count = 0
        # 遍历词元，考虑前 3 个词的修饰
        for i, token in enumerate(tokens):
            word = token.text
            if word in self.positive_words:
                # 检查前置否定与程度副词
                negation = False
                degree = 1.0
                for j in range(max(0, i - 3), i):
                    prev = tokens[j].text
                    if prev in self.negation_words:
                        negation = not negation
                    if prev in self.degree_words:
                        degree = self.degree_words[prev]
                base = 1.0 * degree
                if negation:
                    score -= base * 0.5  # 否定正面词 -> 轻微负面
                    negative_count += 1
                else:
                    score += base
                    positive_count += 1
            elif word in self.negative_words:
                negation = False
                degree = 1.0
                for j in range(max(0, i - 3), i):
                    prev = tokens[j].text
                    if prev in self.negation_words:
                        negation = not negation
                    if prev in self.degree_words:
                        degree = self.degree_words[prev]
                base = 1.0 * degree
                if negation:
                    score += base * 0.5  # 否定负面词 -> 轻微正面
                    positive_count += 1
                else:
                    score -= base
                    negative_count += 1
        # 归一化到 [-1, 1]
        total = positive_count + negative_count
        if total > 0:
            normalized_score = max(-1.0, min(1.0, score / total))
            confidence = min(1.0, total / 10.0)
        else:
            normalized_score = 0.0
            confidence = 0.0
        # 标签
        if normalized_score > 0.1:
            label = "positive"
        elif normalized_score < -0.1:
            label = "negative"
        else:
            label = "neutral"
        return SentimentResult(
            score=normalized_score,
            label=label,
            positive_count=positive_count,
            negative_count=negative_count,
            confidence=confidence,
        )

    # ===== 学术文本特殊处理 =====

    def identify_terms(self, text: str, min_length: int = 2) -> List[Entity]:
        """学术术语识别。

        基于术语后缀、词典与词性组合识别学术术语。

        Args:
            text: 待识别文本。
            min_length: 术语最小长度。

        Returns:
            术语实体列表。
        """
        if not text:
            return []
        terms: List[Entity] = []
        tokens = self.tokenize(text, with_pos=True, with_offset=True)
        # 规则1：词典中的术语
        for token in tokens:
            if token.text in self.dictionary and len(token.text) >= min_length:
                terms.append(Entity(
                    text=token.text, entity_type="TERM",
                    start=token.offset, end=token.offset + token.length,
                    confidence=0.9,
                ))
        # 规则2：以术语后缀结尾的连续名词组合
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.is_chinese and token.pos in ("n", "nr", "ns", "nt", "nz"):
                # 向后扩展名词组合
                j = i + 1
                while j < len(tokens):
                    next_tok = tokens[j]
                    if (next_tok.is_chinese and next_tok.pos in ("n", "nr", "ns", "nt", "nz")
                            and not next_tok.is_stopword):
                        j += 1
                        if j - i > 6:  # 限制最大长度
                            break
                    else:
                        break
                if j > i + 1:
                    combined = "".join(t.text for t in tokens[i:j])
                    if len(combined) >= min_length:
                        # 检查是否以术语后缀结尾
                        has_suffix = any(combined.endswith(s) for s in self.term_suffixes)
                        confidence = 0.8 if has_suffix else 0.6
                        # 避免重复
                        if not any(t.text == combined for t in terms):
                            terms.append(Entity(
                                text=combined, entity_type="TERM",
                                start=tokens[i].offset,
                                end=tokens[j - 1].offset + tokens[j - 1].length,
                                confidence=confidence,
                            ))
                    i = j
                    continue
            i += 1
        # 去重与排序
        seen: Set[str] = set()
        unique_terms: List[Entity] = []
        for term in sorted(terms, key=lambda e: e.start):
            if term.text not in seen:
                seen.add(term.text)
                unique_terms.append(term)
        return unique_terms

    def identify_formulas(self, text: str) -> List[FormulaInfo]:
        """公式识别。

        识别 LaTeX 公式（$...$、$$...$$、\\(...\\)、\\[...\\]）与 equation 环境。

        Args:
            text: 待识别文本。

        Returns:
            公式信息列表。
        """
        if not text:
            return []
        formulas: List[FormulaInfo] = []
        for pattern, ftype in [
            (re.compile(r"\$\$[^$]+\$\$"), "block"),
            (re.compile(r"\$[^$\n]+\$"), "inline"),
            (re.compile(r"\\\([^)]+\\\)"), "inline"),
            (re.compile(r"\\\[[^\]]+\\\]"), "block"),
            (re.compile(r"\\begin\{equation\}.*?\\end\{equation\}", re.DOTALL), "block"),
        ]:
            for m in pattern.finditer(text):
                formulas.append(FormulaInfo(
                    text=m.group(), formula_type=ftype,
                    start=m.start(), end=m.end(),
                ))
        # 去重（嵌套匹配）
        formulas.sort(key=lambda f: (f.start, -(f.end - f.start)))
        unique: List[FormulaInfo] = []
        for f in formulas:
            if not any(u.start <= f.start < u.end for u in unique):
                unique.append(f)
        return unique

    def identify_citations(self, text: str) -> List[CitationInfo]:
        """引用标记识别。

        识别数字引用（[1]）、作者-年份引用（Smith, 2020）、中文引用（张三，2020）。

        Args:
            text: 待识别文本。

        Returns:
            引用信息列表。
        """
        if not text:
            return []
        citations: List[CitationInfo] = []
        for pattern, ctype in [
            (CITATION_PATTERNS[0], "numeric"),
            (CITATION_PATTERNS[1], "author_year"),
            (CITATION_PATTERNS[2], "author_year"),
            (CITATION_PATTERNS[3], "chinese"),
            (CITATION_PATTERNS[4], "chinese"),
        ]:
            for m in pattern.finditer(text):
                ref_id = self._parse_citation_id(m.group(), ctype)
                citations.append(CitationInfo(
                    text=m.group(), citation_type=ctype,
                    start=m.start(), end=m.end(), ref_id=ref_id,
                ))
        # 去重与排序
        citations.sort(key=lambda c: c.start)
        return citations

    def _parse_citation_id(self, citation_text: str, ctype: str) -> Optional[str]:
        """解析引用标识。

        Args:
            citation_text: 引用文本。
            ctype: 引用类型。

        Returns:
            引用标识字符串。
        """
        try:
            if ctype == "numeric":
                # [1] / [1,2,3] / [1-3]
                inner = citation_text.strip("[]")
                return inner.replace(" ", "")
            elif ctype == "author_year":
                # (Smith, 2020) -> Smith:2020
                m = re.match(r"\(\s*([A-Z][a-zA-Z]+).*?,\s*(\d{4})\s*\)", citation_text)
                if m:
                    return f"{m.group(1)}:{m.group(2)}"
            elif ctype == "chinese":
                # 张三（2020） -> 张三:2020
                m = re.match(r"([\u4e00-\u9fff]{2,4})等?（(\d{4})）", citation_text)
                if m:
                    return f"{m.group(1)}:{m.group(2)}"
        except Exception:  # pragma: no cover
            pass
        return None

    # ===== 文本去重 =====

    def compute_simhash(self, text: str, hash_bits: int = 64) -> int:
        """计算文本的 SimHash 指纹。

        SimHash 是一种局部敏感哈希，相似文本的 SimHash 指纹海明距离较小。

        Args:
            text: 待计算文本。
            hash_bits: 哈希位数。

        Returns:
            SimHash 指纹（整数）。
        """
        if not text:
            return 0
        tokens = self.tokenize(text, with_pos=True)
        # 过滤停用词
        valid_tokens = [t for t in tokens if not t.is_stopword and len(t.text) >= 2]
        if not valid_tokens:
            valid_tokens = tokens
        if not valid_tokens:
            return 0
        # 词频统计
        word_freq: Counter = Counter(t.text for t in valid_tokens)
        # 初始化权重向量
        weights = [0] * hash_bits
        for word, freq in word_freq.items():
            # 计算词的哈希
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            # 对每一位加权
            for i in range(hash_bits):
                bit = (h >> i) & 1
                if bit:
                    weights[i] += freq
                else:
                    weights[i] -= freq
        # 生成指纹
        fingerprint = 0
        for i in range(hash_bits):
            if weights[i] > 0:
                fingerprint |= (1 << i)
        return fingerprint

    def hamming_distance(self, hash1: int, hash2: int) -> int:
        """计算两个 SimHash 指纹的海明距离。"""
        return bin(hash1 ^ hash2).count("1")

    def compute_minhash_signature(
        self,
        text: str,
        num_hashes: int = 128,
    ) -> List[int]:
        """计算文本的 MinHash 签名。

        MinHash 用于近似集合相似度计算，常用于大规模文本去重。

        Args:
            text: 待计算文本。
            num_hashes: 哈希函数数量。

        Returns:
            MinHash 签名列表。
        """
        if not text:
            return [0] * num_hashes
        tokens = self.tokenize(text)
        # 构建 n-gram 集合（3-gram）
        valid_tokens = [t.text for t in tokens if not t.is_stopword]
        if len(valid_tokens) < 3:
            shingles = set(valid_tokens) if valid_tokens else {text}
        else:
            shingles = {
                "".join(valid_tokens[i:i + 3])
                for i in range(len(valid_tokens) - 2)
            }
        if not shingles:
            return [0] * num_hashes
        # 计算签名
        signature: List[int] = []
        for i in range(num_hashes):
            min_hash = float("inf")
            for shingle in shingles:
                # 使用带种子的哈希
                h = int(hashlib.md5(f"{i}:{shingle}".encode("utf-8")).hexdigest(), 16)
                if h < min_hash:
                    min_hash = h
            signature.append(min_hash)
        return signature

    def estimate_jaccard(
        self,
        sig1: List[int],
        sig2: List[int],
    ) -> float:
        """基于 MinHash 签名估算 Jaccard 相似度。"""
        if not sig1 or not sig2 or len(sig1) != len(sig2):
            return 0.0
        matches = sum(1 for a, b in zip(sig1, sig2) if a == b)
        return matches / len(sig1)

    def deduplicate(
        self,
        texts: List[str],
        similarity_threshold: float = 0.85,
        method: str = "simhash",
    ) -> List[int]:
        """文本去重。

        返回保留文本的索引列表（重复文本中保留第一个）。

        Args:
            texts: 待去重文本列表。
            similarity_threshold: 相似度阈值。
            method: 去重方法，"simhash" 或 "minhash"。

        Returns:
            保留文本的索引列表。
        """
        if not texts:
            return []
        if method.lower() == "minhash":
            return self._dedup_minhash(texts, similarity_threshold)
        return self._dedup_simhash(texts, similarity_threshold)

    def _dedup_simhash(
        self,
        texts: List[str],
        threshold: float,
    ) -> List[int]:
        """基于 SimHash 的去重。"""
        hashes = [self.compute_simhash(t) for t in texts]
        # 阈值转换为海明距离
        max_distance = int((1 - threshold) * 64)
        kept: List[int] = []
        for i in range(len(texts)):
            is_dup = False
            for j in kept:
                if self.hamming_distance(hashes[i], hashes[j]) <= max_distance:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(i)
        return kept

    def _dedup_minhash(
        self,
        texts: List[str],
        threshold: float,
    ) -> List[int]:
        """基于 MinHash 的去重。"""
        signatures = [self.compute_minhash_signature(t) for t in texts]
        kept: List[int] = []
        for i in range(len(texts)):
            is_dup = False
            for j in kept:
                if self.estimate_jaccard(signatures[i], signatures[j]) >= threshold:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(i)
        return kept

    # ===== 相似度计算 =====

    def compute_similarity(
        self,
        text1: str,
        text2: str,
        method: str = "cosine",
    ) -> float:
        """中文文本相似度计算。

        支持多种方法：
            - cosine: 基于词频向量的余弦相似度
            - jaccard: 基于 n-gram 集合的 Jaccard 相似度
            - edit: 基于编辑距离的相似度
            - simhash: 基于 SimHash 海明距离的相似度

        Args:
            text1: 文本1。
            text2: 文本2。
            method: 相似度计算方法。

        Returns:
            相似度分数（0-1）。
        """
        if not text1 or not text2:
            return 0.0
        method = method.lower()
        if method == "cosine":
            return self._sim_cosine(text1, text2)
        elif method == "jaccard":
            return self._sim_jaccard(text1, text2)
        elif method == "edit":
            return self._sim_edit(text1, text2)
        elif method == "simhash":
            return self._sim_simhash(text1, text2)
        else:
            return self._sim_cosine(text1, text2)

    def _sim_cosine(self, text1: str, text2: str) -> float:
        """余弦相似度（基于词频向量）。"""
        tokens1 = [t.text for t in self.tokenize(text1) if not t.is_stopword]
        tokens2 = [t.text for t in self.tokenize(text2) if not t.is_stopword]
        if not tokens1 or not tokens2:
            return 0.0
        freq1: Counter = Counter(tokens1)
        freq2: Counter = Counter(tokens2)
        # 共同词
        common_words = set(freq1.keys()) & set(freq2.keys())
        if not common_words:
            return 0.0
        # 点积
        dot_product = sum(freq1[w] * freq2[w] for w in common_words)
        # 模
        norm1 = math.sqrt(sum(v * v for v in freq1.values()))
        norm2 = math.sqrt(sum(v * v for v in freq2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def _sim_jaccard(self, text1: str, text2: str) -> float:
        """Jaccard 相似度（基于 3-gram 集合）。"""
        tokens1 = [t.text for t in self.tokenize(text1) if not t.is_stopword]
        tokens2 = [t.text for t in self.tokenize(text2) if not t.is_stopword]
        # 构建 3-gram
        def make_shingles(tokens: List[str]) -> Set[str]:
            if len(tokens) < 3:
                return set(tokens)
            return {"".join(tokens[i:i + 3]) for i in range(len(tokens) - 2)}
        s1 = make_shingles(tokens1)
        s2 = make_shingles(tokens2)
        if not s1 or not s2:
            return 0.0
        intersection = len(s1 & s2)
        union = len(s1 | s2)
        return intersection / union if union > 0 else 0.0

    def _sim_edit(self, text1: str, text2: str) -> float:
        """编辑距离相似度。"""
        if text1 == text2:
            return 1.0
        max_len = max(len(text1), len(text2))
        if max_len == 0:
            return 1.0
        distance = self._levenshtein(text1, text2)
        return 1.0 - distance / max_len

    def _levenshtein(self, s1: str, s2: str) -> int:
        """计算 Levenshtein 编辑距离。"""
        if len(s1) < len(s2):
            return self._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def _sim_simhash(self, text1: str, text2: str) -> float:
        """SimHash 相似度（基于海明距离）。"""
        h1 = self.compute_simhash(text1)
        h2 = self.compute_simhash(text2)
        distance = self.hamming_distance(h1, h2)
        return 1.0 - distance / 64.0

    # ===== 中英文混合处理 =====

    def split_mixed_text(self, text: str) -> List[Tuple[str, str]]:
        """中英文混合文本切分。

        将混合文本切分为连续的中文片段与英文片段。

        Args:
            text: 混合文本。

        Returns:
            (片段文本, 语言标签) 列表，标签为 "zh" 或 "en"。
        """
        if not text:
            return []
        segments = self._split_by_script(text)
        result: List[Tuple[str, str]] = []
        for seg_text, seg_type in segments:
            if seg_type == "chinese":
                result.append((seg_text, "zh"))
            elif seg_type == "english":
                result.append((seg_text, "en"))
            # 数字与标点合并到前一段
            elif result and seg_type in ("number", "punct"):
                prev_text, prev_lang = result[-1]
                result[-1] = (prev_text + seg_text, prev_lang)
            elif seg_type in ("number", "punct"):
                result.append((seg_text, "en"))
        return result

    def detect_language(self, text: str) -> str:
        """语言检测（中文/英文/混合）。

        Args:
            text: 待检测文本。

        Returns:
            "zh"（中文）、"en"（英文）或 "mixed"（混合）。
        """
        if not text:
            return "zh"
        cjk_count = sum(1 for ch in text if _is_cjk_char(ch))
        alpha_count = sum(1 for ch in text if ch.isalpha() and not _is_cjk_char(ch))
        total = cjk_count + alpha_count
        if total == 0:
            return "zh"
        cjk_ratio = cjk_count / total
        if cjk_ratio > 0.8:
            return "zh"
        elif cjk_ratio < 0.2:
            return "en"
        return "mixed"

    # ===== 批量处理 =====

    def batch_tokenize(
        self,
        texts: List[str],
        with_pos: bool = False,
    ) -> List[List[Token]]:
        """批量分词。

        Args:
            texts: 文本列表。
            with_pos: 是否词性标注。

        Returns:
            每个文本的词元列表。
        """
        return [self.tokenize(t, with_pos=with_pos) for t in texts]

    def batch_extract_keywords(
        self,
        texts: List[str],
        top_k: int = 10,
        method: str = "tfidf",
    ) -> List[List[Keyword]]:
        """批量关键词提取。

        Args:
            texts: 文本列表。
            top_k: 每个文本返回的关键词数。
            method: 提取方法。

        Returns:
            每个文本的关键词列表。
        """
        return [self.extract_keywords(t, top_k=top_k, method=method) for t in texts]

    def batch_compute_similarity(
        self,
        query: str,
        candidates: List[str],
        method: str = "cosine",
    ) -> List[float]:
        """批量相似度计算。

        Args:
            query: 查询文本。
            candidates: 候选文本列表。
            method: 相似度方法。

        Returns:
            查询与每个候选的相似度列表。
        """
        return [self.compute_similarity(query, c, method=method) for c in candidates]

    # ===== 统计信息 =====

    def text_statistics(self, text: str) -> Dict[str, Any]:
        """文本统计信息。

        Args:
            text: 待统计文本。

        Returns:
            统计信息字典，包含字符数、词数、句数、段落数、平均句长等。
        """
        if not text:
            return {
                "char_count": 0, "word_count": 0, "sentence_count": 0,
                "paragraph_count": 0, "avg_sentence_length": 0.0,
                "avg_word_length": 0.0, "language": "zh",
            }
        tokens = self.tokenize(text)
        sentences = self.split_sentences(text)
        paragraphs = self.split_paragraphs(text)
        # 中文字符数
        cjk_count = sum(1 for ch in text if _is_cjk_char(ch))
        alpha_count = sum(1 for ch in text if ch.isalpha() and not _is_cjk_char(ch))
        # 平均句长
        total_sent_len = sum(len(s.text) for s in sentences)
        avg_sent_len = total_sent_len / len(sentences) if sentences else 0.0
        # 平均词长
        total_word_len = sum(len(t.text) for t in tokens)
        avg_word_len = total_word_len / len(tokens) if tokens else 0.0
        return {
            "char_count": len(text),
            "cjk_char_count": cjk_count,
            "alpha_char_count": alpha_count,
            "word_count": len(tokens),
            "sentence_count": len(sentences),
            "paragraph_count": len(paragraphs),
            "avg_sentence_length": round(avg_sent_len, 2),
            "avg_word_length": round(avg_word_len, 2),
            "language": self.detect_language(text),
            "unique_word_count": len({t.text for t in tokens}),
        }

    def add_stopwords(self, words: Iterable[str]) -> None:
        """添加自定义停用词。"""
        self.stopwords.update(words)

    def remove_stopwords(self, words: Iterable[str]) -> None:
        """移除停用词。"""
        self.stopwords.difference_update(words)

    def add_dictionary_words(self, words: Iterable[str]) -> None:
        """添加自定义词典词。"""
        new_words = set(words)
        self.dictionary.update(new_words)
        self._max_word_len = max(self._max_word_len, max((len(w) for w in new_words), default=0))
        if self.use_jieba:
            for word in new_words:
                try:
                    jieba.add_word(word)  # type: ignore
                except Exception:  # pragma: no cover
                    pass


# ===== 模块级单例访问 =====

def get_chinese_processor() -> ChineseProcessor:
    """获取全局中文处理器单例。"""
    return ChineseProcessor.get_instance()


def tokenize(text: str, with_pos: bool = False) -> List[Token]:
    """模块级分词便捷函数。"""
    return get_chinese_processor().tokenize(text, with_pos=with_pos)


def extract_keywords(text: str, top_k: int = 10, method: str = "tfidf") -> List[Keyword]:
    """模块级关键词提取便捷函数。"""
    return get_chinese_processor().extract_keywords(text, top_k=top_k, method=method)


def split_sentences(text: str) -> List[Sentence]:
    """模块级句子分割便捷函数。"""
    return get_chinese_processor().split_sentences(text)


def compute_similarity(text1: str, text2: str, method: str = "cosine") -> float:
    """模块级相似度计算便捷函数。"""
    return get_chinese_processor().compute_similarity(text1, text2, method=method)
