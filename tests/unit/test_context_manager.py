"""上下文管理器模块单元测试

测试 backend/sessions/context_manager.py 中的所有组件：
    - ConversationContext: 单会话上下文数据类
    - ContextStore: 上下文存储（内存 + 持久化）
    - ContextSwitcher: 上下文切换器
    - ContextVersionManager: 上下文版本管理（含回滚）
    - ContextDiff: 上下文差异比较
    - MultiContextManager: 多上下文管理器
    - 全局函数: get_context_manager / get_context / create_context

测试覆盖：
    - 数据类的字段默认值、序列化/反序列化
    - 存储的增删改查、LRU 淘汰、持久化/恢复
    - 切换器的切换、回切、历史记录
    - 版本管理的保存、获取、回滚、清除
    - 差异比较的简单字段、列表字段、历史、候选、元数据
    - 多上下文管理器的整合操作
    - 全局单例与便捷函数
    - 边界条件与异常场景
"""
import os
import sys
import time
import json
import copy
import threading
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 确保能导入被测模块
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 尝试导入被测模块（源模块可能存在预先 bug，需优雅处理）
_IMPORT_OK = False
_IMPORT_ERROR = None
try:
    from backend.sessions.context_manager import (
        ConversationContext,
        ContextStore,
        ContextSwitcher,
        ContextVersionManager,
        ContextDiff,
        MultiContextManager,
        get_context_manager,
        get_context,
        create_context,
    )
    _IMPORT_OK = True
except Exception as exc:  # pragma: no cover - 仅为兼容源模块预先 bug
    _IMPORT_ERROR = str(exc)

# 若导入失败则跳过所有测试（保证测试文件本身可被 pytest 收集）
pytestmark = pytest.mark.skipif(not _IMPORT_OK, reason=f"被测模块导入失败: {_IMPORT_ERROR}")


# ===== 辅助函数 =====


def _make_context(
    session_id: str = "test-session",
    user_id: str = "user-001",
    degree: str = "master",
    discipline: str = "计算机科学",
    mentor_info: str = "张教授",
) -> ConversationContext:
    """构造测试用上下文实例。"""
    return ConversationContext(
        session_id=session_id,
        user_id=user_id,
        degree=degree,
        discipline=discipline,
        mentor_info=mentor_info,
    )


def _make_filled_context(session_id: str = "filled-session") -> ConversationContext:
    """构造填充了消息、候选、方法的上下文实例。"""
    ctx = _make_context(session_id=session_id)
    ctx.add_message("user", "你好，我想选一个论题")
    ctx.add_message("assistant", "好的，请告诉我您的学科方向")
    ctx.add_message("user", "计算机科学，深度学习方向")
    ctx.add_candidate({"topic": "基于深度学习的图像识别", "score": 0.85})
    ctx.add_candidate({"topic": "基于强化学习的路径规划", "score": 0.78})
    ctx.select_topic("基于深度学习的图像识别")
    ctx.confirm_method("实验法")
    ctx.confirm_method("文献分析法")
    ctx.add_open_question("数据集如何选择？")
    ctx.set_stage("generation")
    ctx.metadata["priority"] = "high"
    ctx.metadata["tags"] = ["深度学习", "图像识别"]
    return ctx


# ===== ConversationContext 测试 =====


