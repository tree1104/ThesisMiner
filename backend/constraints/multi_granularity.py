"""多粒度生成器

支持四种粒度输出：
- 标题级（≤20字）
- 摘要级（200-300字）
- 大纲级（3级目录）
- 全文级（≥5000字）
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class GranularitySpec:
    """粒度规格定义"""
    level: str
    name: str
    min_length: int
    max_length: int
    description: str


GRANULARITY_SPECS = {
    "title": GranularitySpec("title", "标题级", 8, 20, "精炼的论题标题"),
    "abstract": GranularitySpec("abstract", "摘要级", 200, 300, "包含背景/问题/方法/意义的摘要"),
    "outline": GranularitySpec("outline", "大纲级", 500, 2000, "三级目录结构"),
    "full": GranularitySpec("full", "全文级", 5000, 50000, "完整开题报告"),
}


def get_granularity_spec(level: str) -> Optional[GranularitySpec]:
    """获取粒度规格"""
    return GRANULARITY_SPECS.get(level)


def validate_granularity(content: str, level: str) -> dict:
    """验证生成内容是否符合粒度要求"""
    spec = get_granularity_spec(level)
    if not spec:
        return {"valid": False, "message": f"未知粒度: {level}"}

    length = len(content)
    valid = spec.min_length <= length <= spec.max_length

    return {
        "valid": valid,
        "level": level,
        "length": length,
        "min_required": spec.min_length,
        "max_required": spec.max_length,
        "message": "符合要求" if valid else f"长度{length}不在要求范围[{spec.min_length}, {spec.max_length}]内",
    }


def build_granularity_prompt(level: str, topic: str, context: dict = None) -> str:
    """构建粒度生成 Prompt"""
    spec = get_granularity_spec(level)
    if not spec:
        return ""

    context = context or {}

    prompts = {
        "title": f"""请为以下研究方向生成一个精炼的论题标题。
要求：
- 字数在{spec.min_length}-{spec.max_length}字之间
- 突出创新点
- 避免宽泛表述

研究方向：{topic}
""",
        "abstract": f"""请为以下论题生成一个摘要。
要求：
- 字数在{spec.min_length}-{spec.max_length}字之间
- 包含研究背景、问题、方法、意义四个要素
- 语言精炼，避免空话

论题：{topic}
""",
        "outline": f"""请为以下论题生成一个三级大纲。
要求：
- 使用标准的学术大纲格式（一、(一)、1.）
- 包含绪论、文献综述、研究方法、预期成果等章节
- 每个三级标题下附简要说明

论题：{topic}
""",
        "full": f"""请为以下论题生成完整的开题报告。
要求：
- 字数≥{spec.min_length}字
- 包含：选题依据、文献综述、研究内容、研究方法、技术路线、预期成果、进度安排
- 学术规范，引用规范

论题：{topic}
""",
    }

    return prompts.get(level, "")
