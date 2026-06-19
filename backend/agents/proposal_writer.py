"""开题报告直出模块

基于论题结构化数据，生成符合标准高校模板的 Markdown 开题报告。
支持 AI 增强与模板兜底两种模式：AI 已配置时调用大模型扩展各章节，
未配置或调用失败时自动降级为内置模板生成，确保功能始终可用。
"""
import datetime
import json

from backend.ai.ai_proxy import call_llm, check_api_configured
from backend.database import fetch_one


async def generate_report(proposal_id: str, use_ai: bool = True) -> dict:
    """生成开题报告 Markdown 文档。

    Args:
        proposal_id: 论题 ID
        use_ai: 是否使用 AI 增强（默认 True），AI 未配置时自动降级为模板生成

    Returns:
        包含以下字段的字典：
        - proposal_id: 论题 ID
        - title: 论题标题
        - report: 完整 Markdown 报告字符串
        - ai_enhanced: 是否使用了 AI 增强
        - generated_at: 生成时间 ISO 格式

    Raises:
        ValueError: 当论题不存在时抛出
    """
    # 1. 从数据库获取论题
    proposal = fetch_one("SELECT * FROM proposals WHERE id = ?;", (proposal_id,))
    if proposal is None:
        raise ValueError(f"论题不存在：{proposal_id}")

    # 反序列化 JSON 字段（research_significance / research_content）
    _deserialize_fields(proposal)

    # 2. 获取会话信息（学位、学科、导师）
    session_id = proposal.get("session_id")
    session = None
    if session_id:
        session = fetch_one("SELECT * FROM sessions WHERE id = ?;", (session_id,))

    degree = session.get("degree", "master") if session else "master"
    discipline = session.get("discipline", "") if session else ""
    mentor_info = session.get("mentor_info", "") if session else ""

    # 3. 尝试 AI 增强，失败时降级为模板生成
    ai_enhanced = False
    if use_ai and check_api_configured():
        try:
            report = await _generate_with_ai(proposal, degree, discipline, mentor_info)
            ai_enhanced = True
        except Exception:
            # AI 调用失败，降级为模板生成
            report = _generate_with_template(proposal, degree, discipline, mentor_info)
    else:
        report = _generate_with_template(proposal, degree, discipline, mentor_info)

    return {
        "proposal_id": proposal_id,
        "title": proposal.get("title", ""),
        "report": report,
        "ai_enhanced": ai_enhanced,
        "generated_at": datetime.datetime.now().isoformat(),
    }


async def _generate_with_ai(
    proposal: dict, degree: str, discipline: str, mentor_info: str
) -> str:
    """使用 AI 增强生成开题报告。

    将结构化论题数据组装为提示，调用大模型扩展为完整 Markdown 报告。
    AI 返回空内容时降级为模板生成。

    Args:
        proposal: 论题字典（JSON 字段已反序列化）
        degree: 学位类型
        discipline: 学科类型
        mentor_info: 导师信息

    Returns:
        Markdown 格式的开题报告字符串
    """
    system_prompt = (
        "你是学术写作助手，负责将论题结构化数据扩展为完整的开题报告。"
        "输出格式为 Markdown，包含以下部分：选题依据、国内外研究现状、"
        "研究内容、技术路线、进度安排。保持学术严谨性，语言正式。"
    )

    # 构建用户提示：将论题各字段拼接为结构化输入
    user_prompt = f"""请基于以下论题数据生成完整的开题报告：

标题：{proposal.get('title', '')}
学位：{degree}
学科：{discipline}
导师信息：{mentor_info}

灵感来源：{proposal.get('inspiration_source', '')}
问题意识：{proposal.get('problem_awareness', '')}
研究意义（理论）：{proposal.get('research_significance', {}).get('theoretical', '')}
研究意义（实践）：{proposal.get('research_significance', {}).get('practical', '')}
文献综述大纲：{proposal.get('literature_review_outline', '')}
差异化/创新点：{proposal.get('differentiation', '')}
研究内容：{json.dumps(proposal.get('research_content', []), ensure_ascii=False)}
可行性分析：{proposal.get('feasibility_analysis', '')}

请输出完整的 Markdown 开题报告。"""

    result = await call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        purpose="proposal_report",
    )

    content = result.get("content", "")
    if not content:
        # AI 返回空内容，降级为模板
        return _generate_with_template(proposal, degree, discipline, mentor_info)

    return content


