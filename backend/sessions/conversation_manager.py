"""对话管理器 - 支持多对话并存与上下文隔离

每个 session 下可有多条独立对话线（conversation），
每条对话有独立的上下文窗口与消息历史，互不干扰。
"""
import json
import uuid
from typing import Optional

from backend.database import get_db_connection


class ConversationManager:
    """对话管理器"""

    def create_conversation(
        self,
        session_id: str,
        title: str = "新对话",
        agent_id: str = "orchestrator",
    ) -> dict:
        """创建新对话

        Args:
            session_id: 所属会话 ID。
            title: 对话标题，默认"新对话"。
            agent_id: 默认 Agent ID，默认"orchestrator"。

        Returns:
            新建的对话字典（含 message_count）。
        """
        conv_id = str(uuid.uuid4())
        conn = get_db_connection()
        try:
            conn.execute(
                """INSERT INTO conversations (id, session_id, title, agent_id, status)
                   VALUES (?, ?, ?, ?, 'active')""",
                (conv_id, session_id, title, agent_id),
            )
            # 更新 session 的 active_conversation_id
            conn.execute(
                "UPDATE sessions SET active_conversation_id = ? WHERE id = ?",
                (conv_id, session_id),
            )
            conn.commit()
            return self.get_conversation(conv_id)
        finally:
            conn.close()

    def list_conversations(self, session_id: str) -> list[dict]:
        """列出会话下的所有对话

        Args:
            session_id: 会话 ID。

        Returns:
            对话字典列表，按 updated_at 降序排列，每项含 message_count。
        """
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """SELECT c.*,
                   (SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = c.id) as message_count
                   FROM conversations c
                   WHERE c.session_id = ?
                   ORDER BY c.updated_at DESC""",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_conversation(self, conversation_id: str) -> Optional[dict]:
        """获取对话详情

        Args:
            conversation_id: 对话 ID。

        Returns:
            对话字典（含 message_count），不存在时返回 None。
        """
        conn = get_db_connection()
        try:
            row = conn.execute(
                """SELECT c.*,
                   (SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = c.id) as message_count
                   FROM conversations c
                   WHERE c.id = ?""",
                (conversation_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话（级联删除消息与引用）

        Args:
            conversation_id: 对话 ID。

        Returns:
            是否删除成功（受影响行数 > 0）。
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def rename_conversation(self, conversation_id: str, title: str) -> Optional[dict]:
        """重命名对话

        Args:
            conversation_id: 对话 ID。
            title: 新标题。

        Returns:
            更新后的对话字典，不存在时返回 None。
        """
        conn = get_db_connection()
        try:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
                (title, conversation_id),
            )
            conn.commit()
            return self.get_conversation(conversation_id)
        finally:
            conn.close()

    def set_active(self, session_id: str, conversation_id: str) -> bool:
        """设置会话的激活对话

        Args:
            session_id: 会话 ID。
            conversation_id: 要激活的对话 ID。

        Returns:
            是否设置成功。
        """
        conn = get_db_connection()
        try:
            conn.execute(
                "UPDATE sessions SET active_conversation_id = ? WHERE id = ?",
                (conversation_id, session_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        agent_id: str = "",
        reasoning: str = "",
        search_results: list = None,
        token_usage: dict = None,
        citations: list = None,
    ) -> dict:
        """添加消息到对话

        Args:
            conversation_id: 对话 ID。
            role: 消息角色（user/assistant/system）。
            content: 消息内容。
            agent_id: 产生该消息的 Agent ID。
            reasoning: 推理过程文本。
            search_results: 搜索结果列表，将以 JSON 存储。
            token_usage: token 用量字典，将以 JSON 存储。
            citations: 引用列表，每项含 url/title/snippet/source_domain/favicon。

        Returns:
            新建的消息字典（含解析后的 search_results 与 token_usage）。
        """
        msg_id = str(uuid.uuid4())
        conn = get_db_connection()
        try:
            conn.execute(
                """INSERT INTO conversation_messages
                   (id, conversation_id, agent_id, role, content, reasoning, search_results_json, token_usage_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg_id,
                    conversation_id,
                    agent_id,
                    role,
                    content,
                    reasoning,
                    json.dumps(search_results or [], ensure_ascii=False),
                    json.dumps(token_usage or {}, ensure_ascii=False),
                ),
            )
            # 写入引用
            if citations:
                for cite in citations:
                    cite_id = str(uuid.uuid4())
                    conn.execute(
                        """INSERT INTO search_citations
                           (id, message_id, url, title, snippet, source_domain, favicon)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            cite_id,
                            msg_id,
                            cite.get("url", ""),
                            cite.get("title", ""),
                            cite.get("snippet", ""),
                            cite.get("source_domain", ""),
                            cite.get("favicon", ""),
                        ),
                    )
            # 更新对话的 updated_at
            conn.execute(
                "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
                (conversation_id,),
            )
            conn.commit()
            return self.get_message(msg_id)
        finally:
            conn.close()

    def get_message(self, message_id: str) -> Optional[dict]:
        """获取单条消息

        Args:
            message_id: 消息 ID。

        Returns:
            消息字典（search_results/token_usage 已反序列化），不存在时返回 None。
        """
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT * FROM conversation_messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if row:
                msg = dict(row)
                if msg.get("search_results_json"):
                    msg["search_results"] = json.loads(msg["search_results_json"])
                if msg.get("token_usage_json"):
                    msg["token_usage"] = json.loads(msg["token_usage_json"])
                return msg
            return None
        finally:
            conn.close()

    def get_messages(self, conversation_id: str, limit: int = 100) -> list[dict]:
        """获取对话的所有消息

        Args:
            conversation_id: 对话 ID。
            limit: 返回条数上限，默认 100。

        Returns:
            消息字典列表，按创建时间升序排列。
        """
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """SELECT * FROM conversation_messages
                   WHERE conversation_id = ?
                   ORDER BY created_at ASC, id ASC
                   LIMIT ?""",
                (conversation_id, limit),
            ).fetchall()
            messages = []
            for row in rows:
                msg = dict(row)
                if msg.get("search_results_json"):
                    msg["search_results"] = json.loads(msg["search_results_json"])
                if msg.get("token_usage_json"):
                    msg["token_usage"] = json.loads(msg["token_usage_json"])
                messages.append(msg)
            return messages
        finally:
            conn.close()

    def get_context_window(self, conversation_id: str, max_tokens: int = 8000) -> list[dict]:
        """获取上下文窗口（使用 DST 压缩历史）

        从最近的消息向前取，直到达到 max_tokens 限制。
        超出窗口的旧消息通过 DST 压缩为摘要。

        Args:
            conversation_id: 对话 ID。
            max_tokens: 上下文窗口最大 token 数，默认 8000。

        Returns:
            上下文窗口消息列表，可能首条为 DST 历史摘要系统消息。
        """
        messages = self.get_messages(conversation_id, limit=200)
        if not messages:
            return []

        # 简单的 token 估算（4 字符 ≈ 1 token）
        def estimate_tokens(text: str) -> int:
            return len(text) // 4 if text else 0

        # 从后向前取消息
        window = []
        token_count = 0
        for msg in reversed(messages):
            msg_tokens = estimate_tokens(msg.get("content", ""))
            if token_count + msg_tokens > max_tokens:
                break
            window.insert(0, msg)
            token_count += msg_tokens

        # 如果有被截断的旧消息，生成 DST 摘要
        if len(window) < len(messages):
            try:
                from backend.sessions.dst_compactor import compact_history
                from backend.sessions.dialogue_state_tracker import extract_state

                old_messages = messages[: len(messages) - len(window)]
                # 提取旧消息的 DST 状态并压缩为摘要
                dst_state = extract_state(old_messages)
                compressed = compact_history(old_messages, dst_state)
                # compressed[0] 是 DST 状态摘要系统消息
                if compressed and compressed[0].get("role") == "system":
                    summary_msg = dict(compressed[0])
                    summary_msg["agent_id"] = "system"
                    window.insert(0, summary_msg)
            except ImportError:
                pass  # DST 模块不可用时跳过压缩

        return window

    def get_message_citations(self, message_id: str) -> list[dict]:
        """获取消息的引用

        Args:
            message_id: 消息 ID。

        Returns:
            引用字典列表，按 id 排序。
        """
        conn = get_db_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM search_citations WHERE message_id = ? ORDER BY id",
                (message_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# 单例
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """获取对话管理器单例

    Returns:
        ConversationManager 单例实例。
    """
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
