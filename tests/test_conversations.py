"""Task 7：对话管理后端测试

验证：
- 创建对话、列出对话、获取对话、删除对话、重命名对话
- 添加消息、获取消息
- 上下文隔离：同一会话下两条对话的消息互不干扰
- 消息引用的存储与检索
- 上下文窗口与 DST 压缩
- 使用临时测试数据库（覆盖 DB_PATH）

运行方式：python -m pytest tests/test_conversations.py -v
或直接运行：python tests/test_conversations.py
"""
import os
import sys
import tempfile

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 在导入 backend 模块前，切换到临时数据库，避免污染正式数据
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_test_")
_tmp_db = os.path.join(_tmp_dir, "test_thesis_miner.db")
_db.DB_PATH = _tmp_db
_db.init_db()

from backend.sessions.conversation_manager import (
    ConversationManager,
    get_conversation_manager,
)
from backend.sessions import session_manager
from backend.models import SessionCreate, DegreeType, DisciplineType


def _make_session(title: str = "测试会话") -> str:
    """创建一个测试会话，返回 session_id。"""
    req = SessionCreate(
        title=title,
        degree=DegreeType.master,
        discipline=DisciplineType.science_engineering,
        mentor_info="测试导师",
    )
    session = session_manager.create_session(req)
    return session["id"]


# ---------------- 对话 CRUD 测试 ----------------


def test_create_conversation():
    """测试创建对话"""
    cm = ConversationManager()
    sid = _make_session("创建对话测试")
    conv = cm.create_conversation(sid, title="第一条对话", agent_id="orchestrator")
    assert conv is not None
    assert conv["session_id"] == sid
    assert conv["title"] == "第一条对话"
    assert conv["agent_id"] == "orchestrator"
    assert conv["status"] == "active"
    assert conv["message_count"] == 0
    print("✓ 创建对话")


def test_list_conversations():
    """测试列出对话"""
    cm = ConversationManager()
    sid = _make_session("列出对话测试")
    # create_session 已自动创建 1 条默认对话
    conv1 = cm.create_conversation(sid, title="对话A")
    conv2 = cm.create_conversation(sid, title="对话B")
    convs = cm.list_conversations(sid)
    # 默认 + 2 条新对话 = 3 条
    assert len(convs) == 3
    titles = [c["title"] for c in convs]
    assert "对话A" in titles
    assert "对话B" in titles
    print("✓ 列出对话")


def test_get_conversation():
    """测试获取对话详情"""
    cm = ConversationManager()
    sid = _make_session("获取对话测试")
    conv = cm.create_conversation(sid, title="待获取对话")
    fetched = cm.get_conversation(conv["id"])
    assert fetched is not None
    assert fetched["id"] == conv["id"]
    assert fetched["title"] == "待获取对话"
    print("✓ 获取对话详情")


def test_get_conversation_not_found():
    """测试获取不存在的对话返回 None"""
    cm = ConversationManager()
    assert cm.get_conversation("不存在的ID") is None
    print("✓ 获取不存在的对话返回 None")


def test_rename_conversation():
    """测试重命名对话"""
    cm = ConversationManager()
    sid = _make_session("重命名对话测试")
    conv = cm.create_conversation(sid, title="旧标题")
    renamed = cm.rename_conversation(conv["id"], "新标题")
    assert renamed is not None
    assert renamed["title"] == "新标题"
    print("✓ 重命名对话")


def test_rename_conversation_not_found():
    """测试重命名不存在的对话返回 None"""
    cm = ConversationManager()
    assert cm.rename_conversation("不存在的ID", "新标题") is None
    print("✓ 重命名不存在的对话返回 None")


def test_delete_conversation():
    """测试删除对话"""
    cm = ConversationManager()
    sid = _make_session("删除对话测试")
    conv = cm.create_conversation(sid, title="待删除对话")
    assert cm.delete_conversation(conv["id"]) is True
    # 删除后获取应返回 None
    assert cm.get_conversation(conv["id"]) is None
    print("✓ 删除对话")