def _generate_with_template(
    proposal: dict, degree: str, discipline: str, mentor_info: str
) -> str:
    """使用内置模板生成开题报告（不依赖 AI）。

    模板包含：基本信息、选题依据、国内外研究现状、研究内容、
    技术路线与可行性分析、进度安排、置信度评估。

    Args:
        proposal: 论题字典（JSON 字段已反序列化）
        degree: 学位类型
        discipline: 学科类型
        mentor_info: 导师信息

    Returns:
        Markdown 格式的开题报告字符串
    """
    title = proposal.get("title", "未命名论题")

    # 研究意义：兼容 dict / str / JSON 字符串
    significance = proposal.get("research_significance", {})
    if isinstance(significance, str):
        try:
            significance = json.loads(significance)
        except (json.JSONDecodeError, TypeError):
            significance = {"theoretical": significance, "practical": ""}

    theoretical = significance.get("theoretical", "") if isinstance(significance, dict) else ""
    practical = significance.get("practical", "") if isinstance(significance, dict) else ""

    # 研究内容：兼容 list / str / JSON 字符串
    research_content = proposal.get("research_content", [])
    if isinstance(research_content, str):
        try:
            research_content = json.loads(research_content)
        except (json.JSONDecodeError, TypeError):
            research_content = [research_content]

    # 学位标签
    degree_label = "硕士" if degree == "master" else "博士"

    report = f"""# 开题报告

## 基本信息

- **论题标题**：{title}
- **学位类型**：{degree_label}
- **学科领域**：{discipline}
- **指导教师**：{mentor_info}

## 一、选题依据

### 1.1 问题意识

{proposal.get('problem_awareness', '（待补充）')}

### 1.2 灵感来源

{proposal.get('inspiration_source', '（待补充）')}

### 1.3 研究意义

**理论意义**：{theoretical or '（待补充）'}

**实践意义**：{practical or '（待补充）'}

## 二、国内外研究现状

{proposal.get('literature_review_outline', '（待补充）')}

### 2.1 差异化与创新点

{proposal.get('differentiation', '（待补充）')}

## 三、研究内容

"""
    # 添加研究内容条目
    if isinstance(research_content, list) and research_content:
        for i, item in enumerate(research_content, 1):
            report += f"{i}. {item}\n\n"
    else:
        report += "（待补充）\n\n"

    report += f"""## 四、技术路线与可行性分析

{proposal.get('feasibility_analysis', '（待补充）')}

## 五、进度安排

"""
    # 根据学位生成进度安排
    if degree == "master":
        schedule = [
            ("第1-2个月", "文献调研与选题确认"),
            ("第3-4个月", "理论框架构建与方法学习"),
            ("第5-8个月", "实验设计与数据收集"),
            ("第9-10个月", "数据分析与结果验证"),
            ("第11-12个月", "论文撰写与答辩准备"),
        ]
    else:  # doctor
        schedule = [
            ("第1-3个月", "文献综述与选题深化"),
            ("第4-6个月", "理论框架构建与预实验"),
            ("第7-12个月", "核心实验与数据收集"),
            ("第13-18个月", "扩展实验与结果验证"),
            ("第19-24个月", "论文撰写与答辩准备"),
        ]

    for period, task in schedule:
        report += f"- **{period}**：{task}\n"

    report += f"""
## 六、置信度评估

本论题的置信度评分为：**{proposal.get('confidence_score', 'N/A')}**

---

*本报告由 ThesisMiner v6.0 自动生成*
"""

    return report


def _deserialize_fields(proposal: dict) -> None:
    """反序列化 proposal 行中的 JSON 字段（原地修改）。

    将 research_significance 与 research_content 字段从 JSON 字符串
    还原为 dict / list；解析失败时保留原始字符串。

    Args:
        proposal: 论题字典（原地修改）
    """
    for field in ("research_significance", "research_content"):
        raw = proposal.get(field)
        if isinstance(raw, str):
            try:
                proposal[field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                # 解析失败时保留原始字符串
                pass
