"""答辩准备助手 Agent（Task 10 / v9.0）

负责答辩 PPT 大纲生成、模拟答辩问题、答辩话术训练与回答评估，
覆盖 DEFENSE_PREP 阶段。作为 BaseAgent 子类接入多 Agent 架构，
通过 ai_proxy.call_llm 调用 LLM，并使用 save_message 持久化每轮交互。

支持的能力：
    - generate_defense_ppt: 生成分页答辩 PPT 大纲（标题/要点/讲稿）
    - generate_questions: 生成可能被问到的答辩问题（含难度分级与建议要点）
    - simulate_defense: 模拟答辩，针对问题生成结构化回答
    - generate_defense_speech: 生成答辩开场白（按指定时长）
    - evaluate_answer: 评估用户回答并给出反馈（评分/优点/不足/建议/参考答案）
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


# 答辩 PPT 标准页面结构（10 页）
_PPT_SLIDE_TEMPLATE = [
    ("第1页 封面", "论文题目、作者、导师、答辩日期"),
    ("第2页 研究背景与动机", "研究背景、问题意识、研究意义"),
    ("第3页 文献综述", "国内外研究现状、研究空白"),
    ("第4页 研究方法（一）", "总体架构、技术路线"),
    ("第5页 研究方法（二）", "关键算法/模型设计"),
    ("第6页 实验结果（一）", "实验设置、主实验结果"),
    ("第7页 实验结果（二）", "消融实验、对比分析"),
    ("第8页 结论与贡献", "研究结论、主要贡献"),
    ("第9页 未来工作", "局限性、未来研究方向"),
    ("第10页 致谢与 Q&A", "致谢、答辩问询环节"),
]


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


def _format_chapters(chapters: list) -> str:
    """将章节列表格式化为可读文本。

    Args:
        chapters: 章节列表，元素可以是字符串或字典（含 title/content 等键）。

    Returns:
        格式化后的章节文本。
    """
    if not chapters:
        return "（未提供章节信息）"
    lines = []
    for i, ch in enumerate(chapters, 1):
        if isinstance(ch, dict):
            title = ch.get("title") or ch.get("chapter_title") or ""
            content = ch.get("content") or ch.get("summary") or ""
            line = f"{i}. {title}".strip()
            if content:
                line += f"：{content}"
        else:
            line = f"{i}. {ch}"
        lines.append(line)
    return "\n".join(lines)


class DefenseAgent(BaseAgent):
    """DefenseAgent - 答辩准备助手

    协助完成答辩 PPT 大纲生成、模拟答辩问题、答辩话术训练与回答评估，
    覆盖 v9.0 DEFENSE_PREP 阶段。通过 ai_proxy.call_llm 调用 LLM，
    使用 save_message 持久化每轮交互。
    """

    def __init__(self):
        super().__init__(
            agent_id="defense_agent",
            name="答辩准备助手",
            description="协助准备答辩PPT、模拟答辩问题、答辩话术训练",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("report"),
            temperature=0.6,
            max_tokens=8192,
            capabilities=["streaming"],
        )

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "你是 ThesisMiner 的答辩准备助手（DefenseAgent），"
            "负责协助研究生完成学位论文答辩的全面准备工作，"
            "包括答辩 PPT 大纲、模拟答辩问题、答辩话术与回答评估。\n\n"
            "工作要求：\n"
            "1. 使用规范的学术中文，语言严谨、客观、自信\n"
            "2. 紧扣论文内容，避免空泛表述，所有要点需基于用户提供的论文章节\n"
            "3. PPT 大纲使用 Markdown 格式，每页包含标题、要点（bullet points）与讲稿（speaker notes）\n"
            "4. 模拟问题应覆盖：研究动机、方法、结果、贡献、局限性、未来工作\n"
            "5. 问题难度分三级：basic（基础）/ intermediate（进阶）/ challenging（挑战）\n"
            "6. 答辩话术应逻辑清晰，包含开场问候、研究概述、核心贡献、致谢\n"
            "7. 回答评估需给出 0-100 分数，并列出优点、不足、改进建议与参考答案\n"
            "8. 严格按要求的 JSON 格式输出结构化结果，便于程序解析\n"
            "9. 不臆造数据与文献，引用需基于用户提供的论文内容"
        )

    async def run(self, task_input: dict) -> AgentResult:
        """执行答辩准备任务（统一入口）。

        Args:
            task_input: 包含以下字段：
                - action: 任务类型（ppt / questions / simulate / speech / evaluate）
                - 其余字段根据 action 不同而变化

        Returns:
            AgentResult，data 包含执行结果。
        """
        action = task_input.get("action", "ppt")
        try:
            if action == "ppt":
                content = await self.generate_defense_ppt(
                    thesis_title=task_input.get("thesis_title", ""),
                    chapters=task_input.get("chapters", []) or [],
                    degree=task_input.get("degree", "master"),
                    session_id=task_input.get("session_id"),
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    content=content,
                    data={"action": "ppt", "ppt": content},
                )
            if action == "questions":
                questions = await self.generate_questions(
                    thesis_title=task_input.get("thesis_title", ""),
                    chapters=task_input.get("chapters", []) or [],
                    degree=task_input.get("degree", "master"),
                    num_questions=task_input.get("num_questions", 20),
                    session_id=task_input.get("session_id"),
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    content=json.dumps(questions, ensure_ascii=False),
                    data={"action": "questions", "questions": questions},
                )
            if action == "simulate":
                content = await self.simulate_defense(
                    question=task_input.get("question", ""),
                    thesis_content=task_input.get("thesis_content", ""),
                    session_id=task_input.get("session_id"),
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    content=content,
                    data={"action": "simulate", "answer": content},
                )
            if action == "speech":
                content = await self.generate_defense_speech(
                    thesis_title=task_input.get("thesis_title", ""),
                    chapters=task_input.get("chapters", []) or [],
                    degree=task_input.get("degree", "master"),
                    duration_minutes=task_input.get("duration_minutes", 10),
                    session_id=task_input.get("session_id"),
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    content=content,
                    data={"action": "speech", "speech": content},
                )
            if action == "evaluate":
                result = await self.evaluate_answer(
                    answer=task_input.get("answer", ""),
                    question=task_input.get("question", ""),
                    thesis_content=task_input.get("thesis_content", ""),
                    session_id=task_input.get("session_id"),
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    content=json.dumps(result, ensure_ascii=False),
                    data={"action": "evaluate", "result": result},
                )
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"未知的 action: {action}",
            )
        except Exception as e:
            logger.warning("答辩准备任务失败: %s", e, exc_info=True)
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"答辩准备任务失败: {e}",
            )

    # ==================== 答辩 PPT 大纲生成（SubTask 10.2） ====================

    async def generate_defense_ppt(
        self,
        thesis_title: str,
        chapters: list,
        degree: str,
        session_id: str = None,
    ) -> str:
        """生成答辩 PPT 大纲（分页结构）。

        Args:
            thesis_title: 论文标题。
            chapters: 章节列表（字符串或字典）。
            degree: 学位层次（本科/硕士/博士 或 bachelor/master/doctor）。
            session_id: 关联的会话 ID，用于消息持久化。

        Returns:
            Markdown 格式的 PPT 大纲字符串，每页包含标题、要点与讲稿。
        """
        label = _degree_label(degree)
        chapters_text = _format_chapters(chapters)
        slide_template_text = "\n".join(
            f"- {title}：{desc}" for title, desc in _PPT_SLIDE_TEMPLATE
        )

        user_prompt = (
            f"论文标题：{thesis_title or '（未提供）'}\n"
            f"学位层次：{label}\n"
            f"论文章节：\n{chapters_text}\n\n"
            f"请生成一份答辩 PPT 大纲，共 10 页，参考结构：\n"
            f"{slide_template_text}\n\n"
            f"要求：\n"
            f"- 每页包含：页面标题、要点（3-5 条 bullet points）、讲稿（speaker notes，1-2 句话）\n"
            f"- 使用 Markdown 格式，## 作为每页标题，- 作为要点，> 作为讲稿\n"
            f"- 内容紧扣论文章节，避免空泛表述\n"
            f"- 封面页需包含论文题目、作者、导师、答辩日期占位符\n"
            f"- 语言为学术中文，自信严谨"
        )

        try:
            self.save_message("user", user_prompt, session_id=session_id)
        except Exception:
            logger.debug("持久化用户消息失败", exc_info=True)
            self.add_message("user", user_prompt)

        content = await self._call_llm(user_prompt, purpose="defense_ppt")

        try:
            self.save_message("assistant", content, session_id=session_id)
        except Exception:
            logger.debug("持久化 assistant 消息失败", exc_info=True)
            self.add_message("assistant", content)

        if not content:
            content = self._ppt_fallback(thesis_title, label)
        return content

    # ==================== 答辩问题生成（SubTask 10.3） ====================

    async def generate_questions(
        self,
        thesis_title: str,
        chapters: list,
        degree: str,
        num_questions: int = 20,
        session_id: str = None,
    ) -> list:
        """生成可能被问到的答辩问题。

        Args:
            thesis_title: 论文标题。
            chapters: 章节列表。
            degree: 学位层次。
            num_questions: 生成问题数量，默认 20。
            session_id: 关联的会话 ID。

        Returns:
            问题列表，每个元素为字典：
                {question, category, difficulty, suggested_answer_points}
            difficulty 取值：basic / intermediate / challenging。
        """
        label = _degree_label(degree)
        chapters_text = _format_chapters(chapters)
        # 限制数量在合理范围
        num = max(5, min(50, int(num_questions or 20)))

        user_prompt = (
            f"论文标题：{thesis_title or '（未提供）'}\n"
            f"学位层次：{label}\n"
            f"论文章节：\n{chapters_text}\n\n"
            f"请生成 {num} 个该论文答辩时可能被问到的问题。要求：\n"
            f"- 问题覆盖：研究动机、方法论、实验结果、主要贡献、局限性、未来工作\n"
            f"- 难度分级：basic（基础概念）/ intermediate（进阶分析）/ challenging（挑战性/批判性）\n"
            f"- 每个问题给出 2-4 条建议回答要点（suggested_answer_points）\n"
            f"- 严格按 JSON 数组格式输出，每个元素结构：\n"
            f'  {{"question": "...", "category": "...", "difficulty": "basic|intermediate|challenging", '
            f'"suggested_answer_points": ["...", "..."]}}\n'
            f"- 仅输出 JSON 数组，不要附加其他说明文字"
        )

        try:
            self.save_message("user", user_prompt, session_id=session_id)
        except Exception:
            logger.debug("持久化用户消息失败", exc_info=True)
            self.add_message("user", user_prompt)

        raw = await self._call_llm(user_prompt, purpose="defense_questions")

        try:
            self.save_message("assistant", raw, session_id=session_id)
        except Exception:
            logger.debug("持久化 assistant 消息失败", exc_info=True)
            self.add_message("assistant", raw)

        return self._parse_questions(raw)

    # ==================== 模拟答辩（SubTask 10.3） ====================

    async def simulate_defense(
        self,
        question: str,
        thesis_content: str,
        session_id: str = None,
    ) -> str:
        """模拟答辩，针对问题生成结构化回答。

        Args:
            question: 答辩问题。
            thesis_content: 论文内容（用于支撑回答）。
            session_id: 关联的会话 ID。

        Returns:
            2-3 段的结构化回答字符串，包含关键论点、论文证据与逻辑推理。
        """
        user_prompt = (
            f"答辩问题：\n{question or '（未提供）'}\n\n"
            f"论文相关内容：\n{thesis_content or '（未提供）'}\n\n"
            f"请以答辩者身份，针对上述问题生成一份结构化回答。要求：\n"
            f"- 2-3 段，每段聚焦一个核心论点\n"
            f"- 包含关键论点、来自论文的证据/数据、逻辑推理\n"
            f"- 语言自信、严谨、学术化，避免口语化\n"
            f"- 使用 Markdown 格式，可用 **加粗** 强调关键术语\n"
            f"- 总字数约 300-500 字"
        )

        try:
            self.save_message("user", user_prompt, session_id=session_id)
        except Exception:
            logger.debug("持久化用户消息失败", exc_info=True)
            self.add_message("user", user_prompt)

        content = await self._call_llm(user_prompt, purpose="defense_simulate")

        try:
            self.save_message("assistant", content, session_id=session_id)
        except Exception:
            logger.debug("持久化 assistant 消息失败", exc_info=True)
            self.add_message("assistant", content)

        if not content:
            content = self._simulate_fallback(question)
        return content

    # ==================== 答辩话术生成（SubTask 10.3） ====================

    async def generate_defense_speech(
        self,
        thesis_title: str,
        chapters: list,
        degree: str,
        duration_minutes: int = 10,
        session_id: str = None,
    ) -> str:
        """生成答辩开场白。

        Args:
            thesis_title: 论文标题。
            chapters: 章节列表。
            degree: 学位层次。
            duration_minutes: 演讲时长（分钟），默认 10。
            session_id: 关联的会话 ID。

        Returns:
            答辩开场白字符串，包含开场问候、研究概述、核心贡献、致谢。
        """
        label = _degree_label(degree)
        chapters_text = _format_chapters(chapters)
        # 限制时长在合理范围
        minutes = max(3, min(30, int(duration_minutes or 10)))
        # 中文演讲语速约 200 字/分钟
        target_words = minutes * 200

        user_prompt = (
            f"论文标题：{thesis_title or '（未提供）'}\n"
            f"学位层次：{label}\n"
            f"论文章节：\n{chapters_text}\n\n"
            f"演讲时长：{minutes} 分钟（约 {target_words} 字）\n\n"
            f"请生成一份答辩开场白。要求：\n"
            f"- 包含：开场问候与自我介绍、研究背景与问题、研究方法概述、"
            f"核心贡献与创新点、主要实验结论、致谢\n"
            f"- 字数贴近 {target_words} 字\n"
            f"- 使用 Markdown 格式，## 作为各部分小标题\n"
            f"- 语言自信、流畅、学术化，适合口头表达\n"
            f"- 开场需包含「各位评委老师，大家好」等正式问候"
        )

        try:
            self.save_message("user", user_prompt, session_id=session_id)
        except Exception:
            logger.debug("持久化用户消息失败", exc_info=True)
            self.add_message("user", user_prompt)

        content = await self._call_llm(user_prompt, purpose="defense_speech")

        try:
            self.save_message("assistant", content, session_id=session_id)
        except Exception:
            logger.debug("持久化 assistant 消息失败", exc_info=True)
            self.add_message("assistant", content)

        if not content:
            content = self._speech_fallback(thesis_title, label, minutes)
        return content

    # ==================== 回答评估（SubTask 10.3） ====================

    async def evaluate_answer(
        self,
        answer: str,
        question: str,
        thesis_content: str,
        session_id: str = None,
    ) -> dict:
        """评估用户回答并给出反馈。

        Args:
            answer: 用户的回答内容。
            question: 答辩问题。
            thesis_content: 论文内容（用于对照）。
            session_id: 关联的会话 ID。

        Returns:
            评估结果字典，包含：
                - score: 0-100 的整数评分
                - strengths: 优点列表
                - weaknesses: 不足列表
                - suggestions: 改进建议列表
                - model_answer: 参考答案字符串
        """
        user_prompt = (
            f"答辩问题：\n{question or '（未提供）'}\n\n"
            f"用户回答：\n{answer or '（未提供）'}\n\n"
            f"论文相关内容：\n{thesis_content or '（未提供）'}\n\n"
            f"请评估上述回答并给出反馈。要求：\n"
            f"- score：0-100 的整数评分（综合准确性、完整性、逻辑性、表达）\n"
            f"- strengths：回答的优点列表（2-4 条）\n"
            f"- weaknesses：回答的不足列表（2-4 条）\n"
            f"- suggestions：具体改进建议列表（2-4 条）\n"
            f"- model_answer：一份高质量的参考答案（200-400 字）\n"
            f"- 严格按 JSON 格式输出：\n"
            f'  {{"score": number, "strengths": [str], "weaknesses": [str], '
            f'"suggestions": [str], "model_answer": str}}'
        )

        try:
            self.save_message("user", user_prompt, session_id=session_id)
        except Exception:
            logger.debug("持久化用户消息失败", exc_info=True)
            self.add_message("user", user_prompt)

        raw = await self._call_llm(user_prompt, purpose="defense_evaluate")

        try:
            self.save_message("assistant", raw, session_id=session_id)
        except Exception:
            logger.debug("持久化 assistant 消息失败", exc_info=True)
            self.add_message("assistant", raw)

        return self._parse_evaluate_result(raw)

    # ==================== 内部辅助方法 ====================

    async def _call_llm(self, user_prompt: str, purpose: str = "defense") -> str:
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
    def _parse_questions(raw: str) -> list:
        """解析 LLM 返回的答辩问题 JSON 数组。

        容错解析：依次尝试直接解析、提取代码块、提取 […]/{…} 子串。
        解析失败时返回兜底空列表。

        Args:
            raw: LLM 返回的原始文本。

        Returns:
            问题字典列表，每个元素包含 question / category / difficulty /
            suggested_answer_points 字段。
        """
        fallback: list = []
        if not raw:
            return fallback

        parsed = None
        # 1. 直接解析（数组或对象）
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. 提取 ```json ... ``` 代码块
        if parsed is None:
            code_block = re.search(
                r"```(?:json)?\s*(\[[\s\S]*?\]|\{[\s\S]*\})\s*```",
                raw,
                re.DOTALL,
            )
            if code_block:
                try:
                    parsed = json.loads(code_block.group(1))
                except (json.JSONDecodeError, TypeError):
                    pass

        # 3. 提取第一个 '[' 到最后一个 ']' 的子串
        if parsed is None:
            first = raw.find("[")
            last = raw.rfind("]")
            if first != -1 and last > first:
                try:
                    parsed = json.loads(raw[first:last + 1])
                except (json.JSONDecodeError, TypeError):
                    pass

        # 4. 兜底：尝试提取 {…}（单个对象）
        if parsed is None:
            first = raw.find("{")
            last = raw.rfind("}")
            if first != -1 and last > first:
                try:
                    obj = json.loads(raw[first:last + 1])
                    if isinstance(obj, dict):
                        parsed = [obj]
                except (json.JSONDecodeError, TypeError):
                    pass

        if not isinstance(parsed, list):
            return fallback

        # 规范化每个问题元素
        normalized_list = []
        valid_difficulties = {"basic", "intermediate", "challenging"}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question", "")).strip()
            if not question:
                continue
            category = str(item.get("category", "")).strip()
            difficulty = str(
                item.get("difficulty", "intermediate")
            ).strip().lower()
            if difficulty not in valid_difficulties:
                difficulty = "intermediate"
            points = item.get("suggested_answer_points", [])
            if not isinstance(points, list):
                points = [str(points)] if points else []
            else:
                points = [str(p) for p in points if p]
            normalized_list.append({
                "question": question,
                "category": category,
                "difficulty": difficulty,
                "suggested_answer_points": points,
            })
        return normalized_list

    @staticmethod
    def _parse_evaluate_result(raw: str) -> dict:
        """解析 LLM 返回的回答评估 JSON。

        容错解析：依次尝试直接解析、提取代码块、提取 {…} 子串。
        解析失败时返回兜底结果。

        Args:
            raw: LLM 返回的原始文本。

        Returns:
            评估结果字典，包含 score / strengths / weaknesses / suggestions /
            model_answer 字段。
        """
        fallback = {
            "score": 0,
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "model_answer": "",
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
        score = parsed.get("score", 0)
        try:
            score = int(score)
        except (TypeError, ValueError):
            try:
                score = int(float(score))
            except (TypeError, ValueError):
                score = 0
        # 限制在 0-100 范围
        score = max(0, min(100, score))

        def _to_str_list(value):
            if not isinstance(value, list):
                return [str(value)] if value else []
            return [str(v) for v in value if v]

        return {
            "score": score,
            "strengths": _to_str_list(parsed.get("strengths", [])),
            "weaknesses": _to_str_list(parsed.get("weaknesses", [])),
            "suggestions": _to_str_list(parsed.get("suggestions", [])),
            "model_answer": str(parsed.get("model_answer", "")),
        }

    @staticmethod
    def _ppt_fallback(thesis_title: str, degree_label: str) -> str:
        """PPT 大纲生成兜底（LLM 不可用时）。

        Args:
            thesis_title: 论文标题。
            degree_label: 学位中文标签。

        Returns:
            Markdown 格式的兜底 PPT 大纲字符串。
        """
        lines = [f"# {degree_label}学位答辩 PPT 大纲", ""]
        for title, desc in _PPT_SLIDE_TEMPLATE:
            lines.append(f"## {title}")
            lines.append(f"- {desc}")
            lines.append(f"> 讲稿：本页介绍{desc}，请结合论文内容展开。")
            lines.append("")
        if thesis_title:
            lines.insert(2, f"- 论文题目：{thesis_title}")
            lines.insert(3, "- 作者：[请填写]")
            lines.insert(4, "- 导师：[请填写]")
            lines.insert(5, "- 答辩日期：[请填写]")
            lines.insert(6, "")
        lines.append("*本 PPT 大纲由 ThesisMiner v9.0 兜底生成*")
        return "\n".join(lines)

    @staticmethod
    def _simulate_fallback(question: str) -> str:
        """模拟答辩兜底（LLM 不可用时）。

        Args:
            question: 答辩问题。

        Returns:
            兜底的回答字符串。
        """
        return (
            f"针对问题「{question or '（未提供）'}」，建议从以下角度回答：\n\n"
            f"首先，明确问题的核心，结合论文研究背景说明该问题的研究意义。"
            f"其次，引用论文中的方法、实验数据或理论推导作为支撑证据，"
            f"展示研究的严谨性。最后，总结回答并指出该问题与论文贡献的关联。\n\n"
            f"*本回答由 ThesisMiner v9.0 兜底生成*"
        )

    @staticmethod
    def _speech_fallback(
        thesis_title: str, degree_label: str, minutes: int
    ) -> str:
        """答辩话术兜底（LLM 不可用时）。

        Args:
            thesis_title: 论文标题。
            degree_label: 学位中文标签。
            minutes: 演讲时长（分钟）。

        Returns:
            兜底的答辩话术字符串。
        """
        return (
            f"## 开场问候\n\n"
            f"各位评委老师，大家好！我是{degree_label}学位答辩候选人，"
            f"今天我汇报的论文题目是《{thesis_title or '（未提供）'}》。\n\n"
            f"## 研究背景与问题\n\n"
            f"（待补充：请结合论文绪论部分介绍研究背景与问题意识。）\n\n"
            f"## 研究方法概述\n\n"
            f"（待补充：请结合论文方法章节介绍技术路线与关键算法。）\n\n"
            f"## 核心贡献与创新点\n\n"
            f"（待补充：请总结论文的主要贡献与创新点。）\n\n"
            f"## 主要实验结论\n\n"
            f"（待补充：请结合实验章节介绍主要结果与结论。）\n\n"
            f"## 致谢\n\n"
            f"感谢导师的悉心指导，感谢评委老师们的聆听，请各位老师批评指正。\n\n"
            f"---\n\n"
            f"*本话术由 ThesisMiner v9.0 兜底生成（目标时长 {minutes} 分钟）*"
        )
