"""E2E 测试：五阶段流程 UI（Task 13）验证"""
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


def test_generate_js_parses():
    """验证 generate.js 语法正确"""
    root = _project_root()
    result = subprocess.run(
        ["node", "--check", "frontend/scripts/pages/generate.js"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    assert result.returncode == 0, f"generate.js 语法错误: {result.stderr}"


def test_generate_js_has_five_stages():
    """验证 generate.js 包含五阶段定义"""
    content = _read_js("generate.js")
    assert "info_confirm" in content, "缺少信息确权阶段"
    assert "creativity" in content, "缺少创意阶段"
    assert "validation" in content, "缺少校验阶段"
    assert "generation" in content, "缺少生成阶段"
    assert "deep_assist" in content, "缺少深度辅助阶段"
    # STAGES 数组定义
    assert "STAGES" in content, "缺少 STAGES 常量"


def test_generate_js_has_stage_progress_bar():
    """验证 generate.js 包含顶部五阶段进度条"""
    content = _read_js("generate.js")
    assert "renderStageProgress" in content, "缺少进度条渲染方法"
    assert "stage-step" in content, "缺少阶段步骤元素"
    assert "stage-progress" in content, "缺少进度条容器"
    # 当前阶段高亮
    assert "active" in content, "缺少激活态样式"
    # 阶段配色变量
    assert "--stage-current" in content, "缺少阶段配色 CSS 变量"


def test_generate_js_has_stage_panels():
    """验证 generate.js 包含五阶段独立面板渲染"""
    content = _read_js("generate.js")
    assert "renderStagePanels" in content, "缺少阶段面板渲染方法"
    assert "stage-panel" in content, "缺少阶段面板元素"
    # 各阶段独立渲染方法
    assert "render_info_confirm" in content, "缺少信息确权阶段渲染方法"
    assert "render_creativity" in content, "缺少创意阶段渲染方法"
    assert "render_validation" in content, "缺少校验阶段渲染方法"
    assert "render_generation" in content, "缺少生成阶段渲染方法"
    assert "render_deep_assist" in content, "缺少深度辅助阶段渲染方法"


def test_generate_js_has_info_confirm_stage():
    """验证信息确权阶段：文献摘要 + 确认按钮"""
    content = _read_js("generate.js")
    assert "extractLiterature" in content, "缺少文献提取方法"
    assert "info-confirm" in content, "缺少信息确权样式类"
    # 确认进入创意阶段按钮
    assert "confirmStage" in content, "缺少阶段确认方法"
    assert "creativity" in content, "缺少进入创意阶段目标"


def test_generate_js_has_creativity_stage():
    """验证创意阶段：候选论题卡片 + 选中按钮"""
    content = _read_js("generate.js")
    assert "creativity-card" in content, "缺少候选论题卡片"
    assert "creativity-grid" in content, "缺少候选论题网格"
    assert "selectProposal" in content, "缺少选中论题方法"
    assert "data-select-proposal" in content, "缺少选中论题按钮属性"
    # 选中进入校验
    assert "validation" in content, "缺少进入校验阶段目标"


def test_generate_js_has_validation_stage():
    """验证校验阶段：评分/问题/建议 + 回退按钮"""
    content = _read_js("generate.js")
    assert "validation-score" in content, "缺少评分组件"
    assert "validation-issues" in content, "缺少问题列表"
    assert "validation-issue" in content, "缺少问题项"
    # 评分 < 60 回退按钮
    assert "rollback-creativity" in content, "缺少回退重新生成按钮"
    assert "goToStage" in content, "缺少阶段跳转方法"
    # 评分计算
    assert "computeValidationScore" in content, "缺少评分计算方法"
    # 评分 >= 60 进入生成
    assert "proceed-generation" in content, "缺少进入生成阶段按钮"


def test_generate_js_has_generation_stage():
    """验证生成阶段：多粒度选择器 + style_normalizer 对比"""
    content = _read_js("generate.js")
    # 多粒度选择器
    assert "GRANULARITIES" in content, "缺少 GRANULARITIES 常量"
    assert "granularity-selector" in content, "缺少粒度选择器"
    assert "granularity-option" in content, "缺少粒度选项"
    for g in ["title", "abstract", "outline", "full"]:
        assert g in content, f"缺少粒度类型: {g}"
    # style_normalizer 改写前后对比
    assert "style-compare" in content, "缺少 style_normalizer 对比组件"
    assert "style-compare__panel--before" in content, "缺少改写前面板"
    assert "style-compare__panel--after" in content, "缺少改写后面板"
    assert "styleBefore" in content, "缺少改写前状态"
    assert "styleAfter" in content, "缺少改写后状态"


def test_generate_js_has_deep_assist_stage():
    """验证深度辅助阶段：三件套入口"""
    content = _read_js("generate.js")
    assert "DEEP_ASSISTS" in content, "缺少 DEEP_ASSISTS 常量"
    assert "deep-assist-grid" in content, "缺少深度辅助网格"
    assert "deep-assist-card" in content, "缺少深度辅助卡片"
    assert "enterDeepAssist" in content, "缺少进入深度辅助方法"
    # 三件套
    assert "literature" in content, "缺少文献精读选项"
    assert "experiment" in content, "缺少实验预研选项"
    assert "defense" in content, "缺少答辩模拟选项"


def test_generate_js_has_stage_gates():
    """验证 generate.js 包含阶段门禁逻辑"""
    content = _read_js("generate.js")
    # 阶段确认状态
    assert "stageConfirmed" in content, "缺少阶段确认状态"
    # 当前阶段
    assert "currentStage" in content, "缺少当前阶段状态"


def test_generate_js_registers_page():
    """验证 generate.js 注册到 Pages 注册表"""
    content = _read_js("generate.js")
    assert "window.Pages" in content, "未注册到 window.Pages"
    assert "generate" in content, "缺少 generate 页面键"


def test_generate_css_has_styles():
    """验证 main.css 包含阶段流程样式"""
    root = _project_root()
    css_path = os.path.join(root, "frontend", "styles", "main.css")
    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert ".stage-step" in content, "缺少 .stage-step 样式"
    assert ".stage-panel" in content, "缺少 .stage-panel 样式"
    assert ".info-confirm" in content, "缺少 .info-confirm 样式"
    assert ".creativity-card" in content, "缺少 .creativity-card 样式"
    assert ".validation-score" in content, "缺少 .validation-score 样式"
    assert ".granularity-option" in content, "缺少 .granularity-option 样式"
    assert ".style-compare" in content, "缺少 .style-compare 样式"
    assert ".deep-assist-card" in content, "缺少 .deep-assist-card 样式"


def test_generate_css_has_stage_tokens():
    """验证 main.css 包含阶段配色 CSS 变量"""
    root = _project_root()
    css_path = os.path.join(root, "frontend", "styles", "main.css")
    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "--stage-info_confirm" in content, "缺少 --stage-info_confirm 变量"
    assert "--stage-creativity" in content, "缺少 --stage-creativity 变量"
    assert "--stage-validation" in content, "缺少 --stage-validation 变量"
    assert "--stage-generation" in content, "缺少 --stage-generation 变量"
    assert "--stage-deep_assist" in content, "缺少 --stage-deep_assist 变量"
