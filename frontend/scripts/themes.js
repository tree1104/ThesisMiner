/* ==========================================================================
   ThesisMiner v9.0 - 多主题切换系统
   提供 6 套预设主题，通过 <html data-theme="..."> 切换 CSS 变量。
   依赖：app.js 的 refreshIcons()（在 DOM 就绪后可用）。
   ========================================================================== */

const Themes = {
  /* 主题清单：id 对应 main.css 中的 [data-theme="..."] 选择器 */
  themes: [
    { id: 'editorial', name: 'Editorial Academic', desc: '编辑学术', icon: 'book-open' },
    { id: 'ocean', name: '海洋蓝', desc: 'Ocean Blue', icon: 'waves' },
    { id: 'forest', name: '森林绿', desc: 'Forest Green', icon: 'trees' },
    { id: 'twilight', name: '暮光紫', desc: 'Twilight Purple', icon: 'sunset' },
    { id: 'minimal', name: '极简白', desc: 'Minimal White', icon: 'sun' },
    { id: 'cyberpunk', name: '赛博朋克', desc: 'Cyberpunk', icon: 'cpu' },
  ],

  STORAGE_KEY: 'thesis-theme',
  DEFAULT_THEME: 'editorial',

  /**
   * 初始化：读取 localStorage 中保存的主题并应用，渲染下拉菜单并绑定事件。
   * 应在 DOM 就绪后调用（此时 app.js 的 refreshIcons 已可用）。
   */
  init() {
    const saved = this.getCurrent();
    this.apply(saved);
    this.renderMenu();
    this.bindEvents();
  },

  /**
   * 应用指定主题
   * @param {string} themeId - 主题标识
   */
  apply(themeId) {
    if (!this.themes.some((t) => t.id === themeId)) {
      themeId = this.DEFAULT_THEME;
    }
    document.documentElement.setAttribute('data-theme', themeId);
    localStorage.setItem(this.STORAGE_KEY, themeId);
    // 浅色主题移除 dark 类，深色主题添加 dark 类（配合 Tailwind darkMode: 'class'）
    if (themeId === 'minimal') {
      document.documentElement.classList.remove('dark');
    } else {
      document.documentElement.classList.add('dark');
    }
    this.updateLabel(themeId);
  },

  /**
   * 获取当前主题（优先读取 localStorage，回退到默认主题）
   * @returns {string}
   */
  getCurrent() {
    return localStorage.getItem(this.STORAGE_KEY) || this.DEFAULT_THEME;
  },

  /**
   * 更新触发按钮上的主题名称标签
   * @param {string} themeId
   */
  updateLabel(themeId) {
    const theme = this.themes.find((t) => t.id === themeId);
    const labelEl = document.getElementById('theme-current-label');
    if (labelEl && theme) {
      labelEl.textContent = theme.name;
    }
  },

  /**
   * 渲染下拉菜单项
   */
  renderMenu() {
    const menu = document.getElementById('theme-menu');
    if (!menu) return;
    const current = this.getCurrent();
    menu.innerHTML = this.themes
      .map(
        (t) => `
      <button class="theme-switcher__item ${t.id === current ? 'theme-switcher__item--active' : ''}" data-theme-id="${t.id}" role="menuitem">
        <span class="theme-switcher__item-icon" data-lucide="${t.icon}"></span>
        <span class="theme-switcher__item-text">
          <span class="theme-switcher__item-name">${t.name}</span>
          <span class="theme-switcher__item-desc">${t.desc}</span>
        </span>
        <span class="theme-switcher__item-check" data-lucide="check"></span>
      </button>
    `,
      )
      .join('');
    // 刷新菜单内 Lucide 图标
    if (typeof refreshIcons === 'function') {
      refreshIcons(menu);
    }
  },

  /**
   * 绑定下拉菜单的交互事件
   */
  bindEvents() {
    const trigger = document.getElementById('theme-trigger');
    const menu = document.getElementById('theme-menu');
    const switcher = document.getElementById('theme-switcher');
    if (!trigger || !menu || !switcher) return;

    // 点击触发按钮切换菜单显隐
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleMenu(menu.hidden);
    });

    // 点击菜单项应用对应主题
    menu.addEventListener('click', (e) => {
      const item = e.target.closest('[data-theme-id]');
      if (!item) return;
      const themeId = item.dataset.themeId;
      this.apply(themeId);
      this.renderMenu();
      this.toggleMenu(false);
    });

    // 点击外部关闭菜单
    document.addEventListener('click', (e) => {
      if (!switcher.contains(e.target)) {
        this.toggleMenu(false);
      }
    });

    // Esc 关闭菜单
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.toggleMenu(false);
    });
  },

  /**
   * 切换菜单显隐
   * @param {boolean} open
   */
  toggleMenu(open) {
    const menu = document.getElementById('theme-menu');
    const trigger = document.getElementById('theme-trigger');
    const switcher = document.getElementById('theme-switcher');
    if (!menu || !trigger || !switcher) return;
    menu.hidden = !open;
    trigger.setAttribute('aria-expanded', String(open));
    switcher.classList.toggle('theme-switcher--open', open);
  },
};

// 暴露到全局
window.Themes = Themes;
