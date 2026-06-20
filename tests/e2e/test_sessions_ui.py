"""E2E 测试：多对话管理 UI（Task 12）验证"""
import subprocess
import os


def _project_root():
    """返回项目根目录绝对路径"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_js(name):
    root = _project_root()
    js_path = os.path.join(root, "frontend", "scripts", "pages", name)
    with open(js_path, "r", encoding="utf-8") as f:
        return f.read()


def test_sessions_js_parses():
    """验证 sessions.js 语法正确"""
    root = _project_root()
    result = subprocess.run(
        ["node", "--check", "frontend/scripts/pages/sessions.js"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    assert result.returncode == 0, f"sessions.js 语法错误: {result.stderr}"


def test_sessions_js_has_conversation_tabs():
    """验证 sessions.js 包含对话标签栏（新建/切换/关闭/重命名）"""
    content = _read_js("sessions.js")
    # 对话标签栏容器
    assert "session-tabs" in content, "缺少 .session-tabs 标签栏容器"
    # 新建对话按钮
    assert "session-tab-new" in content, "缺少新建对话按钮"
    assert "openNewConversationDrawer" in content, "缺少新建对话抽屉方法"
    # 切换对话
    assert "selectConversation" in content, "缺少切换对话方法"
    assert "session-tab--active" in content, "缺少激活态样式类"
    # 关闭对话
    assert "close-tab" in content, "缺少关闭对话按钮"
    assert "confirmCloseConversation" in content, "缺少关闭对话确认方法"
    # 重命名对话（双击）
    assert "renameConversation" in content, "缺少重命名对话方法"


def test_sessions_js_has_agent_selector():
    """验证 sessions.js 包含 Agent 选择器（6 种 Agent）"""
    content = _read_js("sessions.js")
    assert "AGENT_LABELS" in content, "缺少 AGENT_LABELS 常量"
    assert "AGENT_COLORS" in content, "缺少 AGENT_COLORS 常量"
    # 六种 Agent
    for agent in ["orchestrator", "reasoner", "mentor", "critic", "writer", "searcher"]:
        assert agent in content, f"缺少 Agent 类型: {agent}"
    # 输入区 Agent 选择器
    assert "session-input" in content, "缺少输入区容器"
    assert "bindInputArea" in content, "缺少输入区事件绑定方法"
    assert "handleSend" in content, "缺少发送消息方法"


def test_sessions_js_has_message_rendering():
    """验证 sessions.js 消息列表渲染（agent 标签/role/content/reasoning/citations）"""
    content = _read_js("sessions.js")
    assert "renderMessages" in content, "缺少消息渲染方法"
    assert "messageHtml" in content, "缺少单条消息渲染方法"
    # agent_id 标签（颜色编码）
    assert "session-message__agent" in content, "缺少 agent 标签元素"
    assert "hexToRgba" in content, "缺少颜色转换工具"
    # role
    assert "session-message__role" in content, "缺少 role 元素"
    # content
    assert "session-message__bubble" in content, "缺少 content 气泡"
    # reasoning（可折叠）
    assert "session-reasoning" in content, "缺少 reasoning 折叠面板"
    assert "session-reasoning__toggle" in content, "缺少 reasoning 折叠开关"
    assert "session-reasoning--open" in content, "缺少 reasoning 展开状态"


def test_sessions_js_has_citation_cards():
    """验证 sessions.js 引用卡片组件（标题/摘要/域名/favicon/点击打开）"""
    content = _read_js("sessions.js")
    assert "citationHtml" in content, "缺少引用卡片渲染方法"
    assert "session-citation" in content, "缺少引用卡片类"
    assert "session-citation__title" in content, "缺少引用标题"
    assert "session-citation__snippet" in content, "缺少引用摘要"
    assert "session-citation__domain" in content, "缺少引用来源域名"
    assert "session-citation__favicon" in content, "缺少引用 favicon"
    assert "session-citations__grid" in content, "缺少引用网格布局"
    # 点击新窗口打开
    assert 'target="_blank"' in content, "缺少新窗口打开链接"
    assert "extractDomain" in content, "缺少域名提取工具"


def test_sessions_js_has_streaming():
    """验证 sessions.js 流式输出（reasoning 实时追加/content 实时追加/citations 流后渲染）"""
    content = _read_js("sessions.js")
    assert "startSseStreaming" in content, "缺少流式启动方法"
    assert "finalizeStreaming" in content, "缺少流式结束方法"
    assert "stopStreaming" in content, "缺少流式停止方法"
    # 流式状态标记
    assert "_streaming" in content, "缺少流式状态标记"
    # SSE 流式配置
    assert "streamAbortController" in content, "缺少流式中断控制器"
    assert "text/event-stream" in content, "缺少 SSE 内容类型"


def test_sessions_js_has_context_isolation():
    """验证 sessions.js 切换标签上下文隔离"""
    content = _read_js("sessions.js")
    # 按 conversation_id 加载消息
    assert "loadMessages" in content, "缺少消息加载方法"
    assert "getConversationMessages" in content, "缺少按 conversation_id 获取消息 API"
    # 会话状态隔离
    assert "activeConversationId" in content, "缺少激活对话 ID 状态"
    assert "activeSessionId" in content, "缺少激活会话 ID 状态"


def test_sessions_js_registers_page():
    """验证 sessions.js 注册到 Pages 注册表"""
    content = _read_js("sessions.js")
    assert "window.Pages" in content, "未注册到 window.Pages"
    assert "sessions" in content, "缺少 sessions 页面键"


def test_sessions_css_has_styles():
    """验证 main.css 包含 session- 前缀样式"""
    root = _project_root()
    css_path = os.path.join(root, "frontend", "styles", "main.css")
    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert ".session-sidebar" in content, "缺少 .session-sidebar 样式"
    assert ".session-tabs" in content, "缺少 .session-tabs 样式"
    assert ".session-tab" in content, "缺少 .session-tab 样式"
    assert ".session-message" in content, "缺少 .session-message 样式"
    assert ".session-citation" in content, "缺少 .session-citation 样式"
    assert ".session-reasoning" in content, "缺少 .session-reasoning 样式"
    assert ".session-input" in content, "缺少 .session-input 样式"
    assert ".session-empty" in content, "缺少 .session-empty 样式"


def test_sessions_css_has_agent_tokens():
    """验证 main.css 包含 Agent 配色 CSS 变量"""
    root = _project_root()
    css_path = os.path.join(root, "frontend", "styles", "main.css")
    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "--agent-orchestrator" in content, "缺少 --agent-orchestrator 变量"
    assert "--agent-reasoner" in content, "缺少 --agent-reasoner 变量"
    assert "--agent-mentor" in content, "缺少 --agent-mentor 变量"
    assert "--agent-critic" in content, "缺少 --agent-critic 变量"
    assert "--agent-writer" in content, "缺少 --agent-writer 变量"
    assert "--agent-searcher" in content, "缺少 --agent-searcher 变量"


def test_api_has_conversation_methods():
    """验证 api.js 包含对话管理 API 方法"""
    root = _project_root()
    api_path = os.path.join(root, "frontend", "scripts", "api.js")
    with open(api_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "getConversations" in content, "缺少 getConversations 方法"
    assert "createConversation" in content, "缺少 createConversation 方法"
    assert "getConversationMessages" in content, "缺少 getConversationMessages 方法"
    assert "addMessage" in content, "缺少 addMessage 方法"
    assert "deleteConversation" in content, "缺少 deleteConversation 方法"
    assert "renameConversation" in content, "缺少 renameConversation 方法"
    assert "getAgents" in content, "缺少 getAgents 方法"
    assert "getMessageCitations" in content, "缺少 getMessageCitations 方法"
    assert "setActiveConversation" in content, "缺少 setActiveConversation 方法"
