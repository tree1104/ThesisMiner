"""上下文管理器

提供多会话上下文管理、上下文切换、上下文持久化、上下文版本与差异能力。

核心组件：
    - ConversationContext: 单会话上下文
    - ContextStore: 上下文存储（内存 + 持久化）
    - ContextSwitcher: 上下文切换器
    - ContextVersionManager: 上下文版本管理
    - ContextDiff: 上下文差异比较
    - MultiContextManager: 多上下文管理器
"""
import copy
import hashlib
import json
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ConversationContext:
    """单会话上下文

    封装一个会话的完整上下文状态。
    """
    session_id: str
    user_id: str = ""
    degree: str = ""
    discipline: str = ""
    mentor_info: str = ""
    history: list = field(default_factory=list)
    candidates: list = field(default_factory=list)
    selected_topic: str = ""
    confirmed_methods: list = field(default_factory=list)
    open_questions: list = field(default_factory=list)
    stage: str = "info_confirm"
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: int = 1

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "degree": self.degree,
            "discipline": self.discipline,
            "mentor_info": self.mentor_info,
            "history": self.history,
            "candidates": self.candidates,
            "selected_topic": self.selected_topic,
            "confirmed_methods": self.confirmed_methods,
            "open_questions": self.open_questions,
            "stage": self.stage,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationContext":
        """从字典创建。"""
        return cls(
            session_id=data.get("session_id", ""),
            user_id=data.get("user_id", ""),
            degree=data.get("degree", ""),
            discipline=data.get("discipline", ""),
            mentor_info=data.get("mentor_info", ""),
            history=data.get("history", []),
            candidates=data.get("candidates", []),
            selected_topic=data.get("selected_topic", ""),
            confirmed_methods=data.get("confirmed_methods", []),
            open_questions=data.get("open_questions", []),
            stage=data.get("stage", "info_confirm"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            version=data.get("version", 1),
        )

    def add_message(self, role: str, content: str) -> None:
        """添加消息到历史。"""
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        self.updated_at = time.time()
        self.version += 1

    def add_candidate(self, candidate: dict) -> None:
        """添加候选论题。"""
        self.candidates.append(candidate)
        self.updated_at = time.time()
        self.version += 1

    def select_topic(self, topic: str) -> None:
        """选择论题。"""
        self.selected_topic = topic
        self.updated_at = time.time()
        self.version += 1

    def confirm_method(self, method: str) -> None:
        """确认研究方法。"""
        if method not in self.confirmed_methods:
            self.confirmed_methods.append(method)
            self.updated_at = time.time()
            self.version += 1

    def add_open_question(self, question: str) -> None:
        """添加待解决问题。"""
        self.open_questions.append(question)
        self.updated_at = time.time()
        self.version += 1

    def resolve_question(self, question: str) -> None:
        """解决问题。"""
        if question in self.open_questions:
            self.open_questions.remove(question)
            self.updated_at = time.time()
            self.version += 1

    def set_stage(self, stage: str) -> None:
        """设置当前阶段。"""
        self.stage = stage
        self.updated_at = time.time()
        self.version += 1

    def get_recent_history(self, count: int = 5) -> list:
        """获取最近的历史消息。"""
        return self.history[-count:] if count < len(self.history) else self.history

    def get_context_hash(self) -> str:
        """获取上下文哈希。"""
        serialized = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]

    def clone(self) -> "ConversationContext":
        """深拷贝上下文。"""
        return copy.deepcopy(self)


# ===== 上下文存储 =====