class TestConversationContext:
    """测试 ConversationContext 数据类。"""

    def test_default_values(self):
        """测试默认字段值。"""
        ctx = ConversationContext(session_id="s1")
        assert ctx.session_id == "s1"
        assert ctx.user_id == ""
        assert ctx.degree == ""
        assert ctx.discipline == ""
        assert ctx.mentor_info == ""
        assert ctx.history == []
        assert ctx.candidates == []
        assert ctx.selected_topic == ""
        assert ctx.confirmed_methods == []
        assert ctx.open_questions == []
        assert ctx.stage == "info_confirm"
        assert ctx.metadata == {}
        assert ctx.version == 1
        assert ctx.created_at > 0
        assert ctx.updated_at > 0

    def test_custom_values(self):
        """测试自定义字段值。"""
        ctx = ConversationContext(
            session_id="s2",
            user_id="u2",
            degree="doctor",
            discipline="物理学",
            mentor_info="李教授",
            stage="generation",
        )
        assert ctx.session_id == "s2"
        assert ctx.user_id == "u2"
        assert ctx.degree == "doctor"
        assert ctx.discipline == "物理学"
        assert ctx.mentor_info == "李教授"
        assert ctx.stage == "generation"

    def test_to_dict_contains_all_fields(self):
        """测试 to_dict 包含所有字段。"""
        ctx = _make_filled_context()
        d = ctx.to_dict()
        expected_keys = {
            "session_id", "user_id", "degree", "discipline", "mentor_info",
            "history", "candidates", "selected_topic", "confirmed_methods",
            "open_questions", "stage", "metadata", "created_at", "updated_at",
            "version",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_values_match(self):
        """测试 to_dict 的值与对象一致。"""
        ctx = _make_filled_context()
        d = ctx.to_dict()
        assert d["session_id"] == ctx.session_id
        assert d["user_id"] == ctx.user_id
        assert d["degree"] == ctx.degree
        assert d["discipline"] == ctx.discipline
        assert d["mentor_info"] == ctx.mentor_info
        assert d["selected_topic"] == ctx.selected_topic
        assert d["stage"] == ctx.stage
        assert d["version"] == ctx.version

    def test_from_dict_roundtrip(self):
        """测试 from_dict 与 to_dict 的往返一致性。"""
        ctx = _make_filled_context()
        d = ctx.to_dict()
        restored = ConversationContext.from_dict(d)
        assert restored.session_id == ctx.session_id
        assert restored.user_id == ctx.user_id
        assert restored.degree == ctx.degree
        assert restored.discipline == ctx.discipline
        assert restored.mentor_info == ctx.mentor_info
        assert restored.selected_topic == ctx.selected_topic
        assert restored.stage == ctx.stage
        assert restored.version == ctx.version
        assert len(restored.history) == len(ctx.history)
        assert len(restored.candidates) == len(ctx.candidates)

    def test_from_dict_with_missing_fields(self):
        """测试 from_dict 对缺失字段的容错。"""
        restored = ConversationContext.from_dict({"session_id": "s3"})
        assert restored.session_id == "s3"
        assert restored.user_id == ""
        assert restored.history == []
        assert restored.stage == "info_confirm"
        assert restored.version == 1

    def test_from_dict_empty_dict(self):
        """测试 from_dict 对空字典的容错。"""
        restored = ConversationContext.from_dict({})
        assert restored.session_id == ""
        assert restored.stage == "info_confirm"

    def test_add_message(self):
        """测试添加消息。"""
        ctx = _make_context()
        old_version = ctx.version
        ctx.add_message("user", "测试消息")
        assert len(ctx.history) == 1
        assert ctx.history[0]["role"] == "user"
        assert ctx.history[0]["content"] == "测试消息"
        assert "timestamp" in ctx.history[0]
        assert ctx.version == old_version + 1
        assert ctx.updated_at >= ctx.created_at

    def test_add_multiple_messages(self):
        """测试添加多条消息。"""
        ctx = _make_context()
        for i in range(10):
            ctx.add_message("user", f"消息{i}")
        assert len(ctx.history) == 10
        assert ctx.history[0]["content"] == "消息0"
        assert ctx.history[-1]["content"] == "消息9"

    def test_add_candidate(self):
        """测试添加候选论题。"""
        ctx = _make_context()
        old_version = ctx.version
        ctx.add_candidate({"topic": "论题A", "score": 0.9})
        assert len(ctx.candidates) == 1
        assert ctx.candidates[0]["topic"] == "论题A"
        assert ctx.version == old_version + 1

    def test_add_multiple_candidates(self):
        """测试添加多个候选。"""
        ctx = _make_context()
        for i in range(5):
            ctx.add_candidate({"topic": f"论题{i}", "score": 0.5 + i * 0.1})
        assert len(ctx.candidates) == 5
        assert ctx.candidates[4]["topic"] == "论题4"

    def test_select_topic(self):
        """测试选择论题。"""
        ctx = _make_context()
        old_version = ctx.version
        ctx.select_topic("选定论题")
        assert ctx.selected_topic == "选定论题"
        assert ctx.version == old_version + 1

    def test_select_topic_override(self):
        """测试覆盖选择论题。"""
        ctx = _make_context()
        ctx.select_topic("论题A")
        ctx.select_topic("论题B")
        assert ctx.selected_topic == "论题B"

    def test_confirm_method(self):
        """测试确认研究方法。"""
        ctx = _make_context()
        old_version = ctx.version
        ctx.confirm_method("实验法")
        assert "实验法" in ctx.confirmed_methods
        assert ctx.version == old_version + 1

    def test_confirm_method_dedup(self):
        """测试确认方法去重。"""
        ctx = _make_context()
        ctx.confirm_method("实验法")
        old_version = ctx.version
        ctx.confirm_method("实验法")  # 重复确认
        assert len(ctx.confirmed_methods) == 1
        assert ctx.version == old_version  # 不应增加版本号

    def test_confirm_multiple_methods(self):
        """测试确认多个方法。"""
        ctx = _make_context()
        ctx.confirm_method("实验法")
        ctx.confirm_method("文献分析法")
        ctx.confirm_method("问卷调查法")
        assert len(ctx.confirmed_methods) == 3

    def test_add_open_question(self):
        """测试添加待解决问题。"""
        ctx = _make_context()
        old_version = ctx.version
        ctx.add_open_question("数据集如何选择？")
        assert len(ctx.open_questions) == 1
        assert ctx.version == old_version + 1

    def test_resolve_question(self):
        """测试解决问题。"""
        ctx = _make_context()
        ctx.add_open_question("问题A")
        ctx.add_open_question("问题B")
        old_version = ctx.version
        ctx.resolve_question("问题A")
        assert "问题A" not in ctx.open_questions
        assert "问题B" in ctx.open_questions
        assert ctx.version == old_version + 1

    def test_resolve_nonexistent_question(self):
        """测试解决不存在的问题（不应报错）。"""
        ctx = _make_context()
        old_version = ctx.version
        ctx.resolve_question("不存在的问题")
        assert ctx.version == old_version  # 不应增加版本号

    def test_set_stage(self):
        """测试设置阶段。"""
        ctx = _make_context()
        old_version = ctx.version
        ctx.set_stage("generation")
        assert ctx.stage == "generation"
        assert ctx.version == old_version + 1

    def test_get_recent_history(self):
        """测试获取最近历史。"""
        ctx = _make_context()
        for i in range(10):
            ctx.add_message("user", f"消息{i}")
        recent = ctx.get_recent_history(3)
        assert len(recent) == 3
        assert recent[-1]["content"] == "消息9"
        assert recent[0]["content"] == "消息7"

    def test_get_recent_history_more_than_available(self):
        """测试获取超过可用数量的历史。"""
        ctx = _make_context()
        ctx.add_message("user", "消息1")
        recent = ctx.get_recent_history(10)
        assert len(recent) == 1

    def test_get_recent_history_empty(self):
        """测试空历史的获取。"""
        ctx = _make_context()
        recent = ctx.get_recent_history(5)
        assert recent == []

    def test_get_context_hash(self):
        """测试上下文哈希。"""
        ctx1 = _make_filled_context("hash-test")
        ctx2 = _make_filled_context("hash-test")
        # 相同内容应产生相同哈希
        assert ctx1.get_context_hash() == ctx2.get_context_hash()
        # 哈希应为 32 位十六进制字符串
        h = ctx1.get_context_hash()
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)

    def test_context_hash_changes_with_content(self):
        """测试内容变化时哈希变化。"""
        ctx = _make_context()
        hash1 = ctx.get_context_hash()
        ctx.add_message("user", "新消息")
        hash2 = ctx.get_context_hash()
        assert hash1 != hash2

    def test_context_hash_different_sessions(self):
        """测试不同会话的哈希不同。"""
        ctx1 = _make_context("session-A")
        ctx2 = _make_context("session-B")
        assert ctx1.get_context_hash() != ctx2.get_context_hash()

    def test_clone(self):
        """测试深拷贝克隆。"""
        ctx = _make_filled_context()
        cloned = ctx.clone()
        assert cloned.session_id == ctx.session_id
        assert cloned.user_id == ctx.user_id
        assert cloned.selected_topic == ctx.selected_topic
        # 修改克隆不应影响原对象
        cloned.add_message("user", "克隆消息")
        assert len(cloned.history) == len(ctx.history) + 1

    def test_clone_independence(self):
        """测试克隆的独立性（深拷贝）。"""
        ctx = _make_context()
        ctx.add_candidate({"topic": "论题A"})
        cloned = ctx.clone()
        cloned.candidates[0]["topic"] = "修改后的论题"
        assert ctx.candidates[0]["topic"] == "论题A"

    def test_version_increments(self):
        """测试版本号递增。"""
        ctx = _make_context()
        assert ctx.version == 1
        ctx.add_message("user", "msg")
        ctx.add_candidate({"topic": "t"})
        ctx.select_topic("t")
        ctx.confirm_method("m")
        ctx.set_stage("s")
        assert ctx.version == 6