def test_delete_conversation_not_found():
    """测试删除不存在的对话返回 False"""
    cm = ConversationManager()
    assert cm.delete_conversation("不存在的ID") is False
    print("✓ 删除不存在的对话返回 False")


def test_set_active():
    """测试设置激活对话"""
    cm = ConversationManager()
    sid = _make_session("激活对话测试")
    conv1 = cm.create_conversation(sid, title="对话1")
    conv2 = cm.create_conversation(sid, title="对话2")
    # 设置激活对话为 conv2
    assert cm.set_active(sid, conv2["id"]) is True
    session = session_manager.get_session(sid)
    assert session["active_conversation_id"] == conv2["id"]
    print("✓ 设置激活对话")


# ---------------- 消息管理测试 ----------------


def test_add_and_get_message():
    """测试添加消息与获取消息"""
    cm = ConversationManager()
    sid = _make_session("消息测试")
    conv = cm.create_conversation(sid, title="消息对话")
    msg = cm.add_message(
        conv["id"],
        role="user",
        content="你好，请帮我生成论题",
        agent_id="orchestrator",
    )
    assert msg is not None
    assert msg["role"] == "user"
    assert msg["content"] == "你好，请帮我生成论题"
    assert msg["agent_id"] == "orchestrator"
    # 获取消息列表
    messages = cm.get_messages(conv["id"])
    assert len(messages) == 1
    assert messages[0]["content"] == "你好，请帮我生成论题"
    print("✓ 添加与获取消息")


def test_add_message_with_search_results():
    """测试带搜索结果的消息"""
    cm = ConversationManager()
    sid = _make_session("搜索结果测试")
    conv = cm.create_conversation(sid, title="搜索对话")
    search_results = [
        {"title": "论文A", "url": "https://example.com/a"},
        {"title": "论文B", "url": "https://example.com/b"},
    ]
    token_usage = {"prompt_tokens": 100, "completion_tokens": 50}
    msg = cm.add_message(
        conv["id"],
        role="assistant",
        content="根据搜索结果...",
        agent_id="search",
        search_results=search_results,
        token_usage=token_usage,
    )
    assert msg["search_results"] == search_results
    assert msg["token_usage"] == token_usage
    print("✓ 带搜索结果的消息")


def test_get_messages_empty():
    """测试获取空对话的消息列表"""
    cm = ConversationManager()
    sid = _make_session("空消息测试")
    conv = cm.create_conversation(sid, title="空对话")
    messages = cm.get_messages(conv["id"])
    assert messages == []
    print("✓ 空对话消息列表")


def test_get_message_not_found():
    """测试获取不存在的消息返回 None"""
    cm = ConversationManager()
    assert cm.get_message("不存在的ID") is None
    print("✓ 获取不存在的消息返回 None")


# ---------------- 上下文隔离测试 ----------------


def test_context_isolation():
    """测试上下文隔离：同一会话下两条对话的消息互不干扰"""
    cm = ConversationManager()
    sid = _make_session("隔离测试")
    conv1 = cm.create_conversation(sid, title="对话线1")
    conv2 = cm.create_conversation(sid, title="对话线2")
    # 向对话1添加消息
    cm.add_message(conv1["id"], role="user", content="对话1的消息A")
    cm.add_message(conv1["id"], role="assistant", content="对话1的回复A")
    # 向对话2添加消息
    cm.add_message(conv2["id"], role="user", content="对话2的消息B")
    # 验证对话1只有2条消息
    msgs1 = cm.get_messages(conv1["id"])
    assert len(msgs1) == 2
    contents1 = [m["content"] for m in msgs1]
    assert "对话1的消息A" in contents1
    assert "对话1的回复A" in contents1
    assert "对话2的消息B" not in contents1
    # 验证对话2只有1条消息
    msgs2 = cm.get_messages(conv2["id"])
    assert len(msgs2) == 1
    assert msgs2[0]["content"] == "对话2的消息B"
    print("✓ 上下文隔离")


# ---------------- 引用存储与检索测试 ----------------


