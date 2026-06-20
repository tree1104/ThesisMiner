"""论文撰写助手 Agent（Task 9 / v9.0）

负责论文各章节的撰写、修改与查重降重，覆盖 THESIS_WRITING 阶段。
作为 BaseAgent 子类接入多 Agent 架构，通过 ai_proxy.call_llm 调用 LLM，
并使用 save_message 持久化每轮交互。

支持的能力：
    - generate_outline: 基于开题报告生成分学位层次的章节大纲
    - write_chapter: 撰写指定章节（含学术格式与引用标注）
    - revise_chapter: 根据反馈意见修订章节
    - check_plagiarism: 模拟查重，返回相似度评分与高风险段落
    - reduce_similarity: 根据查重建议进行降重改写
"""
import json
import logging
import re

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.config import get_step_model

logger = logging.getLogger(__name__)


# 学位层次到中文学位标签的映射
_DEGREE_LABELS = {
    "bachelor": "本科",
    "master": "硕士",
    "doctor": "博士",
    "本科": "本科",
    "硕士": "硕士",
    "博士": "博士",
}


# 各学位层次的章节模板（用于提示与兜底）
_DEGREE_OUTLINE_TEMPLATES = {
    "bachelor": [
        ("第一章 绪论", "研究背景、问题意识、研究意义、研究内容与论文结构", 3000),
        ("第二章 相关工作/文献综述", "国内外研究现状、现有方法对比、研究空白", 4000),
        ("第三章 系统设计/研究方法", "总体架构、关键技术、研究方法与实验设计", 5000),
        ("第四章 实现与实验", "系统实现、实验设置、结果分析与讨论", 5000),
        ("第五章 总结与展望", "研究总结、主要贡献、局限性与未来工作", 2000),
    ],
    "master": [
        ("第一章 绪论", "研究背景、问题意识、研究意义、研究内容与技术路线", 3500),
        ("第二章 文献综述", "国内外研究现状、现有方法分类与对比、研究空白", 5000),
        ("第三章 理论基础/技术路线", "核心理论、技术框架、关键算法与数学推导", 5000),
        ("第四章 系统设计/实验设计", "总体架构、模块设计、实验环境与评估指标", 5500),
        ("第五章 实验与分析", "实验设置、结果对比、消融实验与结果讨论", 5500),
        ("第六章 总结与展望", "研究总结、主要贡献、局限性与未来工作", 2500),
    ],
    "doctor": [
        ("第一章 绪论", "研究背景、问题意识、研究意义、研究内容与创新点", 4000),
        ("第二章 文献综述", "国内外研究现状、研究脉络梳理、研究空白与挑战", 6000),
        ("第三章 理论框架", "核心理论建构、假设提出、理论模型与推演", 6000),
        ("第四章 研究方法", "研究设计、数据采集、分析方法与有效性保障", 5500),
        ("第五章 实验与分析", "实验设置、主实验结果、消融实验与统计检验", 6500),
        ("第六章 讨论与验证", "结果讨论、理论验证、对比分析与局限性分析", 5000),
        ("第七章 总结与展望", "研究总结、主要贡献、理论/实践意义与未来工作", 3000),
    ],
}


def _normalize_degree(degree: str) -> str:
    """将学位标识规范化为 bachelor/master/doctor。

    兼容中英文输入：本科→bachelor，硕士→master，博士→doctor。
    无法识别时回退为 master。
    """
    if not degree:
        return "master"
    degree_lower = str(degree).lower().strip()
    if degree_lower in ("bachelor", "本科"):
        return "bachelor"
    if degree_lower in ("doctor", "博士", "phd"):
        return "doctor"
    return "master"


def _degree_label(degree: str) -> str:
    """获取学位的中文标签。"""
    normalized = _normalize_degree(degree)
    return _DEGREE_LABELS.get(normalized, "硕士")