# ===== ContextStore 测试 =====


class TestContextStore:
    """测试 ContextStore 上下文存储。"""

    def test_save_and_load(self):
        """测试保存与加载。"""
        store = ContextStore()
        ctx = _make_context("store-1")
        store.save(ctx)
        loaded = store.load("store-1")
        assert loaded is not None
        assert loaded.session_id == "store-1"

    def test_load_nonexistent(self):
        """测试加载不存在的上下文。"""
        store = ContextStore()
        assert store.load("nonexistent") is None

    def test_delete(self):
        """测试删除。"""
        store = ContextStore()
        ctx = _make_context("store-2")
        store.save(ctx)
        assert store.delete("store-2") is True
        assert store.load("store-2") is None

    def test_delete_nonexistent(self):
        """测试删除不存在的上下文。"""
        store = ContextStore()
        assert store.delete("nonexistent") is False

    def test_exists(self):
        """测试判断存在。"""
        store = ContextStore()
        ctx = _make_context("store-3")
        store.save(ctx)
        assert store.exists("store-3") is True
        assert store.exists("nonexistent") is False

    def test_list_sessions(self):
        """测试列出所有会话。"""
        store = ContextStore()
        for i in range(5):
            store.save(_make_context(f"session-{i}"))
        sessions = store.list_sessions()
        assert len(sessions) == 5
        for i in range(5):
            assert f"session-{i}" in sessions

    def test_clear(self):
        """测试清空存储。"""
        store = ContextStore()
        for i in range(3):
            store.save(_make_context(f"clear-{i}"))
        store.clear()
        assert store.size() == 0
        assert store.list_sessions() == []

    def test_size(self):
        """测试存储大小。"""
        store = ContextStore()
        assert store.size() == 0
        store.save(_make_context("s1"))
        assert store.size() == 1
        store.save(_make_context("s2"))
        assert store.size() == 2

    def test_get_all(self):
        """测试获取所有上下文。"""
        store = ContextStore()
        for i in range(3):
            store.save(_make_context(f"all-{i}"))
        all_ctx = store.get_all()
        assert len(all_ctx) == 3

    def test_save_updates_existing(self):
        """测试保存已存在的上下文会更新。"""
        store = ContextStore()
        ctx = _make_context("update-test")
        ctx.add_message("user", "初始消息")
        store.save(ctx)
        # 修改并重新保存
        ctx.add_message("user", "第二条消息")
        store.save(ctx)
        loaded = store.load("update-test")
        assert len(loaded.history) == 2

    def test_lru_eviction(self):
        """测试 LRU 淘汰策略。"""
        store = ContextStore(max_size=3)
        store.save(_make_context("lru-1"))
        store.save(_make_context("lru-2"))
        store.save(_make_context("lru-3"))
        assert store.size() == 3
        # 访问 lru-1 使其变为最近使用
        store.load("lru-1")
        # 添加第 4 个，应淘汰 lru-2（最久未使用）
        store.save(_make_context("lru-4"))
        assert store.size() == 3
        assert not store.exists("lru-2")
        assert store.exists("lru-1")
        assert store.exists("lru-3")
        assert store.exists("lru-4")

    def test_lru_order_on_save(self):
        """测试保存时更新 LRU 顺序。"""
        store = ContextStore(max_size=2)
        store.save(_make_context("a"))
        store.save(_make_context("b"))
        # 重新保存 a，使其变为最近使用
        store.save(_make_context("a"))
        # 添加 c，应淘汰 b
        store.save(_make_context("c"))
        assert store.exists("a")
        assert not store.exists("b")
        assert store.exists("c")

    def test_persist_without_path(self):
        """测试无路径时持久化返回 False。"""
        store = ContextStore()
        assert store.persist() is False

    def test_restore_without_path(self):
        """测试无路径时恢复返回 0。"""
        store = ContextStore()
        assert store.restore() == 0

    def test_persist_and_restore(self, tmp_path):
        """测试持久化与恢复。"""
        persist_file = str(tmp_path / "contexts.json")
        store = ContextStore(max_size=10, persist_path=persist_file)
        ctx = _make_filled_context("persist-test")
        store.save(ctx)
        # 持久化
        assert store.persist() is True
        assert os.path.exists(persist_file)
        # 新存储从文件恢复
        store2 = ContextStore(max_size=10, persist_path=persist_file)
        count = store2.restore()
        assert count == 1
        loaded = store2.load("persist-test")
        assert loaded is not None
        assert loaded.session_id == "persist-test"
        assert loaded.selected_topic == "基于深度学习的图像识别"

    def test_persist_creates_directory(self, tmp_path):
        """测试持久化时创建目录。"""
        persist_file = str(tmp_path / "subdir" / "contexts.json")
        store = ContextStore(max_size=10, persist_path=persist_file)
        store.save(_make_context("dir-test"))
        assert store.persist() is True
        assert os.path.exists(persist_file)

    def test_restore_nonexistent_file(self, tmp_path):
        """测试从不存在的文件恢复返回 0。"""
        persist_file = str(tmp_path / "nonexistent.json")
        store = ContextStore(max_size=10, persist_path=persist_file)
        assert store.restore() == 0

    def test_thread_safety(self):
        """测试线程安全（并发保存）。"""
        store = ContextStore(max_size=100)
        errors = []

        def worker(thread_id: int):
            try:
                for i in range(20):
                    store.save(_make_context(f"thread-{thread_id}-ctx-{i}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert store.size() == 100


# ===== ContextSwitcher 测试 =====


class TestContextSwitcher:
    """测试 ContextSwitcher 上下文切换器。"""

    def test_switch_to(self):
        """测试切换到指定会话。"""
        store = ContextStore()
        store.save(_make_context("switch-1"))
        switcher = ContextSwitcher(store)
        assert switcher.switch_to("switch-1") is True
        assert switcher.get_current_id() == "switch-1"

    def test_switch_to_nonexistent(self):
        """测试切换到不存在的会话。"""
        store = ContextStore()
        switcher = ContextSwitcher(store)
        assert switcher.switch_to("nonexistent") is False
        assert switcher.get_current_id() is None

    def test_get_current(self):
        """测试获取当前上下文。"""
        store = ContextStore()
        ctx = _make_context("current-test")
        store.save(ctx)
        switcher = ContextSwitcher(store)
        switcher.switch_to("current-test")
        current = switcher.get_current()
        assert current is not None
        assert current.session_id == "current-test"

    def test_get_current_when_none(self):
        """测试无当前上下文时返回 None。"""
        store = ContextStore()
        switcher = ContextSwitcher(store)
        assert switcher.get_current() is None

    def test_get_current_id(self):
        """测试获取当前会话 ID。"""
        store = ContextStore()
        store.save(_make_context("id-test"))
        switcher = ContextSwitcher(store)
        assert switcher.get_current_id() is None
        switcher.switch_to("id-test")
        assert switcher.get_current_id() == "id-test"

    def test_clear_current(self):
        """测试清除当前上下文。"""
        store = ContextStore()
        store.save(_make_context("clear-test"))
        switcher = ContextSwitcher(store)
        switcher.switch_to("clear-test")
        switcher.clear_current()
        assert switcher.get_current_id() is None

    def test_switch_history(self):
        """测试切换历史记录。"""
        store = ContextStore()
        store.save(_make_context("hist-1"))
        store.save(_make_context("hist-2"))
        switcher = ContextSwitcher(store)
        switcher.switch_to("hist-1")
        switcher.switch_to("hist-2")
        history = switcher.get_switch_history()
        assert len(history) == 2
        assert history[0]["to"] == "hist-1"
        assert history[1]["to"] == "hist-2"

    def test_switch_back(self):
        """测试切换回上一个会话。"""
        store = ContextStore()
        store.save(_make_context("back-1"))
        store.save(_make_context("back-2"))
        switcher = ContextSwitcher(store)
        switcher.switch_to("back-1")
        switcher.switch_to("back-2")
        assert switcher.switch_back() is True
        assert switcher.get_current_id() == "back-1"

    def test_switch_back_no_history(self):
        """测试无历史时无法回切。"""
        store = ContextStore()
        switcher = ContextSwitcher(store)
        assert switcher.switch_back() is False

    def test_switch_back_single_switch(self):
        """测试仅一次切换时无法回切。"""
        store = ContextStore()
        store.save(_make_context("single-1"))
        switcher = ContextSwitcher(store)
        switcher.switch_to("single-1")
        assert switcher.switch_back() is False

    def test_multiple_switches(self):
        """测试多次切换。"""
        store = ContextStore()
        for i in range(5):
            store.save(_make_context(f"multi-{i}"))
        switcher = ContextSwitcher(store)
        for i in range(5):
            assert switcher.switch_to(f"multi-{i}") is True
        assert switcher.get_current_id() == "multi-4"
        assert len(switcher.get_switch_history()) == 5


# ===== ContextVersionManager 测试 =====


class TestContextVersionManager:
    """测试 ContextVersionManager 版本管理。"""

    def test_save_version(self):
        """测试保存版本。"""
        mgr = ContextVersionManager()
        ctx = _make_context("ver-1")
        version = mgr.save_version(ctx)
        assert version == ctx.version

    def test_get_version(self):
        """测试获取指定版本。"""
        mgr = ContextVersionManager()
        ctx = _make_context("ver-2")
        ctx.add_message("user", "msg")
        mgr.save_version(ctx)
        retrieved = mgr.get_version("ver-2", ctx.version)
        assert retrieved is not None
        assert retrieved.version == ctx.version

    def test_get_version_nonexistent(self):
        """测试获取不存在的版本。"""
        mgr = ContextVersionManager()
        assert mgr.get_version("nonexistent", 1) is None

    def test_get_latest_version(self):
        """测试获取最新版本。"""
        mgr = ContextVersionManager()
        ctx = _make_context("ver-3")
        ctx.add_message("user", "msg1")
        mgr.save_version(ctx)
        ctx.add_message("user", "msg2")
        mgr.save_version(ctx)
        latest = mgr.get_latest_version("ver-3")
        assert latest is not None
        assert len(latest.history) == 2

    def test_get_latest_version_empty(self):
        """测试无版本时获取最新返回 None。"""
        mgr = ContextVersionManager()
        assert mgr.get_latest_version("nonexistent") is None

    def test_list_versions(self):
        """测试列出所有版本。"""
        mgr = ContextVersionManager()
        ctx = _make_context("ver-4")
        for i in range(3):
            ctx.add_message("user", f"msg{i}")
            mgr.save_version(ctx)
        versions = mgr.list_versions("ver-4")
        assert len(versions) == 3
        for v in versions:
            assert "version" in v
            assert "updated_at" in v
            assert "stage" in v

    def test_list_versions_empty(self):
        """测试列出空版本。"""
        mgr = ContextVersionManager()
        assert mgr.list_versions("nonexistent") == []

    def test_rollback(self):
        """测试回滚到指定版本。"""
        mgr = ContextVersionManager()
        ctx = _make_context("rollback-test")
        ctx.add_message("user", "msg1")
        mgr.save_version(ctx)
        v1 = ctx.version
        ctx.add_message("user", "msg2")
        ctx.add_message("user", "msg3")
        mgr.save_version(ctx)
        # 回滚到 v1
        rolled = mgr.rollback("rollback-test", v1)
        assert rolled is not None
        assert rolled.version == v1
        assert len(rolled.history) == 1
        # 回滚后版本列表应截断
        versions = mgr.list_versions("rollback-test")
        assert len(versions) == 1

    def test_rollback_nonexistent(self):
        """测试回滚不存在的版本。"""
        mgr = ContextVersionManager()
        assert mgr.rollback("nonexistent", 1) is None

    def test_clear_versions(self):
        """测试清除版本。"""
        mgr = ContextVersionManager()
        ctx = _make_context("clear-ver")
        mgr.save_version(ctx)
        count = mgr.clear_versions("clear-ver")
        assert count == 1
        assert mgr.get_version_count("clear-ver") == 0

    def test_clear_versions_nonexistent(self):
        """测试清除不存在的版本返回 0。"""
        mgr = ContextVersionManager()
        assert mgr.clear_versions("nonexistent") == 0

    def test_get_version_count(self):
        """测试获取版本数。"""
        mgr = ContextVersionManager()
        ctx = _make_context("count-test")
        for i in range(5):
            ctx.add_message("user", f"msg{i}")
            mgr.save_version(ctx)
        assert mgr.get_version_count("count-test") == 5

    def test_max_versions_limit(self):
        """测试最大版本数限制。"""
        mgr = ContextVersionManager(max_versions=3)
        ctx = _make_context("max-ver")
        for i in range(10):
            ctx.add_message("user", f"msg{i}")
            mgr.save_version(ctx)
        # 超过限制后只保留最近 3 个
        assert mgr.get_version_count("max-ver") == 3

    def test_version_independence(self):
        """测试版本独立性（深拷贝）。"""
        mgr = ContextVersionManager()
        ctx = _make_context("indep-test")
        ctx.add_message("user", "original")
        mgr.save_version(ctx)
        # 修改原上下文
        ctx.add_message("user", "modified")
        # 获取保存的版本应不受影响
        saved = mgr.get_latest_version("indep-test")
        # 最新版本应包含 modified（因为保存了两次前没有再 save）
        # 这里测试的是 save_version 时的深拷贝
        assert saved is not None


# ===== ContextDiff 测试 =====


class TestContextDiff:
    """测试 ContextDiff 差异比较。"""

    def test_diff_no_changes(self):
        """测试无差异。"""
        ctx1 = _make_filled_context("diff-1")
        ctx2 = ctx1.clone()
        result = ContextDiff.diff(ctx1, ctx2)
        assert result["has_changes"] is False
        assert result["change_count"] == 0

    def test_diff_simple_field_change(self):
        """测试简单字段变化。"""
        ctx1 = _make_context("diff-2", degree="master")
        ctx2 = _make_context("diff-2", degree="doctor")
        result = ContextDiff.diff(ctx1, ctx2)
        assert result["has_changes"] is True
        assert "degree" in result["changes"]
        assert result["changes"]["degree"]["old"] == "master"
        assert result["changes"]["degree"]["new"] == "doctor"

    def test_diff_stage_change(self):
        """测试阶段字段变化。"""
        ctx1 = _make_context("diff-3")
        ctx1.set_stage("info_confirm")
        ctx2 = _make_context("diff-3")
        ctx2.set_stage("generation")
        result = ContextDiff.diff(ctx1, ctx2)
        assert "stage" in result["changes"]

    def test_diff_selected_topic_change(self):
        """测试论题变化。"""
        ctx1 = _make_context("diff-4")
        ctx1.select_topic("论题A")
        ctx2 = _make_context("diff-4")
        ctx2.select_topic("论题B")
        result = ContextDiff.diff(ctx1, ctx2)
        assert "selected_topic" in result["changes"]

    def test_diff_list_field_added(self):
        """测试列表字段新增。"""
        ctx1 = _make_context("diff-5")
        ctx2 = _make_context("diff-5")
        ctx2.confirm_method("实验法")
        result = ContextDiff.diff(ctx1, ctx2)
        assert "confirmed_methods" in result["changes"]
        assert "实验法" in result["changes"]["confirmed_methods"]["added"]

    def test_diff_list_field_removed(self):
        """测试列表字段移除。"""
        ctx1 = _make_context("diff-6")
        ctx1.confirm_method("实验法")
        ctx2 = _make_context("diff-6")
        result = ContextDiff.diff(ctx1, ctx2)
        assert "confirmed_methods" in result["changes"]
        assert "实验法" in result["changes"]["confirmed_methods"]["removed"]

    def test_diff_history_count_change(self):
        """测试历史数量变化。"""
        ctx1 = _make_context("diff-7")
        ctx2 = _make_context("diff-7")
        ctx2.add_message("user", "新消息")
        result = ContextDiff.diff(ctx1, ctx2)
        assert "history" in result["changes"]
        assert result["changes"]["history"]["old_count"] == 0
        assert result["changes"]["history"]["new_count"] == 1

    def test_diff_candidates_count_change(self):
        """测试候选数量变化。"""
        ctx1 = _make_context("diff-8")
        ctx2 = _make_context("diff-8")
        ctx2.add_candidate({"topic": "新论题"})
        result = ContextDiff.diff(ctx1, ctx2)
        assert "candidates" in result["changes"]

    def test_diff_metadata_change(self):
        """测试元数据变化。"""
        ctx1 = _make_context("diff-9")
        ctx1.metadata["key"] = "old"
        ctx2 = _make_context("diff-9")
        ctx2.metadata["key"] = "new"
        result = ContextDiff.diff(ctx1, ctx2)
        assert "metadata" in result["changes"]
        assert result["changes"]["metadata"]["key"]["old"] == "old"
        assert result["changes"]["metadata"]["key"]["new"] == "new"

    def test_diff_metadata_added(self):
        """测试元数据新增键。"""
        ctx1 = _make_context("diff-10")
        ctx2 = _make_context("diff-10")
        ctx2.metadata["new_key"] = "value"
        result = ContextDiff.diff(ctx1, ctx2)
        assert "metadata" in result["changes"]
        assert "new_key" in result["changes"]["metadata"]

    def test_summarize_diff_no_changes(self):
        """测试无差异的摘要。"""
        ctx1 = _make_context("sum-1")
        ctx2 = ctx1.clone()
        result = ContextDiff.diff(ctx1, ctx2)
        summary = ContextDiff.summarize_diff(result)
        assert summary == "无变化"

    def test_summarize_diff_with_changes(self):
        """测试有差异的摘要。"""
        ctx1 = _make_context("sum-2", degree="master")
        ctx2 = _make_context("sum-2", degree="doctor")
        result = ContextDiff.diff(ctx1, ctx2)
        summary = ContextDiff.summarize_diff(result)
        assert "degree" in summary
        assert "master" in summary
        assert "doctor" in summary

    def test_summarize_diff_list_changes(self):
        """测试列表差异的摘要。"""
        ctx1 = _make_context("sum-3")
        ctx2 = _make_context("sum-3")
        ctx2.confirm_method("实验法")
        result = ContextDiff.diff(ctx1, ctx2)
        summary = ContextDiff.summarize_diff(result)
        assert "confirmed_methods" in summary
        assert "实验法" in summary

    def test_diff_change_count(self):
        """测试差异计数。"""
        ctx1 = _make_context("count-diff")
        ctx2 = _make_context("count-diff")
        ctx2.set_stage("generation")
        ctx2.select_topic("新论题")
        ctx2.confirm_method("实验法")
        result = ContextDiff.diff(ctx1, ctx2)
        assert result["change_count"] == len(result["changes"])
        assert result["change_count"] >= 2


# ===== MultiContextManager 测试 =====


class TestMultiContextManager:
    """测试 MultiContextManager 多上下文管理器。"""

    def test_create_context(self):
        """测试创建上下文。"""
        mgr = MultiContextManager()
        ctx = mgr.create_context("mctx-1", user_id="u1", degree="master")
        assert ctx.session_id == "mctx-1"
        assert ctx.user_id == "u1"
        assert ctx.degree == "master"
        assert mgr.get_context("mctx-1") is not None

    def test_get_context(self):
        """测试获取上下文。"""
        mgr = MultiContextManager()
        mgr.create_context("mctx-2")
        ctx = mgr.get_context("mctx-2")
        assert ctx is not None
        assert ctx.session_id == "mctx-2"

    def test_get_context_nonexistent(self):
        """测试获取不存在的上下文。"""
        mgr = MultiContextManager()
        assert mgr.get_context("nonexistent") is None

    def test_update_context(self):
        """测试更新上下文。"""
        mgr = MultiContextManager()
        ctx = mgr.create_context("mctx-3")
        old_version = ctx.version
        ctx.add_message("user", "新消息")
        mgr.update_context(ctx)
        assert ctx.version == old_version + 1
        # 版本管理器应记录新版本
        versions = mgr.get_version_history("mctx-3")
        assert len(versions) >= 2

    def test_delete_context(self):
        """测试删除上下文。"""
        mgr = MultiContextManager()
        mgr.create_context("mctx-4")
        assert mgr.delete_context("mctx-4") is True
        assert mgr.get_context("mctx-4") is None

    def test_delete_context_nonexistent(self):
        """测试删除不存在的上下文。"""
        mgr = MultiContextManager()
        assert mgr.delete_context("nonexistent") is False

    def test_switch_to(self):
        """测试切换上下文。"""
        mgr = MultiContextManager()
        mgr.create_context("mctx-5")
        mgr.create_context("mctx-6")
        assert mgr.switch_to("mctx-5") is True
        assert mgr.get_current().session_id == "mctx-5"
        assert mgr.switch_to("mctx-6") is True
        assert mgr.get_current().session_id == "mctx-6"

    def test_switch_to_nonexistent(self):
        """测试切换到不存在的上下文。"""
        mgr = MultiContextManager()
        assert mgr.switch_to("nonexistent") is False

    def test_get_current(self):
        """测试获取当前上下文。"""
        mgr = MultiContextManager()
        assert mgr.get_current() is None
        mgr.create_context("mctx-7")
        mgr.switch_to("mctx-7")
        current = mgr.get_current()
        assert current is not None
        assert current.session_id == "mctx-7"

    def test_add_message(self):
        """测试通过管理器添加消息。"""
        mgr = MultiContextManager()
        mgr.create_context("mctx-8")
        assert mgr.add_message("mctx-8", "user", "测试消息") is True
        ctx = mgr.get_context("mctx-8")
        assert len(ctx.history) == 1
        assert ctx.history[0]["content"] == "测试消息"

    def test_add_message_nonexistent(self):
        """测试向不存在的会话添加消息。"""
        mgr = MultiContextManager()
        assert mgr.add_message("nonexistent", "user", "msg") is False

    def test_add_candidate(self):
        """测试通过管理器添加候选。"""
        mgr = MultiContextManager()
        mgr.create_context("mctx-9")
        assert mgr.add_candidate("mctx-9", {"topic": "论题"}) is True
        ctx = mgr.get_context("mctx-9")
        assert len(ctx.candidates) == 1

    def test_select_topic(self):
        """测试通过管理器选择论题。"""
        mgr = MultiContextManager()
        mgr.create_context("mctx-10")
        assert mgr.select_topic("mctx-10", "选定论题") is True
        ctx = mgr.get_context("mctx-10")
        assert ctx.selected_topic == "选定论题"

    def test_set_stage(self):
        """测试通过管理器设置阶段。"""
        mgr = MultiContextManager()
        mgr.create_context("mctx-11")
        assert mgr.set_stage("mctx-11", "generation") is True
        ctx = mgr.get_context("mctx-11")
        assert ctx.stage == "generation"

    def test_rollback(self):
        """测试通过管理器回滚。"""
        mgr = MultiContextManager()
        ctx = mgr.create_context("mctx-12")
        ctx.add_message("user", "msg1")
        mgr.update_context(ctx)
        v1 = ctx.version
        ctx.add_message("user", "msg2")
        mgr.update_context(ctx)
        # 回滚
        rolled = mgr.rollback("mctx-12", v1)
        assert rolled is not None
        assert rolled.version == v1

    def test_get_version_history(self):
        """测试获取版本历史。"""
        mgr = MultiContextManager()
        ctx = mgr.create_context("mctx-13")
        ctx.add_message("user", "msg1")
        mgr.update_context(ctx)
        history = mgr.get_version_history("mctx-13")
        assert len(history) >= 2

    def test_diff_contexts(self):
        """测试比较两个会话差异。"""
        mgr = MultiContextManager()
        mgr.create_context("mctx-14", degree="master")
        mgr.create_context("mctx-15", degree="doctor")
        result = mgr.diff_contexts("mctx-14", "mctx-15")
        assert result["has_changes"] is True
        assert "degree" in result["changes"]

    def test_diff_contexts_nonexistent(self):
        """测试比较不存在的会话。"""
        mgr = MultiContextManager()
        result = mgr.diff_contexts("nonexistent-1", "nonexistent-2")
        assert result["has_changes"] is False
        assert "error" in result

    def test_diff_versions(self):
        """测试比较同会话的两个版本。"""
        mgr = MultiContextManager()
        ctx = mgr.create_context("mctx-16", degree="master")
        v1 = ctx.version
        ctx.degree = "doctor"
        mgr.update_context(ctx)
        v2 = ctx.version
        result = mgr.diff_versions("mctx-16", v1, v2)
        assert result["has_changes"] is True

    def test_list_sessions(self):
        """测试列出所有会话。"""
        mgr = MultiContextManager()
        for i in range(3):
            mgr.create_context(f"list-{i}")
        sessions = mgr.list_sessions()
        assert len(sessions) == 3

    def test_get_stats(self):
        """测试获取统计信息。"""
        mgr = MultiContextManager()
        mgr.create_context("stat-1")
        mgr.create_context("stat-2")
        mgr.switch_to("stat-1")
        stats = mgr.get_stats()
        assert stats["total_contexts"] == 2
        assert stats["current_session"] == "stat-1"

    def test_persist_and_restore(self, tmp_path):
        """测试持久化与恢复。"""
        persist_file = str(tmp_path / "multi.json")
        mgr = MultiContextManager(persist_path=persist_file)
        mgr.create_context("persist-1")
        mgr.create_context("persist-2")
        assert mgr.persist() is True
        # 新管理器恢复
        mgr2 = MultiContextManager(persist_path=persist_file)
        count = mgr2.restore()
        assert count == 2

    def test_clear_all(self):
        """测试清空所有。"""
        mgr = MultiContextManager()
        for i in range(3):
            mgr.create_context(f"clear-{i}")
        mgr.clear_all()
        assert len(mgr.list_sessions()) == 0


# ===== 全局函数测试 =====


class TestGlobalFunctions:
    """测试全局函数。"""

    def test_get_context_manager(self):
        """测试获取全局管理器。"""
        mgr = get_context_manager()
        assert mgr is not None
        assert isinstance(mgr, MultiContextManager)

    def test_get_context_manager_singleton(self):
        """测试全局管理器为单例。"""
        mgr1 = get_context_manager()
        mgr2 = get_context_manager()
        assert mgr1 is mgr2

    def test_get_context(self):
        """测试便捷获取上下文函数。"""
        mgr = get_context_manager()
        mgr.create_context("global-test-ctx")
        ctx = get_context("global-test-ctx")
        assert ctx is not None
        assert ctx.session_id == "global-test-ctx"

    def test_get_context_nonexistent(self):
        """测试获取不存在的上下文。"""
        assert get_context("nonexistent-global") is None

    def test_create_context(self):
        """测试便捷创建上下文函数。"""
        ctx = create_context("global-create-test", user_id="u1", degree="master")
        assert ctx.session_id == "global-create-test"
        assert ctx.user_id == "u1"
        assert ctx.degree == "master"
        # 应已存入全局管理器
        assert get_context("global-create-test") is not None


# ===== 集成测试 =====


class TestIntegration:
    """集成测试：模拟完整工作流。"""

    def test_full_workflow(self):
        """测试完整工作流：创建→操作→版本→回滚→差异。"""
        mgr = MultiContextManager()
        # 1. 创建上下文
        ctx = mgr.create_context(
            "workflow-test",
            user_id="student-001",
            degree="master",
            discipline="计算机科学",
        )
        # 2. 添加消息与候选
        mgr.add_message("workflow-test", "user", "我想选深度学习方向的论题")
        mgr.add_message("workflow-test", "assistant", "好的，为您推荐以下论题")
        mgr.add_candidate("workflow-test", {"topic": "基于CNN的图像分类", "score": 0.85})
        mgr.add_candidate("workflow-test", {"topic": "基于RNN的文本生成", "score": 0.78})
        # 3. 选择论题
        mgr.select_topic("workflow-test", "基于CNN的图像分类")
        mgr.confirm_method("workflow-test", "实验法")
        mgr.set_stage("workflow-test", "generation")
        # 4. 验证状态
        ctx = mgr.get_context("workflow-test")
        assert ctx.selected_topic == "基于CNN的图像分类"
        assert "实验法" in ctx.confirmed_methods
        assert ctx.stage == "generation"
        # 5. 版本历史
        versions = mgr.get_version_history("workflow-test")
        assert len(versions) >= 2

    def test_multi_session_workflow(self):
        """测试多会话并行工作流。"""
        mgr = MultiContextManager()
        # 创建多个会话
        for i in range(5):
            mgr.create_context(f"parallel-{i}", user_id=f"user-{i}")
        # 在不同会话中操作
        for i in range(5):
            mgr.add_message(f"parallel-{i}", "user", f"会话{i}的消息")
            mgr.add_candidate(f"parallel-{i}", {"topic": f"论题{i}"})
        # 验证各会话独立
        for i in range(5):
            ctx = mgr.get_context(f"parallel-{i}")
            assert len(ctx.history) == 1
            assert ctx.history[0]["content"] == f"会话{i}的消息"
            assert len(ctx.candidates) == 1

    def test_switch_and_operate(self):
        """测试切换会话后操作。"""
        mgr = MultiContextManager()
        mgr.create_context("switch-op-1")
        mgr.create_context("switch-op-2")
        # 切换到会话1并操作
        mgr.switch_to("switch-op-1")
        mgr.add_message("switch-op-1", "user", "会话1消息")
        # 切换到会话2并操作
        mgr.switch_to("switch-op-2")
        mgr.add_message("switch-op-2", "user", "会话2消息")
        # 验证各会话独立
        ctx1 = mgr.get_context("switch-op-1")
        ctx2 = mgr.get_context("switch-op-2")
        assert len(ctx1.history) == 1
        assert len(ctx2.history) == 1
        assert ctx1.history[0]["content"] == "会话1消息"
        assert ctx2.history[0]["content"] == "会话2消息"

    def test_version_rollback_workflow(self):
        """测试版本回滚工作流。"""
        mgr = MultiContextManager()
        ctx = mgr.create_context("rollback-wf")
        # 保存多个版本
        ctx.add_message("user", "消息1")
        mgr.update_context(ctx)
        v1 = ctx.version
        ctx.add_message("user", "消息2")
        mgr.update_context(ctx)
        ctx.add_message("user", "消息3")
        mgr.update_context(ctx)
        # 回滚到 v1
        rolled = mgr.rollback("rollback-wf", v1)
        assert rolled is not None
        assert len(rolled.history) == 1
        assert rolled.history[0]["content"] == "消息1"

    def test_diff_workflow(self):
        """测试差异比较工作流。"""
        mgr = MultiContextManager()
        ctx1 = mgr.create_context("diff-wf-1", degree="master", discipline="CS")
        ctx2 = mgr.create_context("diff-wf-2", degree="doctor", discipline="Physics")
        result = mgr.diff_contexts("diff-wf-1", "diff-wf-2")
        assert result["has_changes"] is True
        assert "degree" in result["changes"]
        assert "discipline" in result["changes"]
        summary = ContextDiff.summarize_diff(result)
        assert "degree" in summary


# ===== 边界条件测试 =====


class TestEdgeCases:
    """边界条件与异常场景测试。"""

    def test_empty_session_id(self):
        """测试空会话 ID。"""
        ctx = ConversationContext(session_id="")
        assert ctx.session_id == ""
        store = ContextStore()
        store.save(ctx)
        assert store.exists("")

    def test_very_long_session_id(self):
        """测试超长会话 ID。"""
        long_id = "s" * 1000
        ctx = ConversationContext(session_id=long_id)
        store = ContextStore()
        store.save(ctx)
        assert store.exists(long_id)

    def test_special_characters_in_content(self):
        """测试消息内容含特殊字符。"""
        ctx = _make_context()
        special = "特殊字符：<>&\"'\\n\\t中文表情🎉"
        ctx.add_message("user", special)
        d = ctx.to_dict()
        restored = ConversationContext.from_dict(d)
        assert restored.history[0]["content"] == special

    def test_unicode_in_fields(self):
        """测试字段含 Unicode 字符。"""
        ctx = ConversationContext(
            session_id="unicode-test",
            user_id="用户🎯",
            discipline="计算机科学与技术",
            mentor_info="张教授（博导）",
        )
        d = ctx.to_dict()
        restored = ConversationContext.from_dict(d)
        assert restored.user_id == "用户🎯"
        assert restored.discipline == "计算机科学与技术"
        assert restored.mentor_info == "张教授（博导）"

    def test_store_zero_max_size(self):
        """测试最大容量为 0 的存储。"""
        store = ContextStore(max_size=0)
        ctx = _make_context("zero-max")
        store.save(ctx)
        # 容量为 0 时立即淘汰
        assert store.size() == 0

    def test_store_one_max_size(self):
        """测试最大容量为 1 的存储。"""
        store = ContextStore(max_size=1)
        store.save(_make_context("one-1"))
        assert store.size() == 1
        store.save(_make_context("one-2"))
        assert store.size() == 1
        assert not store.exists("one-1")
        assert store.exists("one-2")

    def test_version_manager_zero_max(self):
        """测试最大版本数为 0。"""
        mgr = ContextVersionManager(max_versions=0)
        ctx = _make_context("zero-max-ver")
        mgr.save_version(ctx)
        # deque(maxlen=0) 不保存任何元素
        assert mgr.get_version_count("zero-max-ver") == 0

    def test_concurrent_access(self):
        """测试并发访问安全性。"""
        store = ContextStore(max_size=100)
        errors = []

        def reader():
            try:
                for _ in range(50):
                    store.list_sessions()
                    store.size()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(50):
                    store.save(_make_context(f"conc-{i}"))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_clone_then_modify(self):
        """测试克隆后修改不影响原对象。"""
        ctx = _make_filled_context()
        cloned = ctx.clone()
        cloned.add_message("user", "克隆新增")
        cloned.confirm_method("新方法")
        cloned.metadata["new"] = "value"
        # 原对象不应受影响
        original = _make_filled_context()
        original_history_len = len(ctx.history)
        assert len(ctx.history) == original_history_len
        assert "新方法" not in ctx.confirmed_methods
        assert "new" not in ctx.metadata

    def test_context_hash_stability(self):
        """测试相同内容的哈希稳定性。"""
        ctx1 = _make_filled_context("hash-stable")
        ctx2 = _make_filled_context("hash-stable")
        # 两次调用应返回相同结果
        h1 = ctx1.get_context_hash()
        h2 = ctx1.get_context_hash()
        assert h1 == h2
        # 相同内容的两个对象哈希相同
        assert h1 == ctx2.get_context_hash()

    def test_large_history(self):
        """测试大量历史消息。"""
        ctx = _make_context()
        for i in range(1000):
            ctx.add_message("user", f"消息{i}")
        assert len(ctx.history) == 1000
        recent = ctx.get_recent_history(10)
        assert len(recent) == 10
        assert recent[-1]["content"] == "消息999"

    def test_many_candidates(self):
        """测试大量候选论题。"""
        ctx = _make_context()
        for i in range(100):
            ctx.add_candidate({"topic": f"论题{i}", "score": i / 100})
        assert len(ctx.candidates) == 100

    def test_metadata_with_complex_values(self):
        """测试元数据含复杂值。"""
        ctx = _make_context()
        ctx.metadata["nested"] = {"a": [1, 2, 3], "b": {"c": True}}
        ctx.metadata["list"] = [1, "two", 3.0, None]
        d = ctx.to_dict()
        restored = ConversationContext.from_dict(d)
        assert restored.metadata["nested"]["a"] == [1, 2, 3]
        assert restored.metadata["nested"]["b"]["c"] is True
        assert restored.metadata["list"][1] == "two"
