"""E2E 测试：谱系图谱 D3.js 重构验证"""
import subprocess
import os


def _project_root():
    """返回项目根目录绝对路径"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_lineage_js_parses():
    """验证 lineage.js 语法正确"""
    root = _project_root()
    result = subprocess.run(
        ["node", "--check", "frontend/scripts/pages/lineage.js"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    assert result.returncode == 0, f"lineage.js 语法错误: {result.stderr}"


def test_d3_included_in_html():
    """验证 D3.js 已在 index.html 中引入"""
    root = _project_root()
    html_path = os.path.join(root, "frontend", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "d3.v7" in content or "d3.js" in content, "D3.js 未在 index.html 中引入"


def test_lineage_js_has_force_graph():
    """验证 lineage.js 包含 force graph 实现"""
    root = _project_root()
    js_path = os.path.join(root, "frontend", "scripts", "pages", "lineage.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "forceSimulation" in content or "d3.force" in content, "缺少 D3 force 布局"
    assert "renderForceGraph" in content, "缺少 renderForceGraph 函数"


def test_lineage_js_has_required_functions():
    """验证 lineage.js 包含任务要求的全部函数"""
    root = _project_root()
    js_path = os.path.join(root, "frontend", "scripts", "pages", "lineage.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()
    required = [
        "renderLineagePage",
        "renderForceGraph",
        "renderNodeList",
        "renderNodeDetail",
        "renderToolbar",
    ]
    for fn in required:
        assert fn in content, f"缺少必需函数: {fn}"


def test_lineage_js_has_d3_features():
    """验证 lineage.js 包含 D3 力导向图谱的关键特性"""
    root = _project_root()
    js_path = os.path.join(root, "frontend", "scripts", "pages", "lineage.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()
    # 力导向布局核心 API（方法名可能跨行，故去除空白后匹配）
    compact = "".join(content.split())
    assert "forceSimulation" in compact, "缺少 d3.forceSimulation"
    assert "forceLink" in compact, "缺少 d3.forceLink"
    assert "forceManyBody" in compact, "缺少 d3.forceManyBody"
    assert "forceCenter" in compact, "缺少 d3.forceCenter"
    # 拖拽
    assert "d3.drag" in compact, "缺少 d3.drag 拖拽支持"
    assert "dragstarted" in content, "缺少 dragstarted 回调"
    assert "dragged" in content, "缺少 dragged 回调"
    assert "dragended" in content, "缺少 dragended 回调"
    # 缩放
    assert "d3.zoom" in compact, "缺少 d3.zoom 缩放支持"


def test_lineage_js_has_type_colors():
    """验证 lineage.js 使用了任务要求的类型配色"""
    root = _project_root()
    js_path = os.path.join(root, "frontend", "scripts", "pages", "lineage.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()
    # 论题=blue, 方法=green, 文献=orange, 导师=purple
    assert "#3B82F6" in content, "缺少论题蓝色 #3B82F6"
    assert "#10B981" in content, "缺少方法绿色 #10B981"
    assert "#F59E0B" in content, "缺少文献橙色 #F59E0B"
    assert "#8B5CF6" in content, "缺少导师紫色 #8B5CF6"


def test_lineage_js_keeps_api_calls():
    """验证 lineage.js 保留了原有 API 调用"""
    root = _project_root()
    js_path = os.path.join(root, "frontend", "scripts", "pages", "lineage.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "API.getLineage" in content, "缺少 API.getLineage 调用"
    assert "API.getLineageGraph" in content, "缺少 API.getLineageGraph 调用"
    assert "API.searchLineage" in content, "缺少 API.searchLineage 调用"
    assert "API.batchDeleteLineage" in content, "缺少 API.batchDeleteLineage 调用"
    assert "API.deleteLineageNode" in content, "缺少 API.deleteLineageNode 调用"
    assert "API.importLineage" in content, "缺少 API.importLineage 调用"


def test_lineage_js_has_toolbar_features():
    """验证 lineage.js 包含工具栏功能（过滤/重置/全屏）"""
    root = _project_root()
    js_path = os.path.join(root, "frontend", "scripts", "pages", "lineage.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "activeFilters" in content, "缺少类型过滤状态"
    assert "resetLayout" in content, "缺少重置布局功能"
    assert "toggleFullscreen" in content, "缺少全屏切换功能"


def test_lineage_js_has_pagination():
    """验证 lineage.js 保留了分页与批量删除功能"""
    root = _project_root()
    js_path = os.path.join(root, "frontend", "scripts", "pages", "lineage.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "PAGE_SIZE" in content, "缺少分页大小常量"
    assert "currentPage" in content, "缺少当前页状态"
    assert "confirmBatchDelete" in content, "缺少批量删除确认"
    assert "paginationToolbar" in content, "缺少分页工具栏"


def test_lineage_css_has_styles():
    """验证 main.css 包含 lineage 前缀样式"""
    root = _project_root()
    css_path = os.path.join(root, "frontend", "styles", "main.css")
    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert ".lineage-toolbar" in content, "缺少 .lineage-toolbar 样式"
    assert ".lineage-graph-wrap" in content, "缺少 .lineage-graph-wrap 样式"
    assert ".lineage-detail" in content, "缺少 .lineage-detail 样式"
    assert ".lineage-legend" in content, "缺少 .lineage-legend 样式"
    assert ".lineage-filter" in content, "缺少 .lineage-filter 样式"
