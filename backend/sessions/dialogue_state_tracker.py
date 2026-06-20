"""对话状态追踪器 DST 模块

从历史对话中提取结构化状态槽，用于压缩上下文、保持 Prompt 前缀稳定。

通过扫描对话历史中的关键词（如"选定"、"确认"、"方法"等），
提取已选定的论题、已确认的研究方法、已确认的学科方向、
待解决的问题以及对话轮数，形成可序列化的状态字典。
"""
import re


def extract_state(history: list[dict]) -> dict:
    """从对话历史中提取结构化状态槽。

    扫描 history 列表，提取以下状态槽：
    - selected_topic: 已选定的论题标题（若用户已确认）
    - confirmed_methods: 已确认的研究方法列表
    - confirmed_discipline: 已确认的学科方向
    - open_questions: 待解决的问题列表
    - iteration_count: 对话轮数

    Args:
        history: 对话历史列表，每项形如 {role, content, proposal?}。

    Returns:
        结构化状态字典。
    """
    state = {
        "selected_topic": None,
        "confirmed_methods": [],
        "confirmed_discipline": None,
        "open_questions": [],
        "iteration_count": len(history) if history else 0,
    }

    if not history or not isinstance(history, list):
        return state

    # 遍历历史，按关键词提取状态槽
    for msg in history:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, str) or not content:
            continue

        _extract_selected_topic(content, state)
        _extract_confirmed_methods(content, state)
        _extract_confirmed_discipline(content, state)
        _extract_open_questions(content, state)

    # 去重保持顺序
    state["confirmed_methods"] = _dedupe(state["confirmed_methods"])
    state["open_questions"] = _dedupe(state["open_questions"])

    return state


def _extract_selected_topic(content: str, state: dict) -> None:
    """从消息内容中提取已选定的论题标题（原地修改 state）。

    匹配"选定论题：xxx"、"确认论题：xxx"、"选择论题：xxx"等模式，
    分隔符（冒号）可选，以兼容"选定论题xxx"等自然语言表达。

    Args:
        content: 单条消息内容。
        state: 状态字典（原地修改）。
    """
    # 匹配 "选定论题：xxx" / "确认论题：xxx" / "选择论题：xxx"
    # 分隔符可选，兼容 "选定论题xxx" 等自然语言表达
    match = re.search(
        r"(?:选定|确认|选择)论题(?:[：:]\s*)?(.+?)(?:[\n。；;]|$)",
        content,
    )
    if match:
        topic = match.group(1).strip()
        if topic:
            state["selected_topic"] = topic


def _extract_confirmed_methods(content: str, state: dict) -> None:
    """从消息内容中提取已确认的研究方法（原地修改 state）。

    匹配"确认方法：xxx"、"研究方法：xxx"等模式，支持顿号/逗号分隔多项。

    Args:
        content: 单条消息内容。
        state: 状态字典（原地修改）。
    """
    # 匹配 "确认方法：xxx" / "研究方法：xxx" / "采用方法：xxx"
    match = re.search(
        r"(?:确认|研究|采用)方法[：:]\s*(.+?)(?:[\n。；;]|$)",
        content,
    )
    if match:
        methods_str = match.group(1).strip()
        if methods_str:
            # 支持顿号、逗号分隔
            parts = re.split(r"[、,，]", methods_str)
            for part in parts:
                part = part.strip()
                if part:
                    state["confirmed_methods"].append(part)


def _extract_confirmed_discipline(content: str, state: dict) -> None:
    """从消息内容中提取已确认的学科方向（原地修改 state）。

    匹配"确认学科：xxx"、"学科方向：xxx"等模式。

    Args:
        content: 单条消息内容。
        state: 状态字典（原地修改）。
    """
    # 匹配 "确认学科：xxx" / "学科方向：xxx" / "选定学科：xxx"
    match = re.search(
        r"(?:确认|选定|选择)学科(?:方向)?[：:]\s*(.+?)(?:[\n。；;]|$)",
        content,
    )
    if match:
        discipline = match.group(1).strip()
        if discipline:
            state["confirmed_discipline"] = discipline


def _extract_open_questions(content: str, state: dict) -> None:
    """从消息内容中提取待解决的问题（原地修改 state）。

    匹配问号结尾的句子，或"待解决问题：xxx"模式。

    Args:
        content: 单条消息内容。
        state: 状态字典（原地修改）。
    """
    # 匹配 "待解决问题：xxx" / "未解决：xxx"
    match = re.search(
        r"(?:待解决问题|未解决|疑问)[：:]\s*(.+?)(?:[\n。；;]|$)",
        content,
    )
    if match:
        question = match.group(1).strip()
        if question:
            state["open_questions"].append(question)
        return

    # 匹配问号结尾的句子（仅 user 角色提问）
    # 按句号/换行分割后取以问号结尾的片段
    sentences = re.split(r"[。\n！!？?]", content)
    for sentence in sentences:
        sentence = sentence.strip()
        # 句子以问号结尾或包含疑问词
        if sentence and (
            sentence.endswith("?") or sentence.endswith("？")
            or _has_question_marker(sentence)
        ):
            # 去掉末尾问号
            cleaned = sentence.rstrip("？?").strip()
            if cleaned:
                state["open_questions"].append(cleaned)


def _has_question_marker(sentence: str) -> bool:
    """判断句子是否包含中文疑问词。

    Args:
        sentence: 待判断的句子。

    Returns:
        包含疑问词返回 True，否则 False。
    """
    markers = ["如何", "怎么", "为什么", "是否", "能否", "能不能", "什么", "哪些", "多少"]
    return any(marker in sentence for marker in markers)


def _dedupe(items: list) -> list:
    """对列表去重并保持原始顺序。

    Args:
        items: 待去重的列表。

    Returns:
        去重后的新列表。
    """
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