class ThesisWriterAgent(BaseAgent):
    """ThesisWriterAgent - 论文撰写助手

    协助完成论文各章节的撰写、修改与查重降重，覆盖 v9.0 THESIS_WRITING 阶段。
    通过 ai_proxy.call_llm 调用 LLM，使用 save_message 持久化每轮交互。
    """

    def __init__(self):
        super().__init__(
            agent_id="thesis_writer",
            name="论文撰写助手",
            description="协助完成论文各章节的撰写、修改与查重降重",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("report"),
            temperature=0.6,
            max_tokens=8192,
            capabilities=["streaming"],
        )

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "你是 ThesisMiner 的论文撰写助手（ThesisWriter），"
            "负责协助研究生完成学位论文各章节的撰写、修改与查重降重。\n\n"
            "写作要求：\n"
            "1. 使用规范的学术中文，语言严谨、客观、正式\n"
            "2. 章节结构清晰，使用 Markdown 标题层级（# / ## / ###）\n"
            "3. 引用文献使用方括号上标格式，如 [1][2]，并在文末列出参考文献\n"
            "4. 图表使用占位符标注，如「图3-1 实验框架」「表4-2 结果对比」\n"
            "5. 公式使用 LaTeX 语法，如 $E = mc^2$\n"
            "6. 严格遵循学位层次要求：本科约5章、硕士约6章、博士约7章\n"
            "7. 不臆造数据与文献，引用需基于用户提供的参考文献列表\n"
            "8. 各章节字数应贴近大纲中预估的字数要求\n\n"
            "查重要求：\n"
            "- 识别可能存在高重复风险的段落（连续表述、定义性内容等）\n"
            "- 给出相似度评分（0-100）与具体降重建议\n"
            "- 降重时通过同义改写、句式重构、语序调整等方式保持原意"
        )

    async def run(self, task_input: dict) -> AgentResult:
        """执行论文撰写任务（统一入口）。

        Args:
            task_input: 包含以下字段：
                - action: 任务类型（outline / write / revise / plagiarism / reduce）
                - 其余字段根据 action 不同而变化

        Returns:
            AgentResult，data 包含执行结果。
        """
        action = task_input.get("action", "outline")
        try:
            if action == "outline":
                content = await self.generate_outline(
                    proposal=task_input.get("proposal", ""),
                    degree=task_input.get("degree", "master"),
                    session_id=task_input.get("session_id"),
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    content=content,
                    data={"action": "outline", "outline": content},
                )
            if action == "write":
                content = await self.write_chapter(
                    chapter_title=task_input.get("chapter_title", ""),
                    outline=task_input.get("outline", ""),
                    references=task_input.get("references", []) or [],
                    degree=task_input.get("degree", "master"),
                    session_id=task_input.get("session_id"),
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    content=content,
                    data={"action": "write", "chapter": content},
                )
            if action == "revise":
                content = await self.revise_chapter(
                    chapter_content=task_input.get("chapter_content", ""),
                    feedback=task_input.get("feedback", ""),
                    session_id=task_input.get("session_id"),
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    content=content,
                    data={"action": "revise", "chapter": content},
                )
            if action == "plagiarism":
                result = await self.check_plagiarism(
                    chapter_content=task_input.get("chapter_content", ""),
                    session_id=task_input.get("session_id"),
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    content=json.dumps(result, ensure_ascii=False),
                    data={"action": "plagiarism", "result": result},
                )
            if action == "reduce":
                content = await self.reduce_similarity(
                    chapter_content=task_input.get("chapter_content", ""),
                    suggestions=task_input.get("suggestions", []) or [],
                    session_id=task_input.get("session_id"),
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    content=content,
                    data={"action": "reduce", "chapter": content},
                )
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"未知的 action: {action}",
            )
        except Exception as e:
            logger.warning("论文撰写任务失败: %s", e, exc_info=True)
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"论文撰写任务失败: {e}",
            )

    # ==================== 大纲生成（SubTask 9.2） ====================

    async def generate_outline(
        self,
        proposal: str,
        degree: str = "master",
        session_id: str = None,
    ) -> str:
        """基于开题报告生成分学位层次的章节大纲。

        Args:
            proposal: 开题报告文本（或论题描述）。
            degree: 学位层次（本科/硕士/博士 或 bachelor/master/doctor）。
            session_id: 关联的会话 ID，用于消息持久化。

        Returns:
            Markdown 格式的章节大纲字符串，每章包含标题、简介、预估字数与要点。
        """
        normalized = _normalize_degree(degree)
        label = _degree_label(degree)
        template = _DEGREE_OUTLINE_TEMPLATES[normalized]

        user_prompt = (
            f"开题报告/论题描述：\n{proposal or '（未提供）'}\n\n"
            f"学位层次：{label}\n"
            f"请基于上述开题报告，生成一份完整的论文章节大纲。\n"
            f"要求：\n"
            f"- 共约 {len(template)} 章，章节结构符合{label}学位论文规范\n"
            f"- 每章包含：章节标题、章节简介、预估字数、关键要点（3-5条）\n"
            f"- 输出 Markdown 格式，使用 ## 作为章节标题\n"
            f"- 大纲应紧扣开题报告中的研究内容与技术路线"
        )

        # 持久化用户消息
        try:
            self.save_message("user", user_prompt, session_id=session_id)
        except Exception:
            logger.debug("持久化用户消息失败", exc_info=True)
            self.add_message("user", user_prompt)

        content = await self._call_llm(user_prompt, purpose="thesis_outline")

        # 持久化 assistant 回复
        try:
            self.save_message("assistant", content, session_id=session_id)
        except Exception:
            logger.debug("持久化 assistant 消息失败", exc_info=True)
            self.add_message("assistant", content)

        if not content:
            content = self._outline_fallback(normalized)
        return content

    # ==================== 章节撰写（SubTask 9.3） ====================

    async def write_chapter(
        self,
        chapter_title: str,
        outline: str,
        references: list,
        degree: str = "master",
        session_id: str = None,
    ) -> str:
        """撰写指定章节的完整内容。

        Args:
            chapter_title: 章节标题。
            outline: 章节大纲（含本章要点与预估字数）。
            references: 参考文献列表（字符串列表）。
            degree: 学位层次。
            session_id: 关联的会话 ID。

        Returns:
            Markdown 格式的章节内容字符串，含小节标题、引用标注与图表占位符。
        """
        label = _degree_label(degree)
        refs_text = ""
        if references:
            ref_lines = [
                f"[{i}] {r}" for i, r in enumerate(references, 1)
            ]
            refs_text = "\n".join(ref_lines)

        user_prompt = (
            f"章节标题：{chapter_title}\n"
            f"学位层次：{label}\n"
            f"章节大纲：\n{outline or '（未提供）'}\n\n"
            f"参考文献列表：\n{refs_text or '（未提供）'}\n\n"
            f"请撰写该章节的完整内容。要求：\n"
            f"- 使用规范的学术中文，语言严谨客观\n"
            f"- 使用 Markdown 格式，### 作为小节标题\n"
            f"- 引用文献使用 [1][2] 方括号上标格式\n"
            f"- 图表使用占位符，如「图3-1 ...」「表4-1 ...」\n"
            f"- 字数贴近大纲中的预估字数\n"
            f"- 不臆造数据，引用需基于上方参考文献列表"
        )

        try:
            self.save_message("user", user_prompt, session_id=session_id)
        except Exception:
            logger.debug("持久化用户消息失败", exc_info=True)
            self.add_message("user", user_prompt)

        content = await self._call_llm(user_prompt, purpose="thesis_write")

        try:
            self.save_message("assistant", content, session_id=session_id)
        except Exception:
            logger.debug("持久化 assistant 消息失败", exc_info=True)
            self.add_message("assistant", content)

        if not content:
            content = self._chapter_fallback(chapter_title)
        return content

    # ==================== 章节修订（SubTask 9.4） ====================

    async def revise_chapter(
        self,
        chapter_content: str,
        feedback: str,
        session_id: str = None,
    ) -> str:
        """根据反馈意见修订章节内容。

        Args:
            chapter_content: 原始章节内容。
            feedback: 修订反馈意见。
            session_id: 关联的会话 ID。

        Returns:
            修订后的章节内容字符串，保持学术风格与引用标注。
        """
        user_prompt = (
            f"原始章节内容：\n{chapter_content or '（未提供）'}\n\n"
            f"修订反馈意见：\n{feedback or '（未提供）'}\n\n"
            f"请根据反馈意见修订上述章节内容。要求：\n"
            f"- 保持学术中文风格与原有引用标注 [1][2]\n"
            f"- 针对性回应每条反馈意见\n"
            f"- 保持章节结构完整，使用 Markdown 格式\n"
            f"- 输出修订后的完整章节内容"
        )

        try:
            self.save_message("user", user_prompt, session_id=session_id)
        except Exception:
            logger.debug("持久化用户消息失败", exc_info=True)
            self.add_message("user", user_prompt)

        content = await self._call_llm(user_prompt, purpose="thesis_revise")

        try:
            self.save_message("assistant", content, session_id=session_id)
        except Exception:
            logger.debug("持久化 assistant 消息失败", exc_info=True)
            self.add_message("assistant", content)

        if not content:
            content = chapter_content or ""
        return content

    # ==================== 查重检测（SubTask 9.4） ====================

    async def check_plagiarism(
        self,
        chapter_content: str,
        session_id: str = None,
    ) -> dict:
        """模拟查重检测，返回相似度评分与高风险段落。

        使用 LLM 识别可能存在高重复风险的段落（定义性内容、连续表述等），
        返回结构化查重报告。

        Args:
            chapter_content: 待查重的章节内容。
            session_id: 关联的会话 ID。

        Returns:
            查重结果字典，包含：
                - similarity_score: 相似度评分（0-100，float）
                - high_risk_sections: 高风险段落列表
                - suggestions: 降重建议列表
        """
        user_prompt = (
            f"待查重内容：\n{chapter_content or '（未提供）'}\n\n"
            f"请模拟学术查重检测，分析上述内容的重复风险。要求：\n"
            f"- 给出整体相似度评分（0-100 的数字）\n"
            f"- 识别高风险段落（定义性内容、常见表述、连续引用等）\n"
            f"- 针对每个高风险段落给出具体降重建议\n"
            f"- 严格按 JSON 格式输出：\n"
            f'{{"similarity_score": number, "high_risk_sections": [str], '
            f'"suggestions": [str]}}'
        )

        try:
            self.save_message("user", user_prompt, session_id=session_id)
        except Exception:
            logger.debug("持久化用户消息失败", exc_info=True)
            self.add_message("user", user_prompt)

        raw = await self._call_llm(user_prompt, purpose="thesis_plagiarism")

        try:
            self.save_message("assistant", raw, session_id=session_id)
        except Exception:
            logger.debug("持久化 assistant 消息失败", exc_info=True)
            self.add_message("assistant", raw)

        result = self._parse_plagiarism_result(raw)
        return result

    # ==================== 降重改写（SubTask 9.4） ====================

    async def reduce_similarity(
        self,
        chapter_content: str,
        suggestions: list,
        session_id: str = None,
    ) -> str:
        """根据查重建议进行降重改写。

        Args:
            chapter_content: 原始章节内容。
            suggestions: 降重建议列表（来自 check_plagiarism）。
            session_id: 关联的会话 ID。

        Returns:
            降重改写后的章节内容字符串，通过同义改写、句式重构、
            语序调整等方式降低相似度，保持原意与学术风格。
        """
        suggestions_text = ""
        if suggestions:
            sug_lines = [
                f"{i}. {s}" for i, s in enumerate(suggestions, 1)
            ]
            suggestions_text = "\n".join(sug_lines)

        user_prompt = (
            f"原始章节内容：\n{chapter_content or '（未提供）'}\n\n"
            f"降重建议：\n{suggestions_text or '（未提供）'}\n\n"
            f"请根据上述建议对章节内容进行降重改写。要求：\n"
            f"- 通过同义改写、句式重构、语序调整等方式降低相似度\n"
            f"- 保持原意与学术中文风格\n"
            f"- 保留原有引用标注 [1][2] 与图表占位符\n"
            f"- 输出降重后的完整章节内容（Markdown 格式）"
        )

        try:
            self.save_message("user", user_prompt, session_id=session_id)
        except Exception:
            logger.debug("持久化用户消息失败", exc_info=True)
            self.add_message("user", user_prompt)

        content = await self._call_llm(user_prompt, purpose="thesis_reduce")

        try:
            self.save_message("assistant", content, session_id=session_id)
        except Exception:
            logger.debug("持久化 assistant 消息失败", exc_info=True)
            self.add_message("assistant", content)

        if not content:
            content = chapter_content or ""
        return content

    # ==================== 内部辅助方法 ====================

    async def _call_llm(self, user_prompt: str, purpose: str = "thesis") -> str:
        """调用 LLM 并返回正文内容。

        延迟导入 ai_proxy 以避免循环依赖。

        Args:
            user_prompt: 用户提示词。
            purpose: 调用用途，用于模型路由与账本记录。

        Returns:
            LLM 返回的正文内容字符串。
        """
        from backend.ai.ai_proxy import call_llm as _call_llm

        result = await _call_llm(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            model=self.model_id,
            temperature=self.temperature,
            purpose=purpose,
        )
        return result.get("content", "")

    @staticmethod
    def _parse_plagiarism_result(raw: str) -> dict:
        """解析 LLM 返回的查重结果 JSON。

        容错解析：依次尝试直接解析、提取代码块、提取 {…} 子串。
        解析失败时返回兜底结果。

        Args:
            raw: LLM 返回的原始文本。

        Returns:
            查重结果字典，包含 similarity_score / high_risk_sections / suggestions。
        """
        fallback = {
            "similarity_score": 0.0,
            "high_risk_sections": [],
            "suggestions": [],
        }
        if not raw:
            return fallback

        parsed = None
        # 1. 直接解析
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. 提取 ```json ... ``` 代码块
        if parsed is None:
            code_block = re.search(
                r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL
            )
            if code_block:
                try:
                    parsed = json.loads(code_block.group(1))
                except (json.JSONDecodeError, TypeError):
                    pass

        # 3. 提取第一个 '{' 到最后一个 '}' 的子串
        if parsed is None:
            first = raw.find("{")
            last = raw.rfind("}")
            if first != -1 and last > first:
                try:
                    parsed = json.loads(raw[first:last + 1])
                except (json.JSONDecodeError, TypeError):
                    pass

        if not isinstance(parsed, dict):
            return fallback

        # 规范化字段
        score = parsed.get("similarity_score", 0)
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0
        # 限制在 0-100 范围
        score = max(0.0, min(100.0, score))

        high_risk = parsed.get("high_risk_sections", [])
        if not isinstance(high_risk, list):
            high_risk = [str(high_risk)] if high_risk else []

        suggestions = parsed.get("suggestions", [])
        if not isinstance(suggestions, list):
            suggestions = [str(suggestions)] if suggestions else []

        return {
            "similarity_score": score,
            "high_risk_sections": [str(s) for s in high_risk],
            "suggestions": [str(s) for s in suggestions],
        }

    @staticmethod
    def _outline_fallback(degree: str) -> str:
        """大纲生成兜底（LLM 不可用时）。

        Args:
            degree: 规范化后的学位层次（bachelor/master/doctor）。

        Returns:
            Markdown 格式的兜底大纲字符串。
        """
        template = _DEGREE_OUTLINE_TEMPLATES.get(degree, _DEGREE_OUTLINE_TEMPLATES["master"])
        label = _DEGREE_LABELS.get(degree, "硕士")
        lines = [f"# {label}学位论文章节大纲", ""]
        for title, desc, word_count in template:
            lines.append(f"## {title}")
            lines.append(f"- 章节简介：{desc}")
            lines.append(f"- 预估字数：{word_count} 字")
            lines.append("- 关键要点：")
            lines.append("  - 研究背景与问题界定")
            lines.append("  - 核心方法与技术路线")
            lines.append("  - 实验设计与结果分析")
            lines.append("")
        lines.append("*本大纲由 ThesisMiner v9.0 兜底生成*")
        return "\n".join(lines)

    @staticmethod
    def _chapter_fallback(chapter_title: str) -> str:
        """章节撰写兜底（LLM 不可用时）。

        Args:
            chapter_title: 章节标题。

        Returns:
            Markdown 格式的兜底章节内容字符串。
        """
        return (
            f"## {chapter_title}\n\n"
            f"### 1. 概述\n\n"
            f"（待补充：本节介绍{chapter_title}的背景与主要内容。）\n\n"
            f"### 2. 核心内容\n\n"
            f"（待补充：本节展开{chapter_title}的核心论述。）\n\n"
            f"### 3. 小结\n\n"
            f"（待补充：本节对{chapter_title}进行总结。）\n\n"
            f"---\n\n"
            f"*本章节由 ThesisMiner v9.0 兜底生成*"
        )