class ContextStore:
    """上下文存储

    提供内存存储与可选的持久化能力。
    """

    def __init__(self, max_size: int = 1000, persist_path: Optional[str] = None):
        """初始化存储。

        Args:
            max_size: 最大存储上下文数。
            persist_path: 持久化文件路径（None 表示仅内存）。
        """
        self.max_size = max_size
        self.persist_path = persist_path
        self._store: OrderedDict[str, ConversationContext] = OrderedDict()
        self._lock = threading.RLock()

    def save(self, context: ConversationContext) -> None:
        """保存上下文。"""
        with self._lock:
            if context.session_id in self._store:
                self._store.move_to_end(context.session_id)
            self._store[context.session_id] = context
            # 超出容量则淘汰最旧
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    def load(self, session_id: str) -> Optional[ConversationContext]:
        """加载上下文。"""
        with self._lock:
            context = self._store.get(session_id)
            if context:
                self._store.move_to_end(session_id)
            return context

    def delete(self, session_id: str) -> bool:
        """删除上下文。"""
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]
                return True
            return False

    def exists(self, session_id: str) -> bool:
        """判断上下文是否存在。"""
        with self._lock:
            return session_id in self._store

    def list_sessions(self) -> list:
        """列出所有会话 ID。"""
        with self._lock:
            return list(self._store.keys())

    def clear(self) -> None:
        """清空存储。"""
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        """存储大小。"""
        with self._lock:
            return len(self._store)

    def get_all(self) -> list:
        """获取所有上下文。"""
        with self._lock:
            return list(self._store.values())

    def persist(self) -> bool:
        """持久化到文件。"""
        if not self.persist_path:
            return False
        try:
            import os
            os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)
            with self._lock:
                data = {sid: ctx.to_dict() for sid, ctx in self._store.items()}
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            return True
        except (IOError, OSError):
            return False

    def restore(self) -> int:
        """从文件恢复。"""
        if not self.persist_path:
            return 0
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                self._store.clear()
                for sid, ctx_data in data.items():
                    self._store[sid] = ConversationContext.from_dict(ctx_data)
            return len(self._store)
        except (IOError, json.JSONDecodeError):
            return 0


# ===== 上下文切换器 =====


class ContextSwitcher:
    """上下文切换器

    管理当前活跃上下文与上下文切换。
    """

    def __init__(self, store: ContextStore):
        self.store = store
        self._current_session_id: Optional[str] = None
        self._lock = threading.RLock()
        self._switch_history: deque = deque(maxlen=50)

    def switch_to(self, session_id: str) -> bool:
        """切换到指定会话。

        Args:
            session_id: 目标会话 ID。

        Returns:
            切换成功返回 True。
        """
        with self._lock:
            if not self.store.exists(session_id):
                return False
            old_id = self._current_session_id
            self._current_session_id = session_id
            self._switch_history.append({
                "from": old_id,
                "to": session_id,
                "timestamp": time.time(),
            })
            return True

    def get_current(self) -> Optional[ConversationContext]:
        """获取当前上下文。"""
        with self._lock:
            if self._current_session_id is None:
                return None
            return self.store.load(self._current_session_id)

    def get_current_id(self) -> Optional[str]:
        """获取当前会话 ID。"""
        with self._lock:
            return self._current_session_id

    def clear_current(self) -> None:
        """清除当前上下文。"""
        with self._lock:
            self._current_session_id = None

    def get_switch_history(self) -> list:
        """获取切换历史。"""
        with self._lock:
            return list(self._switch_history)

    def switch_back(self) -> bool:
        """切换回上一个会话。"""
        with self._lock:
            if len(self._switch_history) < 2:
                return False
            # 获取最后一次切换的源（即上一个会话）
            history = list(self._switch_history)
            last = history[-1]
            target = last["from"]
            if target and self.store.exists(target):
                old_id = self._current_session_id
                self._current_session_id = target
                self._switch_history.append({
                    "from": old_id,
                    "to": target,
                    "timestamp": time.time(),
                })
                return True
            return False


# ===== 上下文版本管理 =====


