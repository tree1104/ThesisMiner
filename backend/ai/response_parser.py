"""AI 响应解析器

解析结构化 AI 响应，提取 JSON、Markdown、引用等内容。
提供响应验证、错误恢复、格式标准化能力。

核心组件：
    - ResponseParser: 响应解析器主类
    - JSONExtractor: JSON 提取器（容错解析）
    - MarkdownParser: Markdown 解析器
    - CitationExtractor: 引用提取器
    - ResponseValidator: 响应验证器
    - ResponseNormalizer: 响应格式标准化器

支持的响应格式：
    - 纯 JSON
    - 代码块包裹的 JSON（```json ... ```）
    - Markdown 文本（含标题、列表、代码块）
    - 混合格式（JSON + Markdown 说明）
    - 流式分块响应
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional


# ===== 响应类型枚举 =====

RESPONSE_TYPES = {
    "json": "JSON 格式响应",
    "markdown": "Markdown 格式响应",
    "text": "纯文本响应",
    "mixed": "混合格式响应",
    "error": "错误响应",
    "empty": "空响应",
}


@dataclass
class ParsedResponse:
    """解析后的响应

    封装解析结果，包含类型、内容、元数据与错误信息。
    """
    type: str = "text"
    content: Any = None
    raw: str = ""
    json_data: Optional[dict] = None
    markdown: str = ""
    text: str = ""
    citations: list = field(default_factory=list)
    code_blocks: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    is_valid: bool = True

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "type": self.type,
            "content": self.content,
            "json_data": self.json_data,
            "markdown": self.markdown,
            "text": self.text,
            "citations": self.citations,
            "code_blocks": self.code_blocks,
            "metadata": self.metadata,
            "errors": self.errors,
            "is_valid": self.is_valid,
        }


# ===== JSON 提取器 =====


class JSONExtractor:
    """JSON 提取器

    从各种格式中提取 JSON 对象，支持容错解析。
    """

    # 代码块包裹的 JSON 正则
    CODE_BLOCK_PATTERN = re.compile(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```",
        re.DOTALL | re.IGNORECASE,
    )

    # 裸 JSON 对象正则（贪婪匹配最外层花括号）
    JSON_OBJECT_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)

    # 裸 JSON 数组正则
    JSON_ARRAY_PATTERN = re.compile(r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]", re.DOTALL)

    @classmethod
    def extract(cls, text: str) -> Optional[dict]:
        """从文本中提取 JSON 对象。

        按优先级尝试：
            1. 直接解析（文本本身就是 JSON）
            2. 从代码块提取
            3. 从裸 JSON 提取

        Args:
            text: 原始文本。

        Returns:
            解析后的字典，失败返回 None。
        """
        if not text:
            return None

        # 1. 直接解析
        result = cls._try_parse_json(text.strip())
        if result is not None:
            return result

        # 2. 从代码块提取
        result = cls._extract_from_code_block(text)
        if result is not None:
            return result

        # 3. 从裸 JSON 提取
        result = cls._extract_bare_json(text)
        if result is not None:
            return result

        return None

    @classmethod
    def extract_list(cls, text: str) -> Optional[list]:
        """从文本中提取 JSON 数组。"""
        if not text:
            return None

        # 直接解析
        try:
            data = json.loads(text.strip())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

        # 从代码块提取
        for match in cls.CODE_BLOCK_PATTERN.finditer(text):
            block = match.group(1).strip()
            try:
                data = json.loads(block)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                continue

        # 裸数组提取
        for match in cls.JSON_ARRAY_PATTERN.finditer(text):
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                continue

        return None

    @classmethod
    def _try_parse_json(cls, text: str) -> Optional[dict]:
        """尝试直接解析 JSON。"""
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return None

    @classmethod
    def _extract_from_code_block(cls, text: str) -> Optional[dict]:
        """从代码块提取 JSON。"""
        for match in cls.CODE_BLOCK_PATTERN.finditer(text):
            block = match.group(1).strip()
            # 直接解析
            try:
                data = json.loads(block)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                # 尝试修复常见 JSON 错误
                fixed = cls._fix_json(block)
                if fixed:
                    try:
                        data = json.loads(fixed)
                        if isinstance(data, dict):
                            return data
                    except json.JSONDecodeError:
                        continue
        return None

    @classmethod
    def _extract_bare_json(cls, text: str) -> Optional[dict]:
        """提取裸 JSON。"""
        for match in cls.JSON_OBJECT_PATTERN.finditer(text):
            candidate = match.group(0)
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                fixed = cls._fix_json(candidate)
                if fixed:
                    try:
                        data = json.loads(fixed)
                        if isinstance(data, dict):
                            return data
                    except json.JSONDecodeError:
                        continue
        return None

    @classmethod
    def _fix_json(cls, text: str) -> Optional[str]:
        """尝试修复常见 JSON 格式错误。

        修复项：
            - 尾部多余逗号
            - 单引号替换为双引号
            - 未引用的键
            - 尾部注释
        """
        if not text:
            return None

        fixed = text

        # 移除尾部注释
        fixed = re.sub(r"//.*?$", "", fixed, flags=re.MULTILINE)
        fixed = re.sub(r"/\*.*?\*/", "", fixed, flags=re.DOTALL)

        # 移除尾部多余逗号
        fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

        # 单引号替换为双引号（仅在键值位置）
        # 注意：这会破坏包含单引号的字符串值，但作为容错手段可接受
        try:
            # 尝试解析单引号 JSON
            import ast
            data = ast.literal_eval(fixed)
            if isinstance(data, dict):
                return json.dumps(data, ensure_ascii=False)
        except (ValueError, SyntaxError):
            pass

        # 未引用的键：{key: value} -> {"key": value}
        fixed = re.sub(r"(\w+)\s*:", r'"\1":', fixed)

        return fixed

    @classmethod
    def extract_all_json_blocks(cls, text: str) -> list:
        """提取文本中所有 JSON 代码块。

        Args:
            text: 原始文本。

        Returns:
            JSON 字典列表。
        """
        results = []
        for match in cls.CODE_BLOCK_PATTERN.finditer(text):
            block = match.group(1).strip()
            try:
                data = json.loads(block)
                results.append(data)
            except json.JSONDecodeError:
                fixed = cls._fix_json(block)
                if fixed:
                    try:
                        data = json.loads(fixed)
                        results.append(data)
                    except json.JSONDecodeError:
                        continue
        return results


# ===== Markdown 解析器 =====


class MarkdownParser:
    """Markdown 解析器

    解析 Markdown 文本，提取标题、列表、代码块、链接等结构。
    """

    # 标题正则
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    # 代码块正则
    CODE_BLOCK_PATTERN = re.compile(
        r"```(\w*)\s*\n(.*?)\n```",
        re.DOTALL,
    )

    # 链接正则
    LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    # 图片正则
    IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    # 无序列表项正则
    UNORDERED_LIST_PATTERN = re.compile(r"^[\s]*[-*+]\s+(.+)$", re.MULTILINE)

    # 有序列表项正则
    ORDERED_LIST_PATTERN = re.compile(r"^[\s]*\d+\.\s+(.+)$", re.MULTILINE)

    # 引用块正则
    BLOCKQUOTE_PATTERN = re.compile(r"^>\s+(.+)$", re.MULTILINE)

    # 表格行正则
    TABLE_ROW_PATTERN = re.compile(r"^\|(.+)\|$", re.MULTILINE)

    # 水平分割线正则
    HR_PATTERN = re.compile(r"^---+$|^\*\*\*+$|^___+$", re.MULTILINE)

    @classmethod
    def extract_headings(cls, text: str) -> list:
        """提取所有标题。

        Returns:
            标题列表，每项为 {"level": int, "text": str}。
        """
        if not text:
            return []
        headings = []
        for match in cls.HEADING_PATTERN.finditer(text):
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            headings.append({"level": level, "text": heading_text})
        return headings

    @classmethod
    def extract_code_blocks(cls, text: str) -> list:
        """提取所有代码块。

        Returns:
            代码块列表，每项为 {"language": str, "code": str}。
        """
        if not text:
            return []
        blocks = []
        for match in cls.CODE_BLOCK_PATTERN.finditer(text):
            language = match.group(1) or "text"
            code = match.group(2)
            blocks.append({"language": language, "code": code})
        return blocks

    @classmethod
    def extract_links(cls, text: str) -> list:
        """提取所有链接。

        Returns:
            链接列表，每项为 {"text": str, "url": str}。
        """
        if not text:
            return []
        links = []
        for match in cls.LINK_PATTERN.finditer(text):
            # 排除图片（以 ! 开头）
            start = match.start()
            if start > 0 and text[start - 1] == "!":
                continue
            links.append({"text": match.group(1), "url": match.group(2)})
        return links

    @classmethod
    def extract_images(cls, text: str) -> list:
        """提取所有图片。"""
        if not text:
            return []
        images = []
        for match in cls.IMAGE_PATTERN.finditer(text):
            images.append({"alt": match.group(1), "url": match.group(2)})
        return images

    @classmethod
    def extract_lists(cls, text: str) -> dict:
        """提取列表（有序与无序）。

        Returns:
            {"ordered": [...], "unordered": [...]}
        """
        if not text:
            return {"ordered": [], "unordered": []}
        ordered = [
            match.group(1).strip()
            for match in cls.ORDERED_LIST_PATTERN.finditer(text)
        ]
        unordered = [
            match.group(1).strip()
            for match in cls.UNORDERED_LIST_PATTERN.finditer(text)
        ]
        return {"ordered": ordered, "unordered": unordered}

    @classmethod
    def extract_blockquotes(cls, text: str) -> list:
        """提取引用块。"""
        if not text:
            return []
        return [
            match.group(1).strip()
            for match in cls.BLOCKQUOTE_PATTERN.finditer(text)
        ]

    @classmethod
    def extract_tables(cls, text: str) -> list:
        """提取表格。

        Returns:
            表格列表，每项为 {"headers": [...], "rows": [[...], ...]}。
        """
        if not text:
            return []
        tables = []
        rows = cls.TABLE_ROW_PATTERN.findall(text)
        if not rows:
            return tables

        # 按连续行分组
        current_table_rows = []
        prev_end = 0
        for match in cls.TABLE_ROW_PATTERN.finditer(text):
            if match.start() > prev_end + 2 and current_table_rows:
                # 表格中断
                tables.append(cls._parse_table_rows(current_table_rows))
                current_table_rows = []
            current_table_rows.append(match.group(1))
            prev_end = match.end()

        if current_table_rows:
            tables.append(cls._parse_table_rows(current_table_rows))

        return tables

    @classmethod
    def _parse_table_rows(cls, rows: list) -> dict:
        """解析表格行。"""
        if not rows:
            return {"headers": [], "rows": []}
        # 第一行为表头
        headers = [cell.strip() for cell in rows[0].split("|")]
        # 跳过分隔行（---）
        data_rows = []
        for row in rows[1:]:
            cells = [cell.strip() for cell in row.split("|")]
            # 跳过分隔行
            if all(re.match(r"^[-:\s]+$", cell) for cell in cells):
                continue
            data_rows.append(cells)
        return {"headers": headers, "rows": data_rows}

    @classmethod
    def to_plain_text(cls, text: str) -> str:
        """将 Markdown 转为纯文本（移除格式标记）。"""
        if not text:
            return ""
        result = text
        # 移除代码块
        result = cls.CODE_BLOCK_PATTERN.sub(r"\2", result)
        # 移除标题标记
        result = cls.HEADING_PATTERN.sub(r"\2", result)
        # 移除链接，保留文本
        result = cls.LINK_PATTERN.sub(r"\1", result)
        # 移除图片
        result = cls.IMAGE_PATTERN.sub(r"\1", result)
        # 移除加粗/斜体
        result = re.sub(r"\*\*(.+?)\*\*", r"\1", result)
        result = re.sub(r"\*(.+?)\*", r"\1", result)
        result = re.sub(r"__(.+?)__", r"\1", result)
        result = re.sub(r"_(.+?)_", r"\1", result)
        result = re.sub(r"`(.+?)`", r"\1", result)
        # 移除引用标记
        result = re.sub(r"^>\s+", "", result, flags=re.MULTILINE)
        # 移除列表标记
        result = cls.UNORDERED_LIST_PATTERN.sub(r"\1", result)
        result = cls.ORDERED_LIST_PATTERN.sub(r"\1", result)
        return result

    @classmethod
    def get_structure(cls, text: str) -> dict:
        """获取 Markdown 文档结构概要。"""
        return {
            "headings": cls.extract_headings(text),
            "code_blocks": cls.extract_code_blocks(text),
            "links": cls.extract_links(text),
            "images": cls.extract_images(text),
            "lists": cls.extract_lists(text),
            "blockquotes": cls.extract_blockquotes(text),
            "tables": cls.extract_tables(text),
        }


# ===== 引用提取器 =====


class CitationExtractor:
    """引用提取器

    从文本中提取学术引用，支持多种引用格式。
    """

    # 数字引用 [1] [2] 等
    NUMERIC_CITATION_PATTERN = re.compile(r"\[(\d+)\]")

    # 作者-年份引用 (Author, 2020) 或 (Author et al., 2020)
    AUTHOR_YEAR_PATTERN = re.compile(
        r"\(([A-Z][a-zA-Z]+(?:\s+(?:et al\.|and|&)\s+[A-Z][a-zA-Z]+)*),\s*(\d{4})\)"
    )

    # 上标引用 Author^1 或 Author¹
    SUPERSCRIPT_PATTERN = re.compile(r"\^(\d+)")

    # DOI 引用
    DOI_PATTERN = re.compile(r"10\.\d{4,}/[^\s]+")

    # arXiv 引用
    ARXIV_PATTERN = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)

    # URL 引用
    URL_PATTERN = re.compile(r"https?://[^\s)]+")

    @classmethod
    def extract_all(cls, text: str) -> list:
        """提取所有引用。

        Returns:
            引用列表，每项为 {"type": str, "value": str, "position": int}。
        """
        if not text:
            return []
        citations = []

        # 数字引用
        for match in cls.NUMERIC_CITATION_PATTERN.finditer(text):
            citations.append({
                "type": "numeric",
                "value": match.group(1),
                "position": match.start(),
            })

        # 作者-年份引用
        for match in cls.AUTHOR_YEAR_PATTERN.finditer(text):
            citations.append({
                "type": "author_year",
                "value": f"{match.group(1)}, {match.group(2)}",
                "author": match.group(1),
                "year": match.group(2),
                "position": match.start(),
            })

        # DOI 引用
        for match in cls.DOI_PATTERN.finditer(text):
            citations.append({
                "type": "doi",
                "value": match.group(0),
                "position": match.start(),
            })

        # arXiv 引用
        for match in cls.ARXIV_PATTERN.finditer(text):
            citations.append({
                "type": "arxiv",
                "value": match.group(1),
                "position": match.start(),
            })

        # URL 引用
        for match in cls.URL_PATTERN.finditer(text):
            citations.append({
                "type": "url",
                "value": match.group(0),
                "position": match.start(),
            })

        return citations

    @classmethod
    def extract_numeric(cls, text: str) -> list:
        """提取数字引用 [1] [2]。"""
        if not text:
            return []
        return [
            int(match.group(1))
            for match in cls.NUMERIC_CITATION_PATTERN.finditer(text)
        ]

    @classmethod
    def extract_author_year(cls, text: str) -> list:
        """提取作者-年份引用。"""
        if not text:
            return []
        results = []
        for match in cls.AUTHOR_YEAR_PATTERN.finditer(text):
            results.append({
                "author": match.group(1),
                "year": match.group(2),
                "raw": match.group(0),
            })
        return results

    @classmethod
    def extract_dois(cls, text: str) -> list:
        """提取 DOI。"""
        if not text:
            return []
        return cls.DOI_PATTERN.findall(text)

    @classmethod
    def extract_arxiv_ids(cls, text: str) -> list:
        """提取 arXiv ID。"""
        if not text:
            return []
        return cls.ARXIV_PATTERN.findall(text)

    @classmethod
    def extract_urls(cls, text: str) -> list:
        """提取 URL。"""
        if not text:
            return []
        return cls.URL_PATTERN.findall(text)

    @classmethod
    def deduplicate(cls, citations: list) -> list:
        """引用去重。"""
        seen = set()
        unique = []
        for cite in citations:
            key = f"{cite['type']}:{cite['value']}"
            if key not in seen:
                seen.add(key)
                unique.append(cite)
        return unique


# ===== 响应验证器 =====


class ResponseValidator:
    """响应验证器

    验证 AI 响应是否符合预期结构与质量。
    """

    @staticmethod
    def validate_json_response(data: dict, required_fields: list) -> dict:
        """验证 JSON 响应的必填字段。

        Args:
            data: 解析后的 JSON 字典。
            required_fields: 必填字段列表。

        Returns:
            {"valid": bool, "missing": [...], "errors": [...]}
        """
        if not isinstance(data, dict):
            return {"valid": False, "missing": required_fields, "errors": ["响应不是有效 JSON 对象"]}

        missing = [f for f in required_fields if f not in data or data[f] is None]
        errors = []
        for field_name in missing:
            errors.append(f"缺少必填字段: {field_name}")

        return {
            "valid": len(missing) == 0,
            "missing": missing,
            "errors": errors,
        }

    @staticmethod
    def validate_field_type(data: dict, field_specs: dict) -> dict:
        """验证字段类型。

        Args:
            data: 数据字典。
            field_specs: 字段规格 {field_name: expected_type}。

        Returns:
            {"valid": bool, "errors": [...]}
        """
        errors = []
        for field_name, expected_type in field_specs.items():
            if field_name in data:
                value = data[field_name]
                if value is not None and not isinstance(value, expected_type):
                    actual_type = type(value).__name__
                    errors.append(
                        f"字段 '{field_name}' 类型错误，期望 {expected_type.__name__}，实际 {actual_type}"
                    )
        return {"valid": len(errors) == 0, "errors": errors}

    @staticmethod
    def validate_field_length(data: dict, length_specs: dict) -> dict:
        """验证字段长度。

        Args:
            data: 数据字典。
            length_specs: {field_name: (min_len, max_len)}。

        Returns:
            {"valid": bool, "errors": [...]}
        """
        errors = []
        for field_name, (min_len, max_len) in length_specs.items():
            if field_name in data and data[field_name] is not None:
                value = data[field_name]
                length = len(value) if isinstance(value, (str, list, dict)) else 0
                if min_len and length < min_len:
                    errors.append(f"字段 '{field_name}' 长度不足，最小 {min_len}，实际 {length}")
                if max_len and length > max_len:
                    errors.append(f"字段 '{field_name}' 长度超限，最大 {max_len}，实际 {length}")
        return {"valid": len(errors) == 0, "errors": errors}

    @staticmethod
    def validate_not_empty(text: str, min_length: int = 1) -> bool:
        """验证文本非空。"""
        return bool(text and len(text.strip()) >= min_length)

    @staticmethod
    def validate_json_structure(data: dict, schema: dict) -> dict:
        """验证 JSON 结构是否符合 schema（简化版）。

        Args:
            data: 待验证数据。
            schema: schema 定义 {field: {type, required, min, max, items}}。

        Returns:
            {"valid": bool, "errors": [...]}
        """
        errors = []
        for field_name, spec in schema.items():
            required = spec.get("required", False)
            expected_type = spec.get("type")
            min_val = spec.get("min")
            max_val = spec.get("max")

            if field_name not in data:
                if required:
                    errors.append(f"缺少必填字段: {field_name}")
                continue

            value = data[field_name]
            if value is None:
                if required:
                    errors.append(f"字段 '{field_name}' 为 None")
                continue

            if expected_type and not isinstance(value, expected_type):
                errors.append(
                    f"字段 '{field_name}' 类型错误，期望 {expected_type.__name__}"
                )
                continue

            if isinstance(value, (int, float)):
                if min_val is not None and value < min_val:
                    errors.append(f"字段 '{field_name}' 值 {value} 小于最小值 {min_val}")
                if max_val is not None and value > max_val:
                    errors.append(f"字段 '{field_name}' 值 {value} 大于最大值 {max_val}")

            if isinstance(value, (str, list)):
                length = len(value)
                if min_val is not None and length < min_val:
                    errors.append(f"字段 '{field_name}' 长度 {length} 小于最小 {min_val}")
                if max_val is not None and length > max_val:
                    errors.append(f"字段 '{field_name}' 长度 {length} 大于最大 {max_val}")

        return {"valid": len(errors) == 0, "errors": errors}


# ===== 响应标准化器 =====


class ResponseNormalizer:
    """响应格式标准化器

    将不同格式的 AI 响应标准化为统一结构。
    """

    @staticmethod
    def normalize_proposal(data: dict) -> dict:
        """标准化论题提案响应。

        确保包含所有必填字段，缺失字段填充默认值。
        """
        normalized = {
            "title": data.get("title", "").strip(),
            "problem_awareness": data.get("problem_awareness", data.get("problem", "")).strip(),
            "research_significance": data.get("research_significance", data.get("significance", "")),
            "literature_review": data.get("literature_review", data.get("literature", "")),
            "differentiation": data.get("differentiation", data.get("innovation", "")),
            "research_content": data.get("research_content", data.get("content", [])),
            "feasibility": data.get("feasibility", {}),
            "confidence_score": float(data.get("confidence_score", data.get("confidence", 0.5))),
            "inspiration_source": data.get("inspiration_source", data.get("source", "")),
        }

        # 确保 research_content 为列表
        if isinstance(normalized["research_content"], str):
            normalized["research_content"] = [normalized["research_content"]]
        elif not isinstance(normalized["research_content"], list):
            normalized["research_content"] = []

        # 确保 research_significance 为字典
        if isinstance(normalized["research_significance"], str):
            normalized["research_significance"] = {
                "theoretical": normalized["research_significance"],
                "practical": "",
            }
        elif not isinstance(normalized["research_significance"], dict):
            normalized["research_significance"] = {
                "theoretical": str(normalized["research_significance"]),
                "practical": "",
            }

        # 确保可行性分析为字典
        if not isinstance(normalized["feasibility"], dict):
            normalized["feasibility"] = {
                "time": "",
                "resources": "",
                "methodology": "",
            }

        # 置信度范围校验
        score = normalized["confidence_score"]
        if score < 0:
            score = 0.0
        elif score > 1:
            score = score / 100 if score > 1 else 1.0
        normalized["confidence_score"] = round(score, 2)

        return normalized

    @staticmethod
    def normalize_candidates(data: dict) -> list:
        """标准化候选论题列表响应。"""
        candidates = data.get("candidates", data.get("topics", []))
        if not isinstance(candidates, list):
            return []

        normalized = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            normalized.append({
                "title": candidate.get("title", "").strip(),
                "direction": candidate.get("direction", "").strip(),
                "suggestion": candidate.get("suggestion", candidate.get("description", "")).strip(),
                "source": candidate.get("source", candidate.get("inspiration_source", "")),
                "keywords": candidate.get("keywords", []),
            })
        return normalized

    @staticmethod
    def normalize_evaluation(data: dict) -> dict:
        """标准化评估响应。"""
        return {
            "score": float(data.get("score", 0)),
            "novelty": float(data.get("novelty", 0)),
            "feasibility": float(data.get("feasibility", 0)),
            "significance": float(data.get("significance", 0)),
            "strengths": data.get("strengths", []) if isinstance(data.get("strengths"), list) else [],
            "weaknesses": data.get("weaknesses", []) if isinstance(data.get("weaknesses"), list) else [],
            "suggestions": data.get("suggestions", []) if isinstance(data.get("suggestions"), list) else [],
            "overall_comment": data.get("overall_comment", data.get("comment", "")).strip(),
        }

    @staticmethod
    def normalize_search_results(data: dict) -> dict:
        """标准化文献检索结果。"""
        papers = data.get("papers", data.get("results", []))
        if not isinstance(papers, list):
            papers = []

        normalized_papers = []
        for paper in papers:
            if not isinstance(paper, dict):
                continue
            normalized_papers.append({
                "title": paper.get("title", "").strip(),
                "authors": paper.get("authors", []) if isinstance(paper.get("authors"), list) else [],
                "year": int(paper.get("year", 0)) if paper.get("year") else 0,
                "abstract": paper.get("abstract", "").strip(),
                "url": paper.get("url", "").strip(),
                "doi": paper.get("doi", "").strip(),
                "source": paper.get("source", "").strip(),
                "citations": int(paper.get("citations", 0)) if paper.get("citations") else 0,
            })

        return {
            "papers": normalized_papers,
            "total": len(normalized_papers),
            "query": data.get("query", "").strip(),
            "degraded": bool(data.get("degraded", False)),
        }


# ===== 响应解析器主类 =====


class ResponseParser:
    """响应解析器主类

    整合 JSON 提取、Markdown 解析、引用提取、验证与标准化能力。
    """

    def __init__(self):
        self.json_extractor = JSONExtractor()
        self.markdown_parser = MarkdownParser()
        self.citation_extractor = CitationExtractor()
        self.validator = ResponseValidator()
        self.normalizer = ResponseNormalizer()

    def parse(self, text: str, expected_type: str = "auto") -> ParsedResponse:
        """解析 AI 响应。

        Args:
            text: 原始响应文本。
            expected_type: 期望类型（auto/json/markdown/text）。

        Returns:
            ParsedResponse 实例。
        """
        result = ParsedResponse(raw=text or "")

        if not text or not text.strip():
            result.type = "empty"
            result.is_valid = False
            result.errors.append("响应为空")
            return result

        # 自动检测类型
        if expected_type == "auto":
            expected_type = self._detect_type(text)

        result.type = expected_type

        if expected_type == "json":
            self._parse_json(text, result)
        elif expected_type == "markdown":
            self._parse_markdown(text, result)
        elif expected_type == "mixed":
            self._parse_mixed(text, result)
        else:
            result.text = text.strip()
            result.content = text.strip()

        # 提取引用（所有类型都提取）
        result.citations = self.citation_extractor.extract_all(text)

        # 提取代码块（所有类型都提取）
        result.code_blocks = self.markdown_parser.extract_code_blocks(text)

        return result

    def _detect_type(self, text: str) -> str:
        """自动检测响应类型。"""
        stripped = text.strip()

        # 纯 JSON
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                json.loads(stripped)
                return "json"
            except json.JSONDecodeError:
                pass

        # 代码块包裹的 JSON
        if stripped.startswith("```json") or stripped.startswith("```"):
            json_blocks = self.json_extractor.extract_all_json_blocks(text)
            if json_blocks:
                return "json"

        # Markdown 特征
        md_features = [
            self.markdown_parser.HEADING_PATTERN.search(text),
            self.markdown_parser.CODE_BLOCK_PATTERN.search(text),
            self.markdown_parser.UNORDERED_LIST_PATTERN.search(text),
            self.markdown_parser.ORDERED_LIST_PATTERN.search(text),
        ]
        if any(md_features):
            # 检查是否同时含 JSON
            if self.json_extractor.extract(text):
                return "mixed"
            return "markdown"

        return "text"

    def _parse_json(self, text: str, result: ParsedResponse) -> None:
        """解析 JSON 响应。"""
        data = self.json_extractor.extract(text)
        if data is None:
            result.is_valid = False
            result.errors.append("JSON 解析失败")
            result.text = text.strip()
            result.content = text.strip()
            return

        result.json_data = data
        result.content = data
        result.text = text.strip()

    def _parse_markdown(self, text: str, result: ParsedResponse) -> None:
        """解析 Markdown 响应。"""
        result.markdown = text.strip()
        result.text = self.markdown_parser.to_plain_text(text)
        result.content = result.text
        result.metadata["structure"] = self.markdown_parser.get_structure(text)

    def _parse_mixed(self, text: str, result: ParsedResponse) -> None:
        """解析混合格式响应。"""
        # 提取 JSON
        data = self.json_extractor.extract(text)
        result.json_data = data

        # 提取 Markdown
        result.markdown = text.strip()
        result.text = self.markdown_parser.to_plain_text(text)
        result.content = data if data else result.text
        result.metadata["structure"] = self.markdown_parser.get_structure(text)

    def parse_json(self, text: str) -> Optional[dict]:
        """便捷方法：解析 JSON 响应。"""
        return self.json_extractor.extract(text)

    def parse_json_list(self, text: str) -> Optional[list]:
        """便捷方法：解析 JSON 数组响应。"""
        return self.json_extractor.extract_list(text)

    def parse_markdown(self, text: str) -> dict:
        """便捷方法：解析 Markdown 响应，返回结构。"""
        return self.markdown_parser.get_structure(text)

    def parse_proposal(self, text: str) -> dict:
        """便捷方法：解析论题提案响应并标准化。"""
        data = self.json_extractor.extract(text)
        if data is None:
            return {}
        return self.normalizer.normalize_proposal(data)

    def parse_candidates(self, text: str) -> list:
        """便捷方法：解析候选论题列表并标准化。"""
        data = self.json_extractor.extract(text)
        if data is None:
            return []
        return self.normalizer.normalize_candidates(data)

    def parse_evaluation(self, text: str) -> dict:
        """便捷方法：解析评估响应并标准化。"""
        data = self.json_extractor.extract(text)
        if data is None:
            return {}
        return self.normalizer.normalize_evaluation(data)

    def parse_search_results(self, text: str) -> dict:
        """便捷方法：解析文献检索结果并标准化。"""
        data = self.json_extractor.extract(text)
        if data is None:
            return {"papers": [], "total": 0}
        return self.normalizer.normalize_search_results(data)

    def extract_citations(self, text: str) -> list:
        """便捷方法：提取引用。"""
        return self.citation_extractor.extract_all(text)

    def validate_response(self, text: str, required_fields: list) -> dict:
        """便捷方法：验证响应。"""
        data = self.json_extractor.extract(text)
        if data is None:
            return {"valid": False, "missing": required_fields, "errors": ["JSON 解析失败"]}
        return self.validator.validate_json_response(data, required_fields)


# ===== 全局实例 =====

_default_parser = ResponseParser()


def get_parser() -> ResponseParser:
    """获取默认响应解析器。"""
    return _default_parser


def parse_response(text: str, expected_type: str = "auto") -> ParsedResponse:
    """便捷函数：解析响应。"""
    return _default_parser.parse(text, expected_type=expected_type)


def extract_json(text: str) -> Optional[dict]:
    """便捷函数：提取 JSON。"""
    return JSONExtractor.extract(text)


def extract_citations(text: str) -> list:
    """便捷函数：提取引用。"""
    return CitationExtractor.extract_all(text)


def parse_markdown(text: str) -> dict:
    """便捷函数：解析 Markdown 结构。"""
    return MarkdownParser.get_structure(text)


def validate_json_response(data: dict, required_fields: list) -> dict:
    """便捷函数：验证 JSON 响应。"""
    return ResponseValidator.validate_json_response(data, required_fields)


def normalize_proposal(data: dict) -> dict:
    """便捷函数：标准化论题提案。"""
    return ResponseNormalizer.normalize_proposal(data)
