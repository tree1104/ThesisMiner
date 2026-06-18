/* ==========================================================================
   ThesisMiner v6.0 - 应用主逻辑
   基于 hash 的 SPA 路由、全局状态、通知、抽屉与工具函数
   ========================================================================== */

/* --------------------------------------------------------------------------
   1. 全局状态
   -------------------------------------------------------------------------- */
const AppState = {
  currentPage: 'dashboard',     // 当前页面标识
  config: null,                 // 后端配置缓存
  status: null,                 // 服务状态
  proposals: [],                // 论题列表缓存
  sessions: [],                 // 会话列表缓存
  aiConfigured: false,          // AI 是否已配置
  isLoading: false,             // 全局加载态
};

/* --------------------------------------------------------------------------
   2. 页面注册表
   每个页面需提供 render() 返回 HTML 字符串，以及可选的 init() 钩子。
   页面脚本会在 app.js 之后加载，并向 Pages 注册自身。
   -------------------------------------------------------------------------- */
const Pages = {
  dashboard: null,
  generate: null,
  lineage: null,
  sessions: null,
  budgets: null,
  settings: null,
};

/* --------------------------------------------------------------------------
   3. 导航配置
   -------------------------------------------------------------------------- */
const NAV_ITEMS = [
  { key: 'dashboard', label: '仪表盘', icon: 'layout-dashboard', hash: '#dashboard' },
  { key: 'generate', label: '论题生成', icon: 'sparkles', hash: '#generate' },
  { key: 'lineage', label: '谱系管理', icon: 'git-fork', hash: '#lineage' },
  { key: 'sessions', label: '会话历史', icon: 'history', hash: '#sessions' },
  { key: 'budgets', label: '预算看板', icon: 'wallet', hash: '#budgets' },
  { key: 'settings', label: '设置', icon: 'settings', hash: '#settings' },
];

/* --------------------------------------------------------------------------
   4. 路由系统
   -------------------------------------------------------------------------- */

/**
 * 解析当前 hash，返回页面标识
 * @returns {string}
 */