class ContextVersionManager:
    """上下文版本管理

    记录上下文的历史版本，支持回滚。
    """

    def __init__(self, max_versions: int = 20):
        self.max_versions = max_versions
        self._versions: dict[str, deque] = {}
        self._lock = threading.RLock()

    def save_version(self, context: ConversationContext) -> int:
        """保存版本。

        Args:
            context: 上下文对象。

        Returns:
            版本号。
        """
        with self._lock:
            if context.session_id not in self._versions:
                self._versions[context.session_id] = deque(maxlen=self.max_versions)
            # 深拷贝以避免后续修改影响
            version_copy = context.clone()
            self._versions[context.session_id].append(version_copy)
            return version_copy.version

    def get_version(self, session_id: str, version: int) -> Optional[ConversationContext]:
        """获取指定版本。"""
        with self._lock:
            versions = self._versions.get(session_id, deque())
            for v in versions:
                if v.version == version:
                    return v.clone()
        return None

    def get_latest_version(self, session_id: str) -> Optional[ConversationContext]:
        """获取最新版本。"""
        with self._lock:
            versions = self._versions.get(session_id, deque())
            if not versions:
                return None
            return versions[-1].clone()

    def list_versions(self, session_id: str) -> list:
        """列出所有版本。"""
        with self._lock:
            versions = self._versions.get(session_id, deque())
            return [
                {"version": v.version, "updated_at": v.updated_at, "stage": v.stage}
                for v in versions
            ]

    def rollback(self, session_id: str, version: int) -> Optional[ConversationContext]:
        """回滚到指定版本。

        Args:
            session_id: 会话 ID。
            version: 目标版本号。

        Returns:
            回滚后的上下文。
        """
        target = self.get_version(session_id, version)
        if target is None:
            return None
        # 移除该版本之后的所有版本
        with self._lock:
            versions = self._versions.get(session_id, deque())
            new_versions = deque(maxlen=self.max_versions)
            for v in versions:
                new_versions.append(v)
                if v.version == version:
                    break
            self._versions[session_id] = new_versions
        return target

    def clear_versions(self, session_id: str) -> int:
        """清除指定会话的所有版本。

        Returns:
            清除的版本数。
        """
        with self._lock:
            count = len(self._versions.get(session_id, deque()))
            self._versions.pop(session_id, None)
            return count

    def get_version_count(self, session_id: str) -> int:
        """获取版本数。"""
        with self._lock:
            return len(self._versions.get(session_id, deque()))


# ===== 上下文差异比较 =====


class ContextDiff:
    """上下文差异比较

    比较两个上下文的差异。
    """

    @staticmethod
    def diff(ctx1: ConversationContext, ctx2: ConversationContext) -> dict:
        """比较两个上下文的差异。

        Args:
            ctx1: 上下文1（基准）。
            ctx2: 上下文2（比较）。

        Returns:
            差异字典。
        """
        changes = {}

        # 简单字段比较
        simple_fields = [
            "session_id", "user_id", "degree", "discipline", "mentor_info",
            "selected_topic", "stage",
        ]
        for field_name in simple_fields:
            val1 = getattr(ctx1, field_name, None)
            val2 = getattr(ctx2, field_name, None)
            if val1 != val2:
                changes[field_name] = {"old": val1, "new": val2}

        # 列表字段比较
        list_fields = ["confirmed_methods", "open_questions"]
        for field_name in list_fields:
            list1 = getattr(ctx1, field_name, [])
            list2 = getattr(ctx2, field_name, [])
            added = [x for x in list2 if x not in list1]
            removed = [x for x in list1 if x not in list2]
            if added or removed:
                changes[field_name] = {"added": added, "removed": removed}

        # 历史比较
        if len(ctx1.history) != len(ctx2.history):
            changes["history"] = {
                "old_count": len(ctx1.history),
                "new_count": len(ctx2.history),
                "added": len(ctx2.history) - len(ctx1.history),
            }
        else:
            # 检查内容是否变化
            for i, (m1, m2) in enumerate(zip(ctx1.history, ctx2.history)):
                if m1.get("content") != m2.get("content"):
                    changes[f"history[{i}]"] = {
                        "old": m1.get("content", "")[:100],
                        "new": m2.get("content", "")[:100],
                    }

        # 候选比较
        if len(ctx1.candidates) != len(ctx2.candidates):
            changes["candidates"] = {
                "old_count": len(ctx1.candidates),
                "new_count": len(ctx2.candidates),
            }

        # 元数据比较
        meta_changes = {}
        for key in set(ctx1.metadata.keys()) | set(ctx2.metadata.keys()):
            val1 = ctx1.metadata.get(key)
            val2 = ctx2.metadata.get(key)
            if val1 != val2:
                meta_changes[key] = {"old": val1, "new": val2}
        if meta_changes:
            changes["metadata"] = meta_changes

        return {
            "has_changes": len(changes) > 0,
            "changes": changes,
            "change_count": len(changes),
        }

    @staticmethod
    def summarize_diff(diff_result: dict) -> str:
        """生成差异摘要。"""
        if not diff_result["has_changes"]:
            return "无变化"
        changes = diff_result["changes"]
        parts = []
        for field, change in changes.items():
            if "old" in change and "new" in change:
                parts.append(f"{field}: {change['old']} → {change['new']}")
            elif "added" in change:
                parts.append(f"{field}: 新增 {change['added']}")
            elif "old_count" in change:
                parts.append(f"{field}: {change['old_count']} → {change['new_count']}")
        return "; ".join(parts)


