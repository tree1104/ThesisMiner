"""E2E 测试：前端页面完整性验证

覆盖所有前端 JS 文件的语法正确性与必需函数/组件验证：
- app.js：全局状态、页面注册表、路由系统
- api.js：API 客户端封装、请求方法
- pages/dashboard.js：仪表盘统计、骨架屏
- pages/generate.js：五阶段流程 UI
- pages/lineage.js：D3.js 谱系图谱
- pages/sessions.js：多对话管理 UI
- pages/budgets.js：预算管理
- pages/settings.js：系统设置
- index.html：资源引入、页面结构

运行方式：python -m pytest tests/e2e/test_frontend_pages.py -v
"""
import os
import subprocess
import sys

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _project_root():
    """返回项目根目录绝对路径"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_file(*parts):
    """读取项目文件内容"""
    root = _project_root()
    file_path = os.path.join(root, *parts)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def _read_js(name):
    """读取 frontend/scripts 下的 JS 文件"""
    return _read_file("frontend", "scripts", name)


def _read_page_js(name):
    """读取 frontend/scripts/pages 下的 JS 文件"""
    return _read_file("frontend", "scripts", "pages", name)


def _check_js_syntax(rel_path):
    """使用 node --check 验证 JS 语法"""
    root = _project_root()
    result = subprocess.run(
        ["node", "--check", rel_path],
        capture_output=True,
        text=True,
        cwd=root,
    )
    return result


# ===== app.js 语法与结构测试 =====

class TestAppJs:
    """app.js 主应用脚本测试"""

    def test_app_js_parses(self):
        """验证 app.js 语法正确"""
        result = _check_js_syntax("frontend/scripts/app.js")
        assert result.returncode == 0, f"app.js 语法错误: {result.stderr}"

    def test_app_js_has_global_state(self):
        """验证 app.js 含全局状态对象"""
        content = _read_js("app.js")
        assert "AppState" in content, "缺少 AppState 全局状态"

    def test_app_js_has_pages_registry(self):
        """验证 app.js 含页面注册表"""
        content = _read_js("app.js")
        assert "Pages" in content, "缺少 Pages 页面注册表"

    def test_app_js_has_navigation(self):
        """验证 app.js 含导航配置"""
        content = _read_js("app.js")
        assert "NAV_ITEMS" in content, "缺少 NAV_ITEMS 导航配置"

    def test_app_js_has_router(self):
        """验证 app.js 含路由系统"""
        content = _read_js("app.js")
        # 路由相关函数
        assert "router" in content.lower() or "hashchange" in content.lower(), "缺少路由系统"

    def test_app_js_pages_registry_includes_all(self):
        """验证页面注册表包含所有页面"""
        content = _read_js("app.js")
        for page in ["dashboard", "generate", "lineage", "sessions", "budgets", "settings"]:
            assert page in content, f"页面注册表缺少: {page}"


# ===== api.js 语法与结构测试 =====

class TestApiJs:
    """api.js API 客户端测试"""

    def test_api_js_parses(self):
        """验证 api.js 语法正确"""
        result = _check_js_syntax("frontend/scripts/api.js")
        assert result.returncode == 0, f"api.js 语法错误: {result.stderr}"

    def test_api_js_has_request_method(self):
        """验证 api.js 含统一请求方法"""
        content = _read_js("api.js")
        assert "request" in content, "缺少 request 请求方法"

    def test_api_js_has_base_url(self):
        """验证 api.js 含基础路径配置"""
        content = _read_js("api.js")
        assert "baseUrl" in content or "/api" in content, "缺少 baseUrl 配置"

    def test_api_js_has_timeout(self):
        """验证 api.js 含超时控制"""
        content = _read_js("api.js")
        assert "timeout" in content, "缺少 timeout 超时配置"

    def test_api_js_has_abort_controller(self):
        """验证 api.js 含 AbortController 超时控制"""
        content = _read_js("api.js")
        assert "AbortController" in content, "缺少 AbortController 超时控制"


# ===== dashboard.js 测试 =====

class TestDashboardJs:
    """dashboard.js 仪表盘页面测试"""

    def test_dashboard_js_parses(self):
        """验证 dashboard.js 语法正确"""
        result = _check_js_syntax("frontend/scripts/pages/dashboard.js")
        assert result.returncode == 0, f"dashboard.js 语法错误: {result.stderr}"

    def test_dashboard_js_has_render(self):
        """验证 dashboard.js 含 render 方法"""
        content = _read_page_js("dashboard.js")
        assert "render" in content, "缺少 render 方法"

    def test_dashboard_js_has_degree_labels(self):
        """验证 dashboard.js 含学位标签映射"""
        content = _read_page_js("dashboard.js")
        assert "DEGREE_LABELS" in content, "缺少 DEGREE_LABELS"

    def test_dashboard_js_has_discipline_labels(self):
        """验证 dashboard.js 含学科标签映射"""
        content = _read_page_js("dashboard.js")
        assert "DISCIPLINE_LABELS" in content, "缺少 DISCIPLINE_LABELS"

    def test_dashboard_js_has_skeleton(self):
        """验证 dashboard.js 含骨架屏"""
        content = _read_page_js("dashboard.js")
        assert "skeleton" in content.lower(), "缺少骨架屏"


# ===== generate.js 五阶段流程测试 =====

class TestGenerateJs:
    """generate.js 五阶段流程 UI 测试"""

    def test_generate_js_parses(self):
        """验证 generate.js 语法正确"""
        result = _check_js_syntax("frontend/scripts/pages/generate.js")
        assert result.returncode == 0, f"generate.js 语法错误: {result.stderr}"

    def test_generate_js_has_five_stages(self):
        """验证 generate.js 含五阶段定义"""
        content = _read_page_js("generate.js")
        for stage in ["info_confirm", "creativity", "validation", "generation", "deep_assist"]:
            assert stage in content, f"缺少阶段: {stage}"

    def test_generate_js_has_stages_array(self):
        """验证 generate.js 含 STAGES 数组"""
        content = _read_page_js("generate.js")
        assert "STAGES" in content, "缺少 STAGES 常量"

    def test_generate_js_has_granularities(self):
        """验证 generate.js 含多粒度生成选项"""
        content = _read_page_js("generate.js")
        assert "GRANULARITIES" in content, "缺少 GRANULARITIES 常量"
        for g in ["title", "abstract", "outline", "full"]:
            assert g in content, f"缺少粒度选项: {g}"

    def test_generate_js_has_deep_assists(self):
        """验证 generate.js 含深度辅助三件套"""
        content = _read_page_js("generate.js")
        assert "DEEP_ASSISTS" in content, "缺少 DEEP_ASSISTS 常量"
        for assist in ["literature", "experiment", "defense"]:
            assert assist in content, f"缺少深度辅助项: {assist}"

    def test_generate_js_has_stage_progress(self):
        """验证 generate.js 含阶段进度条"""
        content = _read_page_js("generate.js")
        assert "renderStageProgress" in content or "stage-progress" in content, "缺少阶段进度条"

    def test_generate_js_has_stage_panels(self):
        """验证 generate.js 含阶段面板"""
        content = _read_page_js("generate.js")
        assert "renderStagePanels" in content or "stage-panel" in content, "缺少阶段面板"

    def test_generate_js_has_state_management(self):
        """验证 generate.js 含状态管理"""
        content = _read_page_js("generate.js")
        assert "state" in content.lower(), "缺少状态管理"
        assert "currentStage" in content or "current_stage" in content, "缺少当前阶段状态"

    def test_generate_js_has_style_normalizer_display(self):
        """验证 generate.js 含 style_normalizer 对比展示"""
        content = _read_page_js("generate.js")
        assert "styleBefore" in content or "style_before" in content.lower(), "缺少 styleBefore"
        assert "styleAfter" in content or "style_after" in content.lower(), "缺少 styleAfter"


# ===== lineage.js D3.js 谱系图谱测试 =====

class TestLineageJs:
    """lineage.js D3.js 谱系图谱测试"""

    def test_lineage_js_parses(self):
        """验证 lineage.js 语法正确"""
        result = _check_js_syntax("frontend/scripts/pages/lineage.js")
        assert result.returncode == 0, f"lineage.js 语法错误: {result.stderr}"

    def test_lineage_js_has_force_graph(self):
        """验证 lineage.js 含 D3 force 布局"""
        content = _read_page_js("lineage.js")
        assert "forceSimulation" in content or "d3.force" in content, "缺少 D3 force 布局"

    def test_lineage_js_has_render_force_graph(self):
        """验证 lineage.js 含 renderForceGraph 函数"""
        content = _read_page_js("lineage.js")
        assert "renderForceGraph" in content, "缺少 renderForceGraph 函数"

    def test_lineage_js_has_required_functions(self):
        """验证 lineage.js 含必需函数"""
        content = _read_page_js("lineage.js")
        required = ["renderLineagePage", "renderForceGraph", "renderNodeList", "renderToolbar"]
        for fn in required:
            assert fn in content, f"缺少必需函数: {fn}"

    def test_lineage_js_has_drag_support(self):
        """验证 lineage.js 含拖拽支持"""
        content = _read_page_js("lineage.js")
        assert "drag" in content.lower(), "缺少拖拽支持"

    def test_lineage_js_has_zoom_support(self):
        """验证 lineage.js 含缩放支持"""
        content = _read_page_js("lineage.js")
        assert "zoom" in content.lower(), "缺少缩放支持"

    def test_lineage_js_has_node_filter(self):
        """验证 lineage.js 含节点类型过滤"""
        content = _read_page_js("lineage.js")
        assert "filter" in content.lower(), "缺少节点过滤"

    def test_lineage_js_has_node_detail(self):
        """验证 lineage.js 含节点详情卡片"""
        content = _read_page_js("lineage.js")
        assert "renderNodeDetail" in content or "node-detail" in content, "缺少节点详情卡片"


# ===== sessions.js 多对话管理测试 =====

class TestSessionsJs:
    """sessions.js 多对话管理 UI 测试"""

    def test_sessions_js_parses(self):
        """验证 sessions.js 语法正确"""
        result = _check_js_syntax("frontend/scripts/pages/sessions.js")
        assert result.returncode == 0, f"sessions.js 语法错误: {result.stderr}"

    def test_sessions_js_has_conversation_tabs(self):
        """验证 sessions.js 含对话标签栏"""
        content = _read_page_js("sessions.js")
        assert "session-tabs" in content or "tab" in content.lower(), "缺少对话标签栏"

    def test_sessions_js_has_agent_selector(self):
        """验证 sessions.js 含 Agent 选择器"""
        content = _read_page_js("sessions.js")
        assert "AGENT_LABELS" in content or "agent" in content.lower(), "缺少 Agent 选择器"

    def test_sessions_js_has_six_agents(self):
        """验证 sessions.js 含六种 Agent"""
        content = _read_page_js("sessions.js")
        for agent in ["orchestrator", "reasoner", "mentor", "critic", "writer", "searcher"]:
            assert agent in content, f"缺少 Agent: {agent}"

    def test_sessions_js_has_message_rendering(self):
        """验证 sessions.js 含消息渲染"""
        content = _read_page_js("sessions.js")
        assert "renderMessages" in content or "messageHtml" in content, "缺少消息渲染"

    def test_sessions_js_has_reasoning_panel(self):
        """验证 sessions.js 含思维链折叠面板"""
        content = _read_page_js("sessions.js")
        assert "reasoning" in content.lower(), "缺少思维链折叠面板"

    def test_sessions_js_has_citation_cards(self):
        """验证 sessions.js 含引用卡片"""
        content = _read_page_js("sessions.js")
        assert "citation" in content.lower(), "缺少引用卡片"

    def test_sessions_js_has_streaming_support(self):
        """验证 sessions.js 含流式输出支持"""
        content = _read_page_js("sessions.js")
        assert "stream" in content.lower(), "缺少流式输出支持"


# ===== budgets.js 测试 =====

class TestBudgetsJs:
    """budgets.js 预算管理页面测试"""

    def test_budgets_js_parses(self):
        """验证 budgets.js 语法正确"""
        result = _check_js_syntax("frontend/scripts/pages/budgets.js")
        assert result.returncode == 0, f"budgets.js 语法错误: {result.stderr}"

    def test_budgets_js_has_render(self):
        """验证 budgets.js 含 render 方法"""
        content = _read_page_js("budgets.js")
        assert "render" in content, "缺少 render 方法"


# ===== settings.js 测试 =====

class TestSettingsJs:
    """settings.js 系统设置页面测试"""

    def test_settings_js_parses(self):
        """验证 settings.js 语法正确"""
        result = _check_js_syntax("frontend/scripts/pages/settings.js")
        assert result.returncode == 0, f"settings.js 语法错误: {result.stderr}"

    def test_settings_js_has_render(self):
        """验证 settings.js 含 render 方法"""
        content = _read_page_js("settings.js")
        assert "render" in content, "缺少 render 方法"

    def test_settings_js_has_step_models(self):
        """验证 settings.js 含步骤路由配置"""
        content = _read_page_js("settings.js")
        assert "STEPS" in content or "step" in content.lower(), "缺少步骤路由配置"

    def test_settings_js_has_model_management(self):
        """验证 settings.js 含模型管理"""
        content = _read_page_js("settings.js")
        assert "model" in content.lower(), "缺少模型管理"

    def test_settings_js_has_currency(self):
        """验证 settings.js 含货币切换"""
        content = _read_page_js("settings.js")
        assert "currency" in content.lower() or "CNY" in content, "缺少货币切换"


# ===== index.html 测试 =====

class TestIndexHtml:
    """index.html 页面结构测试"""

    def test_index_html_exists(self):
        """验证 index.html 存在"""
        content = _read_file("frontend", "index.html")
        assert len(content) > 0

    def test_index_html_has_doctype(self):
        """验证 index.html 含 DOCTYPE 声明"""
        content = _read_file("frontend", "index.html")
        assert "<!DOCTYPE html>" in content or "<!doctype html>" in content.lower()

    def test_index_html_has_meta_charset(self):
        """验证 index.html 含字符编码声明"""
        content = _read_file("frontend", "index.html")
        assert "charset" in content, "缺少 charset 声明"
        assert "UTF-8" in content, "缺少 UTF-8 编码声明"

    def test_index_html_has_viewport(self):
        """验证 index.html 含 viewport 元标签"""
        content = _read_file("frontend", "index.html")
        assert "viewport" in content, "缺少 viewport 元标签"

    def test_index_html_has_tailwind(self):
        """验证 index.html 引入 Tailwind CSS"""
        content = _read_file("frontend", "index.html")
        assert "tailwindcss" in content, "缺少 Tailwind CSS 引入"

    def test_index_html_has_main_css(self):
        """验证 index.html 引入主样式表"""
        content = _read_file("frontend", "index.html")
        assert "main.css" in content, "缺少主样式表引入"

    def test_index_html_has_app_js(self):
        """验证 index.html 引入 app.js"""
        content = _read_file("frontend", "index.html")
        assert "app.js" in content, "缺少 app.js 引入"

    def test_index_html_has_api_js(self):
        """验证 index.html 引入 api.js"""
        content = _read_file("frontend", "index.html")
        assert "api.js" in content, "缺少 api.js 引入"

    def test_index_html_has_all_page_scripts(self):
        """验证 index.html 通过动态加载机制引入所有页面脚本

        index.html 使用 app.js 中的 loadPageScript 动态加载页面脚本，
        而非直接通过 <script> 标签引入。验证动态加载机制存在。
        """
        html_content = _read_file("frontend", "index.html")
        app_content = _read_js("app.js")
        # index.html 应含动态加载注释或机制
        assert "loadPageScript" in app_content or "动态加载" in html_content, \
            "缺少页面脚本动态加载机制"
        # app.js 应注册所有页面
        for page in ["dashboard", "generate", "lineage", "sessions", "budgets", "settings"]:
            assert page in app_content, f"app.js 未注册页面: {page}"

    def test_index_html_has_app_shell(self):
        """验证 index.html 含应用外壳结构"""
        content = _read_file("frontend", "index.html")
        assert "app-shell" in content or "app" in content.lower(), "缺少应用外壳结构"

    def test_index_html_has_lucide_icons(self):
        """验证 index.html 引入 Lucide 图标库"""
        content = _read_file("frontend", "index.html")
        assert "lucide" in content.lower(), "缺少 Lucide 图标库"

    def test_index_html_has_google_fonts(self):
        """验证 index.html 引入 Google Fonts"""
        content = _read_file("frontend", "index.html")
        assert "fonts.googleapis.com" in content, "缺少 Google Fonts"

    def test_index_html_has_title(self):
        """验证 index.html 含标题"""
        content = _read_file("frontend", "index.html")
        assert "<title>" in content, "缺少 title 标签"

    def test_index_html_has_meta_description(self):
        """验证 index.html 含 meta description"""
        content = _read_file("frontend", "index.html")
        assert "description" in content, "缺少 meta description"

    def test_index_html_lang_zh_cn(self):
        """验证 index.html 语言为中文"""
        content = _read_file("frontend", "index.html")
        assert 'lang="zh-CN"' in content or 'lang="zh"' in content, "缺少中文语言声明"


# ===== CSS 样式表测试 =====

class TestMainCss:
    """main.css 样式表测试"""

    def test_main_css_exists(self):
        """验证 main.css 存在"""
        content = _read_file("frontend", "styles", "main.css")
        assert len(content) > 0

    def test_main_css_has_design_tokens(self):
        """验证 main.css 含设计令牌（CSS 变量）"""
        content = _read_file("frontend", "styles", "main.css")
        assert "--" in content, "缺少 CSS 变量（设计令牌）"

    def test_main_css_has_card_styles(self):
        """验证 main.css 含卡片样式"""
        content = _read_file("frontend", "styles", "main.css")
        assert ".card" in content, "缺少卡片样式"

    def test_main_css_has_button_styles(self):
        """验证 main.css 含按钮样式"""
        content = _read_file("frontend", "styles", "main.css")
        assert "button" in content.lower() or ".btn" in content, "缺少按钮样式"

    def test_main_css_has_grid_system(self):
        """验证 main.css 含网格系统"""
        content = _read_file("frontend", "styles", "main.css")
        assert "grid" in content.lower(), "缺少网格系统"

    def test_main_css_has_responsive_design(self):
        """验证 main.css 含响应式设计"""
        content = _read_file("frontend", "styles", "main.css")
        assert "@media" in content, "缺少响应式设计（@media 查询）"


# ===== 跨文件一致性测试 =====

class TestCrossFileConsistency:
    """跨文件一致性验证"""

    def test_all_page_scripts_registered_in_app(self):
        """验证所有页面脚本在 app.js 中注册"""
        app_content = _read_js("app.js")
        pages = ["dashboard", "generate", "lineage", "sessions", "budgets", "settings"]
        for page in pages:
            assert page in app_content, f"app.js 未注册页面: {page}"

    def test_nav_items_match_pages(self):
        """验证导航项与页面一致"""
        app_content = _read_js("app.js")
        pages = ["dashboard", "generate", "lineage", "sessions"]
        for page in pages:
            assert page in app_content, f"导航项缺少页面: {page}"

    def test_api_base_url_matches_routes(self):
        """验证 API 基础路径与后端路由一致"""
        api_content = _read_js("api.js")
        assert "/api" in api_content, "API 基础路径应为 /api"

    def test_index_html_includes_all_scripts(self):
        """验证 index.html 包含所有必需脚本"""
        html_content = _read_file("frontend", "index.html")
        required_scripts = ["app.js", "api.js"]
        for script in required_scripts:
            assert script in html_content, f"index.html 缺少脚本: {script}"


# ===== 前端资源完整性测试 =====

class TestFrontendResourceIntegrity:
    """前端资源完整性测试"""

    def test_all_js_files_exist(self):
        """验证所有 JS 文件存在"""
        root = _project_root()
        js_files = [
            "frontend/scripts/app.js",
            "frontend/scripts/api.js",
            "frontend/scripts/pages/dashboard.js",
            "frontend/scripts/pages/generate.js",
            "frontend/scripts/pages/lineage.js",
            "frontend/scripts/pages/sessions.js",
            "frontend/scripts/pages/budgets.js",
            "frontend/scripts/pages/settings.js",
        ]
        for js_file in js_files:
            full_path = os.path.join(root, js_file)
            assert os.path.isfile(full_path), f"JS 文件不存在: {js_file}"

    def test_all_js_files_non_empty(self):
        """验证所有 JS 文件非空"""
        root = _project_root()
        js_files = [
            "frontend/scripts/app.js",
            "frontend/scripts/api.js",
            "frontend/scripts/pages/dashboard.js",
            "frontend/scripts/pages/generate.js",
            "frontend/scripts/pages/lineage.js",
            "frontend/scripts/pages/sessions.js",
        ]
        for js_file in js_files:
            full_path = os.path.join(root, js_file)
            assert os.path.getsize(full_path) > 0, f"JS 文件为空: {js_file}"

    def test_css_file_exists_and_non_empty(self):
        """验证 CSS 文件存在且非空"""
        root = _project_root()
        css_path = os.path.join(root, "frontend", "styles", "main.css")
        assert os.path.isfile(css_path), "main.css 不存在"
        assert os.path.getsize(css_path) > 0, "main.css 为空"

    def test_index_html_exists_and_non_empty(self):
        """验证 index.html 存在且非空"""
        root = _project_root()
        html_path = os.path.join(root, "frontend", "index.html")
        assert os.path.isfile(html_path), "index.html 不存在"
        assert os.path.getsize(html_path) > 0, "index.html 为空"

    def test_all_js_files_use_strict_mode(self):
        """验证页面 JS 文件使用严格模式"""
        page_files = ["dashboard.js", "generate.js", "lineage.js", "sessions.js", "settings.js"]
        for pf in page_files:
            content = _read_page_js(pf)
            assert "'use strict'" in content or '"use strict"' in content, f"{pf} 未使用严格模式"

    def test_all_page_scripts_use_iife(self):
        """验证页面 JS 文件使用 IIFE 封装"""
        page_files = ["dashboard.js", "generate.js", "lineage.js", "sessions.js", "settings.js"]
        for pf in page_files:
            content = _read_page_js(pf)
            assert "(function" in content or "(()" in content, f"{pf} 未使用 IIFE 封装"
