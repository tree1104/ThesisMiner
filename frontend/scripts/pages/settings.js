/* ==========================================================================
   ThesisMiner v6.0 - 系统设置页面
   AI 接入配置、学术约束常量展示、模型定价表与关于信息
   页面注册到 window.Pages.settings，由 app.js 路由系统动态加载
   ========================================================================== */
(function () {
  'use strict';

  // 可选模型列表
  const MODEL_OPTIONS = [
    'gpt-4o-mini',
    'gpt-4o',
    'deepseek-chat',
    'deepseek-reasoner',
    'qwen-plus',
    'qwen-max',
  ];

  // 学位中文标签
  const DEGREE_LABELS = { master: '硕士', doctor: '博士' };

  window.Pages = window.Pages || {};
  window.Pages.settings = {
    // 同步返回页面骨架
    render() {
      return `
        <header class="page-header">
          <div class="page-header__eyebrow">ThesisMiner · Settings</div>
          <h1 class="page-header__title">系统设置</h1>
          <p class="page-header__desc">配置 AI 接入、查看学术约束常量与模型定价，掌控系统运行参数。</p>
        </header>
        <div class="page-body">
          <div class="grid grid--2 mb-lg">
            <!-- AI 配置卡片 -->
            <div class="card">
              <div class="card__header">
                <div>
                  <div class="card__title">AI 配置</div>
                  <div class="card__subtitle">OpenAI 兼容接口接入</div>
                </div>
                <span class="badge badge--default" id="ai-status-badge"><span class="badge__dot"></span>检测中</span>
              </div>
              <div class="form-group">
                <label class="form-label" for="cfg-apikey">API Key<span class="required">*</span></label>
                <div class="flex gap-sm">
                  <input type="password" class="form-control" id="cfg-apikey" placeholder="sk-..." autocomplete="off" />
                  <button class="btn btn-secondary btn-icon" id="cfg-apikey-toggle" type="button" title="显示/隐藏" aria-label="显示/隐藏 API Key">
                    <i data-lucide="eye"></i>
                  </button>
                </div>
                <div class="form-hint">密钥仅存储于本地 data/config.json，不会上传。</div>
              </div>
              <div class="form-group">
                <label class="form-label" for="cfg-baseurl">Base URL<span class="required">*</span></label>
                <input type="text" class="form-control" id="cfg-baseurl" placeholder="https://api.openai.com/v1" value="https://api.openai.com/v1" />
                <div class="form-hint">OpenAI 兼容接口地址，需以 http(s):// 开头。</div>
              </div>
              <div class="form-group">
                <label class="form-label" for="cfg-model">模型<span class="required">*</span></label>
                <select class="form-control" id="cfg-model">
                  ${MODEL_OPTIONS.map((m) => `<option value="${m}">${m}</option>`).join('')}
                </select>
              </div>
              <div class="flex gap-sm">
                <button class="btn btn-primary flex-1" id="cfg-save">
                  <i data-lucide="save"></i><span>保存配置</span>
                </button>
                <button class="btn btn-secondary" id="cfg-test">
                  <i data-lucide="plug-zap"></i><span>测试连接</span>
                </button>
              </div>
            </div>

            <!-- 约束参数卡片（只读） -->
            <div class="card">
              <div class="card__header">
                <div>
                  <div class="card__title">学术约束常量</div>
                  <div class="card__subtitle">只读 · 来自后端配置</div>
                </div>
                <i data-lucide="graduation-cap" style="color:var(--accent-primary);"></i>
              </div>
              <div class="mb-md">
                <div class="text-xs text-muted mb-sm" style="letter-spacing:0.08em;text-transform:uppercase;">学术日历</div>
                <div id="cfg-calendar" class="flex flex-col gap-sm">
                  <div class="skeleton skeleton--text"></div>
                  <div class="skeleton skeleton--text"></div>
                </div>
              </div>
              <hr class="divider" />
              <div>
                <div class="text-xs text-muted mb-sm" style="letter-spacing:0.08em;text-transform:uppercase;">文献基线</div>
                <div id="cfg-baseline" class="flex flex-col gap-sm">
                  <div class="skeleton skeleton--text"></div>
                  <div class="skeleton skeleton--text"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- 文献检索配置卡片（v6.0 新增） -->
          <div class="card mb-lg">
            <div class="card__header">
              <div>
                <div class="card__title">文献检索配置</div>
                <div class="card__subtitle">真实检索 / 模拟检索切换</div>
              </div>
              <span class="badge badge--default" id="search-status-badge"><span class="badge__dot"></span>检测中</span>
            </div>
            <div class="form-group" style="margin-bottom:0;">
              <div class="flex items-center justify-between gap-md">
                <div style="flex:1;">
                  <div class="form-label">真实文献检索</div>
                  <div class="form-hint">开启后将通过 arXiv 与 Semantic Scholar API 检索真实文献，失败时自动降级为模拟检索。</div>
                </div>
                <button class="btn btn-secondary" id="cfg-real-search-toggle" type="button">
                  <i data-lucide="search"></i><span id="search-toggle-label">已关闭</span>
                </button>
              </div>
            </div>
          </div>

          <!-- 模型定价表 -->
          <div class="card mb-lg">
            <div class="card__header">
              <div>
                <div class="card__title">模型定价表</div>
                <div class="card__subtitle">每千 Token 单价（美元）</div>
              </div>
              <i data-lucide="tags" style="color:var(--accent-primary);"></i>
            </div>
            <div class="table-wrap">
              <table class="table">
                <thead>
                  <tr>
                    <th>模型</th>
                    <th>输入价格（/千 token）</th>
                    <th>输出价格（/千 token）</th>
                  </tr>
                </thead>
                <tbody id="pricing-body">
                  <tr><td colspan="3"><div class="skeleton skeleton--text"></div></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 关于卡片 -->
          <div class="card card--accent">
            <div class="card__header">
              <div>
                <div class="card__title">关于 ThesisMiner</div>
                <div class="card__subtitle">学术语境驱动的实战论题生成与开题架构</div>
              </div>
              <span class="badge badge--accent">v6.0</span>
            </div>
            <div class="card__body">
              <p>ThesisMiner 以学术谱系为根基、以问题意识为驱动，融合创意引擎与约束校验，为研究生提供从灵感激发到开题成稿的全链路支持。</p>
              <div class="flex items-center gap-md mt-md">
                <a class="btn btn-secondary btn-sm" href="/docs" target="_blank" rel="noopener">
                  <i data-lucide="book-open"></i><span>API 文档</span>
                </a>
                <a class="btn btn-ghost btn-sm" href="/docs" target="_blank" rel="noopener">
                  <i data-lucide="external-link"></i><span>Swagger /docs</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      `;
    },

    // app.js 调用入口
    async init() {
      const container = document.getElementById('app-content');
      if (container) await this.mount(container);
    },

    // 挂载：绑定事件并并行加载配置、定价与状态
    async mount(container) {
      // API Key 显示/隐藏切换
      container.querySelector('#cfg-apikey-toggle')?.addEventListener('click', () => {
        const input = document.getElementById('cfg-apikey');
        const btn = document.getElementById('cfg-apikey-toggle');
        if (!input) return;
        const isPwd = input.type === 'password';
        input.type = isPwd ? 'text' : 'password';
        if (btn) {
          btn.innerHTML = isPwd ? '<i data-lucide="eye-off"></i>' : '<i data-lucide="eye"></i>';
          refreshIcons(btn);
        }
      });
      container.querySelector('#cfg-save')?.addEventListener('click', () => this.save());
      container.querySelector('#cfg-test')?.addEventListener('click', () => this.testConnection());

      // 真实文献检索开关
      const searchToggle = container.querySelector('#cfg-real-search-toggle');
      if (searchToggle) {
        searchToggle.addEventListener('click', () => this.toggleRealSearch());
      }

      await Promise.all([
        this.loadConfig(),
        this.loadPricing(),
        this.refreshStatus(),
        this.loadSearchStatus(),
      ]);
    },

    // 加载配置并填充表单与约束常量
    async loadConfig() {
      try {
        const cfg = await API.getConfig();
        const baseUrl = document.getElementById('cfg-baseurl');
        const model = document.getElementById('cfg-model');
        const apikey = document.getElementById('cfg-apikey');
        if (baseUrl && cfg.ai_base_url) baseUrl.value = cfg.ai_base_url;
        if (model && cfg.ai_model) {
          // 若当前模型不在选项中，追加一个选项
          if (!MODEL_OPTIONS.includes(cfg.ai_model)) {
            const opt = document.createElement('option');
            opt.value = cfg.ai_model;
            opt.textContent = cfg.ai_model;
            model.appendChild(opt);
          }
          model.value = cfg.ai_model;
        }
        if (apikey) {
          apikey.placeholder = cfg.ai_api_key_configured ? '已配置（留空则不修改）' : 'sk-...';
        }
        this.renderConstraints(cfg);
      } catch (err) {
        showToast(err.message || '加载配置失败', 'error');
      }
    },

    // 渲染学术日历与文献基线（只读）
    renderConstraints(cfg) {
      const calEl = document.getElementById('cfg-calendar');
      const baseEl = document.getElementById('cfg-baseline');
      const calendar = cfg.academic_calendar || {};
      const baseline = cfg.literature_baseline || {};

      if (calEl) {
        const entries = Object.entries(calendar);
        calEl.innerHTML = entries.length === 0
          ? '<div class="text-xs text-muted">无数据</div>'
          : entries.map(([deg, info]) => {
              const label = DEGREE_LABELS[deg] || deg;
              const years = info && info.max_years != null ? `${info.max_years} 年` : '—';
              const desc = (info && info.description) || '';
              return `<div class="list-item">
                <span class="badge badge--accent">${escapeHtml(label)}</span>
                <span class="text-sm" style="color:var(--text-primary);">${escapeHtml(years)}</span>
                <span class="text-xs text-muted flex-1">${escapeHtml(desc)}</span>
              </div>`;
            }).join('');
      }

      if (baseEl) {
        const entries = Object.entries(baseline);
        baseEl.innerHTML = entries.length === 0
          ? '<div class="text-xs text-muted">无数据</div>'
          : entries.map(([deg, n]) => {
              const label = DEGREE_LABELS[deg] || deg;
              return `<div class="list-item">
                <span class="badge badge--accent">${escapeHtml(label)}</span>
                <span class="text-sm flex-1" style="color:var(--text-primary);">文献基线</span>
                <span class="text-display text-accent" style="font-size:1.1rem;font-weight:600;">${escapeHtml(String(n))} 篇</span>
              </div>`;
            }).join('');
      }
      refreshIcons();
    },

    // 加载模型定价表
    async loadPricing() {
      const body = document.getElementById('pricing-body');
      if (!body) return;
      try {
        const pricing = await API.getPricing();
        const entries = Object.entries(pricing || {});
        if (entries.length === 0) {
          body.innerHTML = `<tr><td colspan="3">
            <div class="empty-state" style="padding:var(--space-lg);">
              <div class="empty-state__icon" data-lucide="tags"></div>
              <div class="empty-state__title">暂无定价数据</div>
            </div>
          </td></tr>`;
          refreshIcons(body);
          return;
        }
        body.innerHTML = entries
          .map(([model, p]) => `<tr>
            <td class="table__cell-primary"><span class="text-mono">${escapeHtml(model)}</span></td>
            <td class="table__cell-mono">$${Number(p.input || 0).toFixed(5)}</td>
            <td class="table__cell-mono">$${Number(p.output || 0).toFixed(5)}</td>
          </tr>`)
          .join('');
      } catch (err) {
        body.innerHTML = `<tr><td colspan="3">
          <div class="empty-state text-danger" style="padding:var(--space-lg);">
            <div class="empty-state__icon" data-lucide="alert-triangle"></div>
            <div class="empty-state__title">加载失败</div>
            <p class="empty-state__desc">${escapeHtml(err.message || '未知错误')}</p>
          </div>
        </td></tr>`;
        refreshIcons(body);
        showToast(err.message || '加载定价失败', 'error');
      }
    },

    // 刷新 AI 配置状态指示（卡片徽章 + 侧边栏指示灯）
    async refreshStatus() {
      const badge = document.getElementById('ai-status-badge');
      try {
        const status = await API.getStatus();
        const configured = !!status.ai_configured;
        if (badge) {
          badge.className = `badge ${configured ? 'badge--success' : 'badge--danger'}`;
          badge.innerHTML = `<span class="badge__dot"></span>${configured ? '已配置' : '未配置'}`;
        }
        // 同步侧边栏底部指示灯
        if (typeof updateAIStatusIndicator === 'function') {
          updateAIStatusIndicator(configured);
        }
      } catch (err) {
        if (badge) {
          badge.className = 'badge badge--danger';
          badge.innerHTML = `<span class="badge__dot"></span>检测失败`;
        }
      }
    },

    // 加载真实文献检索状态（v6.0 新增）
    async loadSearchStatus() {
      const badge = document.getElementById('search-status-badge');
      try {
        const status = await API.getSearchStatus();
        const enabled = !!(status && status.real_search_enabled);
        this.renderSearchStatus(enabled, status);
      } catch (err) {
        if (badge) {
          badge.className = 'badge badge--danger';
          badge.innerHTML = `<span class="badge__dot"></span>检测失败`;
        }
        const label = document.getElementById('search-toggle-label');
        if (label) label.textContent = '检测失败';
      }
    },

    // 渲染检索状态徽章与按钮样式
    renderSearchStatus(enabled, status) {
      const badge = document.getElementById('search-status-badge');
      const toggleBtn = document.getElementById('cfg-real-search-toggle');
      const label = document.getElementById('search-toggle-label');
      const configured = !!(status && status.configured);

      if (badge) {
        if (enabled) {
          badge.className = 'badge badge--success';
          badge.innerHTML = `<span class="badge__dot"></span>${configured ? '已开启' : '已开启·未配置Key'}`;
        } else {
          badge.className = 'badge badge--default';
          badge.innerHTML = `<span class="badge__dot"></span>已关闭`;
        }
      }
      if (toggleBtn) {
        // 开启时使用 primary 高亮，关闭时使用 secondary
        toggleBtn.classList.toggle('btn-primary', enabled);
        toggleBtn.classList.toggle('btn-secondary', !enabled);
      }
      if (label) {
        label.textContent = enabled ? '已开启' : '已关闭';
      }
      if (toggleBtn) refreshIcons(toggleBtn);
    },

    // 切换真实文献检索开关
    async toggleRealSearch() {
      const toggleBtn = document.getElementById('cfg-real-search-toggle');
      const label = document.getElementById('search-toggle-label');
      // 读取当前状态：依据按钮是否含 btn-primary 判定
      const currentlyEnabled = toggleBtn ? toggleBtn.classList.contains('btn-primary') : false;
      const next = !currentlyEnabled;

      if (toggleBtn) {
        toggleBtn.disabled = true;
        const original = label ? label.textContent : '';
        if (label) label.textContent = '切换中…';
      }
      try {
        await API.updateSearchConfig(next);
        // 切换成功后重新拉取状态以同步徽章
        await this.loadSearchStatus();
        showToast(next ? '已开启真实文献检索' : '已关闭真实文献检索', 'success');
      } catch (err) {
        showToast(err.message || '切换检索模式失败', 'error');
        // 回滚 UI
        this.renderSearchStatus(currentlyEnabled, { configured: true });
      } finally {
        if (toggleBtn) toggleBtn.disabled = false;
      }
    },

    // 表单校验：返回 { baseUrl, model, apikey } 或 null
    validate() {
      const baseUrl = (document.getElementById('cfg-baseurl').value || '').trim();
      const model = (document.getElementById('cfg-model').value || '').trim();
      if (!baseUrl) {
        showToast('请填写 Base URL', 'warning');
        return null;
      }
      // URL 格式校验
      try {
        const u = new URL(baseUrl);
        if (!/^https?:$/.test(u.protocol)) {
          showToast('Base URL 必须以 http:// 或 https:// 开头', 'warning');
          return null;
        }
      } catch (_) {
        showToast('Base URL 格式不正确', 'warning');
        return null;
      }
      if (!model) {
        showToast('请选择模型', 'warning');
        return null;
      }
      const apikey = (document.getElementById('cfg-apikey').value || '').trim();
      return { baseUrl, model, apikey };
    },

    // 保存配置
    async save() {
      const validated = this.validate();
      if (!validated) return;
      const { baseUrl, model, apikey } = validated;
      const btn = document.getElementById('cfg-save');
      const original = btn ? btn.innerHTML : '';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<div class="spinner"></div><span>保存中…</span>`;
        refreshIcons(btn);
      }
      try {
        const payload = { ai_base_url: baseUrl, ai_model: model };
        // 仅当填写了 key 时才提交，避免覆盖已有密钥
        if (apikey) payload.ai_api_key = apikey;
        await API.updateConfig(payload);
        showToast('配置已保存', 'success');
        // 清空 key 输入并刷新占位提示与状态
        const apikeyInput = document.getElementById('cfg-apikey');
        if (apikeyInput) {
          apikeyInput.value = '';
          apikeyInput.placeholder = '已配置（留空则不修改）';
        }
        await this.refreshStatus();
      } catch (err) {
        showToast(err.message || '保存失败', 'error');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = original;
          refreshIcons(btn);
        }
      }
    },

    // 测试连接：检查 ai_configured
    async testConnection() {
      const btn = document.getElementById('cfg-test');
      const original = btn ? btn.innerHTML : '';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<div class="spinner"></div><span>测试中…</span>`;
        refreshIcons(btn);
      }
      try {
        const status = await API.getStatus();
        const configured = !!status.ai_configured;
        if (configured) {
          showToast('AI 服务连接正常，已就绪', 'success');
        } else {
          showToast('AI 尚未配置，请先填写并保存 API Key', 'warning');
        }
        await this.refreshStatus();
      } catch (err) {
        showToast(err.message || '测试失败', 'error');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = original;
          refreshIcons(btn);
        }
      }
    },
  };
})();