function parseHash() {
  const hash = window.location.hash.replace(/^#/, '').trim();
  if (!hash) return 'dashboard';
  return NAV_ITEMS.some((item) => item.key === hash) ? hash : 'dashboard';
}

/**
 * 导航到指定页面
 * @param {string} page - 页面标识
 */
function navigate(page) {
  if (!NAV_ITEMS.some((item) => item.key === page)) {
    page = 'dashboard';
  }
  // 同步地址栏，触发 hashchange -> renderPage
  if (window.location.hash !== `#${page}`) {
    window.location.hash = page;
  } else {
    // hash 未变化时手动渲染一次
    renderPage(page);
  }
}

/**
 * 渲染指定页面
 * @param {string} page - 页面标识
 */
async function renderPage(page) {
  AppState.currentPage = page;

  // 更新侧边栏高亮
  updateNavActive(page);

  const contentEl = document.getElementById('app-content');
  if (!contentEl) return;

  // 滚动复位
  contentEl.scrollTop = 0;
  window.scrollTo(0, 0);

  const pageModule = Pages[page];

  // 页面未注册（脚本尚未加载或不存在）
  if (!pageModule || typeof pageModule.render !== 'function') {
    contentEl.innerHTML = renderPlaceholderPage(page);
    // 尝试动态加载页面脚本
    loadPageScript(page);
    return;
  }

  try {
    // 渲染骨架，避免白屏
    contentEl.innerHTML = `<div class="fade-in">${pageModule.render()}</div>`;
    // 执行页面初始化钩子（数据加载、事件绑定）
    if (typeof pageModule.init === 'function') {
      await pageModule.init();
    }
    // 重新初始化页面内 Lucide 图标
    refreshIcons();
  } catch (err) {
    console.error(`[App] 页面渲染失败: ${page}`, err);
    contentEl.innerHTML = renderErrorPage(err);
    refreshIcons();
  }
}

/**
 * 动态加载页面脚本
 * @param {string} page
 */
function loadPageScript(page) {
  const src = `scripts/pages/${page}.js`;
  // 避免重复加载
  if (document.querySelector(`script[data-page="${page}"]`)) return;
  const script = document.createElement('script');
  script.src = src;
  script.dataset.page = page;
  script.onerror = () => {
    const contentEl = document.getElementById('app-content');
    if (contentEl) {
      contentEl.innerHTML = renderPlaceholderPage(page, true);
      refreshIcons();
    }
  };
  script.onload = () => {
    // 脚本加载完成后若已注册则重新渲染
    if (Pages[page] && typeof Pages[page].render === 'function') {
      renderPage(page);
    }
  };
  document.body.appendChild(script);
}

/**
 * 更新侧边栏导航高亮
 * @param {string} page
 */
function updateNavActive(page) {
  document.querySelectorAll('.nav-item').forEach((el) => {
    el.classList.toggle('active', el.dataset.page === page);
  });
}

/* --------------------------------------------------------------------------
   5. 占位与错误页面
   -------------------------------------------------------------------------- */

function renderPlaceholderPage(page, loadFailed = false) {
  const labels = {
    dashboard: '仪表盘',
    generate: '论题生成',
    lineage: '谱系管理',
    sessions: '会话历史',
    budgets: '预算看板',
    settings: '设置',
  };
  const label = labels[page] || page;
  const desc = loadFailed
    ? `页面脚本 <code class="text-mono text-accent">scripts/pages/${page}.js</code> 加载失败，请确认文件已创建。`
    : `该页面模块尚未实现，等待 <code class="text-mono text-accent">scripts/pages/${page}.js</code> 注册。`;
  return `
    <header class="page-header">
      <div class="page-header__eyebrow">ThesisMiner · ${label}</div>
      <h1 class="page-header__title">${label}</h1>
      <p class="page-header__desc">学术论题生成系统的${label}模块。</p>
    </header>
    <div class="page-body">
      <div class="empty-state">
        <div class="empty-state__icon" data-lucide="construction"></div>
        <div class="empty-state__title">模块建设中</div>
        <p class="empty-state__desc">${desc}</p>
      </div>
    </div>
  `;
}

function renderErrorPage(err) {
  return `
    <header class="page-header">
      <div class="page-header__eyebrow">Error</div>
      <h1 class="page-header__title">页面渲染异常</h1>
    </header>
    <div class="page-body">
      <div class="card card--accent">
        <div class="card__body">
          <p class="text-danger font-medium mb-sm">渲染过程中发生错误：</p>
          <pre class="code-block">${escapeHtml(err.message || String(err))}</pre>
        </div>
      </div>
    </div>
  `;
}

/* --------------------------------------------------------------------------
   6. 通知 Toast
   -------------------------------------------------------------------------- */

const TOAST_ICONS = {
  success: 'check-circle-2',
  error: 'alert-circle',
  warning: 'alert-triangle',
  info: 'info',
};

const TOAST_TITLES = {
  success: '成功',
  error: '错误',
  warning: '提示',
  info: '信息',
};

/**
 * 显示通知
 * @param {string} message - 消息内容
 * @param {'success'|'error'|'warning'|'info'} [type='info']
 * @param {object} [opts] - { title?: string, duration?: number }
 */
function showToast(message, type = 'info', opts = {}) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const title = opts.title || TOAST_TITLES[type] || '信息';
  const duration = typeof opts.duration === 'number' ? opts.duration : 4000;
  const iconName = TOAST_ICONS[type] || TOAST_ICONS.info;

  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.innerHTML = `
    <div class="toast__icon" data-lucide="${iconName}"></div>
    <div class="toast__content">
      <div class="toast__title">${escapeHtml(title)}</div>
      <div class="toast__message">${escapeHtml(message)}</div>
    </div>
    <button class="toast__close" aria-label="关闭">
      <i data-lucide="x" style="width:14px;height:14px;"></i>
    </button>
  `;

  const remove = () => {
    toast.classList.add('toast-leaving');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  };

  toast.querySelector('.toast__close').addEventListener('click', remove);
  container.appendChild(toast);
  refreshIcons(toast);

  if (duration > 0) {
    setTimeout(remove, duration);
  }
}