def test_message_citations():
    """测试消息引用的存储与检索"""
    cm = ConversationManager()
    sid = _make_session("引用测试")
    conv = cm.create_conversation(sid, title="引用对话")
    citations = [
        {
            "url": "https://arxiv.org/abs/2401.00001",
            "title": "深度学习综述",
            "snippet": "本文综述了深度学习的最新进展...",
            "source_domain": "arxiv.org",
            "favicon": "https://www.google.com/s2/favicons?domain=arxiv.org",
        },
        {
            "url": "https://example.com/paper2",
            "title": "第二篇论文",
            "snippet": "关于CNN的应用",
            "source_domain": "example.com",
            "favicon": "",
        },
    ]
    msg = cm.add_message(
        conv["id"],
        role="assistant",
        content="根据相关研究 [1] [2]",
        agent_id="search",
        citations=citations,
    )
    # 检索引用
    fetched_cites = cm.get_message_citations(msg["id"])
    assert len(fetched_cites) == 2
    urls = [c["url"] for c in fetched_cites]
    assert "https://arxiv.org/abs/2401.00001" in urls
    assert "https://example.com/paper2" in urls
    # 验证引用字段
    first = next(c for c in fetched_cites if c["url"] == "https://arxiv.org/abs/2401.00001")
    assert first["title"] == "深度学习综述"
    assert first["source_domain"] == "arxiv.org"
    print("✓ 消息引用存储与检索")


def test_message_no_citations():
    """测试无引用消息"""
    cm = ConversationManager()
    sid = _make_session("无引用测试")
    conv = cm.create_conversation(sid, title="无引用对话")
    msg = cm.add_message(conv["id"], role="user", content="普通消息")
    cites = cm.get_message_citations(msg["id"])
    assert cites == []
    print("✓ 无引用消息")


def test_delete_conversation_cascades_citations():
    """测试删除对话级联删除消息与引用"""
    cm = ConversationManager()
    sid = _make_session("级联删除测试")
    conv = cm.create_conversation(sid, title="级联对话")
    cm.add_message(
        conv["id"],
        role="assistant",
        content="带引用的消息",
        citations=[{"url": "https://example.com/c", "title": "引用C"}],
    )
    msg_id = cm.get_messages(conv["id"])[0]["id"]
    # 删除对话
    assert cm.delete_conversation(conv["id"]) is True
    # 消息应被级联删除
    assert cm.get_message(msg_id) is None
    # 引用应被级联删除
    assert cm.get_message_citations(msg_id) == []
    print("✓ 删除对话级联删除消息与引用")


# ---------------- 上下文窗口与 DST 压缩测试 ----------------


def test_context_window_small():
    """测试上下文窗口（消息数较少时无需压缩）"""
    cm = ConversationManager()
    sid = _make_session("小窗口测试")
    conv = cm.create_conversation(sid, title="小窗口对话")
    cm.add_message(conv["id"], role="user", content="短消息1")
    cm.add_message(conv["id"], role="assistant", content="短回复1")
    window = cm.get_context_window(conv["id"], max_tokens=8000)
    # 消息少，全部纳入窗口，无摘要
    assert len(window) == 2
    assert all(m.get("role") != "system" or "[对话状态摘要]" not in m.get("content", "")
               for m in window)
    print("✓ 上下文窗口（无压缩）")


def test_context_window_empty():
    """测试空对话的上下文窗口"""
    cm = ConversationManager()
    sid = _make_session("空窗口测试")
    conv = cm.create_conversation(sid, title="空窗口对话")
    window = cm.get_context_window(conv["id"])
    assert window == []
    print("✓ 空对话上下文窗口")


def test_context_window_with_dst_compression():
    """测试上下文窗口 DST 压缩：超出窗口的旧消息被压缩为摘要"""
    cm = ConversationManager()
    sid = _make_session("DST压缩测试")
    conv = cm.create_conversation(sid, title="压缩对话")
    # 添加多条较长消息，使总 token 超过小窗口限制
    long_text = "这是一段较长的对话内容用于测试DST压缩功能，" * 10
    for i in range(6):
        cm.add_message(
            conv["id"],
            role="user" if i % 2 == 0 else "assistant",
            content=f"消息{i}: {long_text}",
        )
    # 设置很小的 max_tokens，强制触发压缩
    window = cm.get_context_window(conv["id"], max_tokens=50)
    # 窗口应小于总消息数（6条）
    assert len(window) < 6
    # 应包含 DST 摘要系统消息（首条）
    assert window[0]["role"] == "system"
    assert "[对话状态摘要]" in window[0]["content"]
    print("✓ 上下文窗口 DST 压缩")