# ===== 多上下文管理器 =====


class MultiContextManager:
    """多上下文管理器

    整合存储、切换、版本管理与差异比较。
    """

    def __init__(
        self,
        max_contexts: int = 1000,
        max_versions: int = 20,
        persist_path: Optional[str] = None,
    ):
        self.store = ContextStore(max_size=max_contexts, persist_path=persist_path)
        self.switcher = ContextSwitcher(self.store)
        self.version_manager = ContextVersionManager(max_versions=max_versions)
        self._lock = threading.RLock()

    def create_context(
        self,
        session_id: str,
        user_id: str = "",
        degree: str = "",
        discipline: str = "",
        mentor_info: str = "",
    ) -> ConversationContext:
        """创建新上下文。"""
        with self._lock:
            context = ConversationContext(
                session_id=session_id,
                user_id=user_id,
                degree=degree,
                discipline=discipline,
                mentor_info=mentor_info,
            )
            self.store.save(context)
            self.version_manager.save_version(context)
            return context

    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """获取上下文。"""
        return self.store.load(session_id)

    def update_context(self, context: ConversationContext) -> None:
        """更新上下文。"""
        with self._lock:
            context.updated_at = time.time()
            context.version += 1
            self.store.save(context)
            self.version_manager.save_version(context)

    def delete_context(self, session_id: str) -> bool:
        """删除上下文。"""
        with self._lock:
            self.version_manager.clear_versions(session_id)
            if self.switcher.get_current_id() == session_id:
                self.switcher.clear_current()
            return self.store.delete(session_id)

    def switch_to(self, session_id: str) -> bool:
        """切换上下文。"""
        return self.switcher.switch_to(session_id)

    def get_current(self) -> Optional[ConversationContext]:
        """获取当前上下文。"""
        return self.switcher.get_current()

    def add_message(self, session_id: str, role: str, content: str) -> bool:
        """添加消息到指定会话。"""
        with self._lock:
            context = self.store.load(session_id)
            if context is None:
                return False
            context.add_message(role, content)
            self.store.save(context)
            self.version_manager.save_version(context)
            return True

    def add_candidate(self, session_id: str, candidate: dict) -> bool:
        """添加候选论题。"""
        with self._lock:
            context = self.store.load(session_id)
            if context is None:
                return False
            context.add_candidate(candidate)
            self.store.save(context)
            self.version_manager.save_version(context)
            return True

    def select_topic(self, session_id: str, topic: str) -> bool:
        """选择论题。"""
        with self._lock:
            context = self.store.load(session_id)
            if context is None:
                return False
            context.select_topic(topic)
            self.store.save(context)
            self.version_manager.save_version(context)
            return True

    def confirm_method(self, session_id: str, method: str) -> bool:
        """确认研究方法。"""
        with self._lock:
            context = self.store.load(session_id)
            if context is None:
                return False
            context.confirm_method(method)
            self.store.save(context)
            self.version_manager.save_version(context)
            return True

    def set_stage(self, session_id: str, stage: str) -> bool:
        """设置阶段。"""
        with self._lock:
            context = self.store.load(session_id)
            if context is None:
                return False
            context.set_stage(stage)
            self.store.save(context)
            self.version_manager.save_version(context)
            return True

    def rollback(self, session_id: str, version: int) -> Optional[ConversationContext]:
        """回滚到指定版本。"""
        with self._lock:
            context = self.version_manager.rollback(session_id, version)
            if context:
                self.store.save(context)
            return context

    def get_version_history(self, session_id: str) -> list:
        """获取版本历史。"""
        return self.version_manager.list_versions(session_id)

    def diff_contexts(self, session_id1: str, session_id2: str) -> dict:
        """比较两个会话的上下文差异。"""
        ctx1 = self.store.load(session_id1)
        ctx2 = self.store.load(session_id2)
        if ctx1 is None or ctx2 is None:
            return {"has_changes": False, "changes": {}, "change_count": 0, "error": "会话不存在"}
        return ContextDiff.diff(ctx1, ctx2)

    def diff_versions(self, session_id: str, version1: int, version2: int) -> dict:
        """比较同一会话的两个版本差异。"""
        ctx1 = self.version_manager.get_version(session_id, version1)
        ctx2 = self.version_manager.get_version(session_id, version2)
        if ctx1 is None or ctx2 is None:
            return {"has_changes": False, "changes": {}, "change_count": 0, "error": "版本不存在"}
        return ContextDiff.diff(ctx1, ctx2)

    def list_sessions(self) -> list:
        """列出所有会话。"""
        return self.store.list_sessions()

    def get_stats(self) -> dict:
        """获取统计。"""
        return {
            "total_contexts": self.store.size(),
            "current_session": self.switcher.get_current_id(),
            "switch_history_count": len(self.switcher.get_switch_history()),
        }

    def persist(self) -> bool:
        """持久化。"""
        return self.store.persist()

    def restore(self) -> int:
        """恢复。"""
        return self.store.restore()

    def clear_all(self) -> None:
        """清空所有。"""
        with self._lock:
            self.store.clear()
            self.switcher.clear_current()
            self._version_sessions = {}

    def smart_compact(self, messages: list[dict], config: dict = None) -> list[dict]:
        """智能上下文压缩（v9.0）。

        在保留系统提示、DST 状态与最近 N 轮原始对话的前提下，
        将中间历史压缩为短摘要，使压缩后的历史进入三段式 Prompt
        缓存的稳定前缀，仅最近 N 轮进入动态尾部，目标缓存命中率 ≥95%。

        Args:
            messages: 消息字典列表，每项含 'role' 与 'content'。
            config: 压缩配置，可选键：
                - compact_threshold: int (默认 10) - 触发压缩的轮数阈值
                - compact_chars: int (默认 100) - 每条压缩消息的目标字符数
                - compact_keep_recent: int (默认 3) - 保留为原始的最近轮数

        Returns:
            压缩后的消息列表（保持 role/content 结构）。
        """
        return smart_compact(messages, config)