/* --------------------------------------------------------------------------
   7. 抽屉 Drawer
   -------------------------------------------------------------------------- */

/**
 * 显示右侧抽屉
 * @param {object} opts - { title?: string, bodyHtml?: string, footerHtml?: string, onMount?: (el)=>void }
 */
function showDrawer(opts = {}) {
  closeDrawer(true);

  const container = document.getElementById('drawer-container');
  if (!container) return;

  const overlay = document.createElement('div');
  overlay.className = 'drawer-overlay';

  const drawer = document.createElement('div');
  drawer.className = 'drawer';
  drawer.innerHTML = `
    <div class="drawer__header">
      <h3 class="drawer__title">${escapeHtml(opts.title || '详情')}</h3>
      <button class="drawer__close" aria-label="关闭" data-drawer-close>
        <i data-lucide="x"></i>
      </button>
    </div>
    <div class="drawer__body">${opts.bodyHtml || ''}</div>
    ${opts.footerHtml ? `<div class="drawer__footer">${opts.footerHtml}</div>` : ''}
  `;

  overlay.appendChild(drawer);
  container.appendChild(overlay);

  const dismiss = () => closeDrawer();
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) dismiss();
  });
  drawer.querySelector('[data-drawer-close]').addEventListener('click', dismiss);
  document.addEventListener('keydown', function onEsc(e) {
    if (e.key === 'Escape') {
      dismiss();
      document.removeEventListener('keydown', onEsc);
    }
  });

  refreshIcons(drawer);

  if (typeof opts.onMount === 'function') {
    opts.onMount(drawer);
  }

  return { drawer, overlay, close: dismiss };
}

/**
 * 关闭抽屉
 * @param {boolean} [immediate] - 内部调用，跳过动画
 */
function closeDrawer(immediate = false) {
  const container = document.getElementById('drawer-container');
  if (!container) return;
  if (immediate) {
    container.innerHTML = '';
    return;
  }
  const overlay = container.querySelector('.drawer-overlay');
  if (!overlay) return;
  overlay.style.animation = 'fadeIn 200ms reverse forwards';
  const drawer = overlay.querySelector('.drawer');
  if (drawer) drawer.style.animation = 'drawerSlideIn 200ms reverse forwards';
  setTimeout(() => {
    container.innerHTML = '';
  }, 200);
}

/* --------------------------------------------------------------------------
   8. 工具函数
   -------------------------------------------------------------------------- */

/**
 * 格式化日期
 * @param {string|number|Date} dateStr
 * @param {boolean} [withTime=true]
 * @returns {string}
 */