# ---------------- session_manager 委托测试 ----------------


def test_session_manager_delegation():
    """测试 session_manager 对对话操作的委托"""
    sid = _make_session("委托测试")
    # 通过 session_manager 委托创建对话
    conv = session_manager.create_conversation(sid, title="委托对话")
    assert conv is not None
    # 委托列出对话
    convs = session_manager.list_conversations(sid)
    assert any(c["id"] == conv["id"] for c in convs)
    # 委托获取对话
    fetched = session_manager.get_conversation(conv["id"])
    assert fetched["title"] == "委托对话"
    # 委托重命名
    renamed = session_manager.rename_conversation(conv["id"], "委托改名")
    assert renamed["title"] == "委托改名"
    # 委托添加消息
    msg = session_manager.add_conversation_message(
        conv["id"], role="user", content="委托消息"
    )
    assert msg["content"] == "委托消息"
    # 委托获取消息
    msgs = session_manager.get_conversation_messages(conv["id"])
    assert len(msgs) == 1
    # 委托获取上下文
    ctx = session_manager.get_conversation_context(conv["id"])
    assert len(ctx) == 1
    # 委托删除对话
    assert session_manager.delete_conversation(conv["id"]) is True
    print("✓ session_manager 委托")


def test_create_session_auto_conversation():
    """测试创建会话时自动创建默认对话"""
    req = SessionCreate(
        title="自动对话测试",
        degree=DegreeType.doctor,
        discipline=DisciplineType.humanities_social,
        mentor_info="博导",
    )
    session = session_manager.create_session(req)
    # 应有 active_conversation_id
    assert session["active_conversation_id"] is not None
    # 应有 conversations 列表，含 1 条默认对话
    assert len(session["conversations"]) == 1
    default_conv = session["conversations"][0]
    assert default_conv["session_id"] == session["id"]
    print("✓ 创建会话自动创建默认对话")


def test_get_session_includes_conversations():
    """测试获取会话详情包含对话列表与激活对话"""
    sid = _make_session("详情对话测试")
    session = session_manager.get_session(sid)
    assert session is not None
    assert "conversations" in session
    assert "active_conversation" in session
    assert session["active_conversation"] is not None
    assert session["active_conversation"]["id"] == session["active_conversation_id"]
    print("✓ 获取会话详情包含对话列表")


def test_rename_session():
    """测试重命名会话"""
    sid = _make_session("原名")
    renamed = session_manager.rename_session(sid, "新名会话")
    assert renamed is not None
    assert renamed["title"] == "新名会话"
    print("✓ 重命名会话")


def test_get_conversation_manager_singleton():
    """测试对话管理器单例"""
    cm1 = get_conversation_manager()
    cm2 = get_conversation_manager()
    assert cm1 is cm2
    print("✓ 对话管理器单例")


if __name__ == "__main__":
    test_create_conversation()
    test_list_conversations()
    test_get_conversation()
    test_get_conversation_not_found()
    test_rename_conversation()
    test_rename_conversation_not_found()
    test_delete_conversation()
    test_delete_conversation_not_found()
    test_set_active()
    test_add_and_get_message()
    test_add_message_with_search_results()
    test_get_messages_empty()
    test_get_message_not_found()
    test_context_isolation()
    test_message_citations()
    test_message_no_citations()
    test_delete_conversation_cascades_citations()
    test_context_window_small()
    test_context_window_empty()
    test_context_window_with_dst_compression()
    test_session_manager_delegation()
    test_create_session_auto_conversation()
    test_get_session_includes_conversations()
    test_rename_session()
    test_get_conversation_manager_singleton()
    print("\n所有对话管理测试通过 ✓")