# ===== 智能上下文压缩（v9.0）=====


def _count_rounds(messages: list[dict]) -> int:
    """统计对话轮数（user 消息数，等价于 user-assistant 对数）。"""
    return sum(
        1 for m in messages if isinstance(m, dict) and m.get("role") == "user"
    )


def _is_fixed_message(msg: dict) -> bool:
    """判断消息是否为固定消息（系统消息或 DST 状态消息），不应被压缩。"""
    if not isinstance(msg, dict):
        return False
    if msg.get("role") == "system":
        return True
    metadata = msg.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("is_dst_state"):
        return True
    return False


def _partition_messages(
    messages: list[dict], keep_recent: int
) -> tuple[list[dict], list[dict], list[dict]]:
    """将消息划分为三段：固定前缀 / 可压缩中段 / 最近 N 轮。

    - 固定前缀：开头的连续系统/DST 状态消息
    - 最近 N 轮：非系统消息的最后 2*keep_recent 条
    - 可压缩中段：固定前缀与最近 N 轮之间的非系统消息

    Args:
        messages: 原始消息列表。
        keep_recent: 保留为原始的最近轮数。

    Returns:
        (fixed_prefix, compressible, recent) 三元组。
    """
    # 1. 收集开头的连续固定消息（system / DST 状态）
    fixed_prefix: list[dict] = []
    idx = 0
    while idx < len(messages) and _is_fixed_message(messages[idx]):
        fixed_prefix.append(messages[idx])
        idx += 1

    # 2. 剩余为对话消息（user/assistant）
    conversational = list(messages[idx:])

    # 3. 最近 N 轮 = 最后 2*keep_recent 条对话消息
    recent_count = max(0, 2 * keep_recent)
    if recent_count >= len(conversational):
        # 全部保留为最近，无中段可压缩
        return fixed_prefix, [], conversational

    recent = conversational[-recent_count:]
    compressible = conversational[:-recent_count]
    return fixed_prefix, compressible, recent