function formatDate(dateStr, withTime = true) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return String(dateStr);
  const pad = (n) => String(n).padStart(2, '0');
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  if (!withTime) return date;
  return `${date} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * 格式化费用（保留 4 位小数 + $ 符号）
 * @param {number} cost
 * @returns {string}
 */
function formatCost(cost) {
  if (cost === null || cost === undefined || cost === '') return '$0.0000';
  const num = Number(cost);
  if (Number.isNaN(num)) return String(cost);
  return `$${num.toFixed(4)}`;
}

/**
 * 截断文本
 * @param {string} text
 * @param {number} length
 * @returns {string}
 */
function truncate(text, length = 60) {
  if (!text) return '';
  const str = String(text);
  if (str.length <= length) return str;
  return str.slice(0, length).trimEnd() + '…';
}

/**
 * HTML 转义，防止 XSS
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * 刷新 Lucide 图标渲染
 * 说明：lucide.createIcons() 会扫描文档中所有 [data-lucide] 元素并替换为 <svg>，
 * 已替换的元素不再保留该属性，因此重复调用是安全的，仅渲染新增节点。
 * @param {HTMLElement} [scope] - 保留参数以兼容调用方，实际仍全局扫描
 */
function refreshIcons(scope = document) {
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons({
      attrs: { width: 16, height: 16, 'stroke-width': 1.75 },
    });
  }
}

/**
 * 防抖
 * @param {Function} fn
 * @param {number} delay
 * @returns {Function}
 */
function debounce(fn, delay = 300) {
  let timer = null;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * 复制文本到剪贴板
 * @param {string} text
 * @returns {Promise<boolean>}
 */
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (_) {
    return false;
  }
}

/* --------------------------------------------------------------------------
   9. AI 配置状态检查
   -------------------------------------------------------------------------- */

async function checkAIStatus() {
  try {
    const status = await API.getStatus();
    AppState.status = status;
    AppState.aiConfigured = !!status.ai_configured;
    updateAIStatusIndicator(AppState.aiConfigured);
    return AppState.aiConfigured;
  } catch (err) {
    console.warn('[App] 状态检查失败', err);
    AppState.aiConfigured = false;
    updateAIStatusIndicator(false);
    return false;
  }
}

/**
 * 更新侧边栏底部 AI 状态指示灯
 * @param {boolean} configured
 */
function updateAIStatusIndicator(configured) {
  const dot = document.querySelector('.ai-status__dot');
  const text = document.querySelector('.ai-status__text');
  if (!dot) return;
  dot.classList.toggle('configured', configured);
  dot.classList.toggle('unconfigured', !configured);
  if (text) {
    text.textContent = configured ? 'AI 已就绪' : 'AI 未配置';
  }
}

/* --------------------------------------------------------------------------
   10. 侧边栏渲染
   -------------------------------------------------------------------------- */

function renderSidebar() {
  const navEl = document.querySelector('.sidebar__nav');
  if (!navEl) return;
  const items = NAV_ITEMS.map((item) => `
    <div class="nav-item" data-page="${item.key}" data-hash="${item.hash}">
      <span class="nav-item__icon" data-lucide="${item.icon}"></span>
      <span class="nav-item__text">${item.label}</span>
    </div>
  `).join('');
  navEl.innerHTML = `
    <div class="sidebar__nav-label">导航</div>
    ${items}
  `;
  // 绑定点击
  navEl.querySelectorAll('.nav-item').forEach((el) => {
    el.addEventListener('click', () => navigate(el.dataset.page));
  });
  refreshIcons(navEl);
}

/* --------------------------------------------------------------------------
   11. 初始化
   -------------------------------------------------------------------------- */

async function initApp() {
  // 渲染侧边栏导航
  renderSidebar();

  // 监听 hash 变化
  window.addEventListener('hashchange', () => {
    renderPage(parseHash());
  });

  // 渲染初始页面
  const initialPage = parseHash();
  updateNavActive(initialPage);
  renderPage(initialPage);

  // 检查 AI 配置状态
  await checkAIStatus();

  // 加载配置缓存
  try {
    AppState.config = await API.getConfig();
  } catch (err) {
    console.warn('[App] 配置加载失败', err);
  }
}

// DOM 就绪后启动
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

/* --------------------------------------------------------------------------
   12. 暴露全局 API
   -------------------------------------------------------------------------- */
window.AppState = AppState;
window.Pages = Pages;
window.NAV_ITEMS = NAV_ITEMS;
window.navigate = navigate;
window.renderPage = renderPage;
window.showToast = showToast;
window.showDrawer = showDrawer;
window.closeDrawer = closeDrawer;
window.formatDate = formatDate;
window.formatCost = formatCost;
window.truncate = truncate;
window.escapeHtml = escapeHtml;
window.refreshIcons = refreshIcons;
window.debounce = debounce;
window.copyToClipboard = copyToClipboard;
window.checkAIStatus = checkAIStatus;