def _compress_message(msg: dict, chars: int) -> dict:
    """对单条消息进行抽取式压缩（取前 N 字符 + "..."）。

    保留 role 与其他字段，content 前加 "[compressed]" 标记。
    压缩是确定性的：相同输入产生相同输出，利于缓存稳定。

    Args:
        msg: 原始消息字典。
        chars: 目标字符数（截取前 N 字符）。

    Returns:
        压缩后的消息字典。
    """
    if not isinstance(msg, dict):
        return msg
    content = msg.get("content", "")
    if not isinstance(content, str):
        content = str(content)

    if len(content) <= chars:
        truncated = content
    else:
        truncated = content[:chars] + "..."

    compressed = dict(msg)  # 浅拷贝保留 role/metadata 等字段
    compressed["content"] = f"[compressed] {truncated}"
    return compressed


def smart_compact(messages: list[dict], config: dict = None) -> list[dict]:
    """智能上下文压缩（v9.0）。

    在保留系统提示、DST 状态与最近 N 轮原始对话的前提下，
    将中间历史压缩为短摘要，使压缩后的历史进入三段式 Prompt
    缓存的稳定前缀，仅最近 N 轮进入动态尾部，目标缓存命中率 ≥95%。

    压缩是确定性的（相同输入 -> 相同输出），保证缓存前缀字节级稳定。

    Args:
        messages: 消息字典列表，每项含 'role' 与 'content'。
        config: 压缩配置，可选键：
            - compact_threshold: int (默认 10) - 触发压缩的轮数阈值
            - compact_chars: int (默认 100) - 每条压缩消息的目标字符数
            - compact_keep_recent: int (默认 3) - 保留为原始的最近轮数

    Returns:
        压缩后的消息列表（保持 role/content 结构）。
    """
    # 解析配置，缺省时回退到 backend.config 中的全局默认
    try:
        from backend.config import get_compact_config
        defaults = get_compact_config()
    except Exception:  # pragma: no cover - 配置模块不可用时回退硬编码默认
        defaults = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }

    cfg = config or {}
    threshold = int(cfg.get("compact_threshold", defaults.get("compact_threshold", 10)))
    chars = int(cfg.get("compact_chars", defaults.get("compact_chars", 100)))
    keep_recent = int(
        cfg.get("compact_keep_recent", defaults.get("compact_keep_recent", 3))
    )

    # 防御性处理
    if not isinstance(messages, list) or not messages:
        return messages if isinstance(messages, list) else []

    # 1. 统计轮数，不足阈值则原样返回
    rounds = _count_rounds(messages)
    if rounds < threshold:
        return messages

    # 2. 划分三段：固定前缀 / 可压缩中段 / 最近 N 轮
    fixed_prefix, compressible, recent = _partition_messages(messages, keep_recent)

    # 3. 压缩中段（确定性抽取式摘要）
    compressed = [_compress_message(m, chars) for m in compressible]

    # 4. 拼接返回：固定前缀 + 压缩中段 + 最近 N 轮
    return fixed_prefix + compressed + recent


# ===== 全局实例 =====

_global_manager = MultiContextManager()


def get_context_manager() -> MultiContextManager:
    """获取全局上下文管理器。"""
    return _global_manager


def get_context(session_id: str) -> Optional[ConversationContext]:
    """便捷函数：获取上下文。"""
    return _global_manager.get_context(session_id)


def create_context(session_id: str, **kwargs) -> ConversationContext:
    """便捷函数：创建上下文。"""
    return _global_manager.create_context(session_id, **kwargs)
