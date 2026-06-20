/* ==========================================================================
   ThesisMiner v7.0 - 预算看板页面
   汇总调用成本、估算会话预算、展示账本明细与按模型分组统计
   顶部 5 项汇总卡片（总调用 / 输入缓存命中 / 输入未命中 / 输出 / 总费用）
   账本明细与按模型分组均展示三类 token 用量，费用按配置货币显示前缀
   页面注册到 window.Pages.budgets，由 app.js 路由系统动态加载
   ========================================================================== */
(function () {
  'use strict';

  // 账本明细表格骨架行（9 列）
  function skeletonRows(n) {
    let rows = '';
    for (let i = 0; i < (n || 6); i++) {
      rows += `<tr>
        <td><div class="skeleton skeleton--text"></div></td>
        <td><div class="skeleton skeleton--text"></div></td>
        <td><div class="skeleton skeleton--text"></div></td>
        <td><div class="skeleton skeleton--text"></div></td>
        <td><div class="skeleton skeleton--text"></div></td>
        <td><div class="skeleton skeleton--text"></div></td>
        <td><div class="skeleton skeleton--text"></div></td>
        <td><div class="skeleton skeleton--text"></div></td>
        <td><div class="skeleton skeleton--text"></div></td>
      </tr>`;
    }
    return rows;
  }

  // 货币感知费用格式化（覆盖全局 formatCost，按配置显示 ¥ / $ 前缀，保留 4 位小数）
  function formatCost(cost, currency) {
    const prefix = currency === 'USD' ? '$' : '¥';
    if (cost === null || cost === undefined || cost === '') return `${prefix}0.0000`;
    const num = Number(cost);
    if (Number.isNaN(num)) return String(cost);
    return `${prefix}${num.toFixed(4)}`;
  }

  window.Pages = window.Pages || {};
  window.Pages.budgets = {
    // 缓存货币类型，页面加载时拉取一次后复用（默认 CNY）
    currency: 'CNY',
    _currencyLoaded: false,

    // 同步返回页面骨架
    render() {
      return `
        <header class="page-header">
          <div class="page-header__eyebrow">ThesisMiner · Budgets</div>
          <h1 class="page-header__title">预算看板</h1>
          <p class="page-header__desc">透明记录每一次 AI 调用的 token 用量与费用，估算会话成本，掌控学术投入。</p>
        </header>
        <div class="page-body">
          <!-- 顶部汇总卡片（5 项：3 + 2 布局） -->
          <div class="grid grid--3 mb-lg">
            <div class="stat-card">
              <div class="stat-card__icon" data-lucide="hash"></div>
              <div class="stat-card__label">总调用次数</div>
              <div class="stat-card__value" id="sum-calls">—</div>
            </div>
            <div class="stat-card">
              <div class="stat-card__icon" data-lucide="arrow-down-to-line"></div>
              <div class="stat-card__label">输入(缓存命中)</div>
              <div class="stat-card__value stat-card__value-mono" id="sum-input-cached">—</div>
            </div>
            <div class="stat-card">
              <div class="stat-card__icon" data-lucide="arrow-down-circle"></div>
              <div class="stat-card__label">输入(未命中)</div>
              <div class="stat-card__value stat-card__value-mono" id="sum-input-uncached">—</div>
            </div>
          </div>
          <div class="grid grid--2 mb-lg">
            <div class="stat-card">
              <div class="stat-card__icon" data-lucide="arrow-up-from-line"></div>
              <div class="stat-card__label">输出 Token</div>
              <div class="stat-card__value stat-card__value-mono" id="sum-output">—</div>
            </div>
            <div class="stat-card">
              <div class="stat-card__icon" data-lucide="dollar-sign"></div>
              <div class="stat-card__label">总费用</div>
              <div class="stat-card__value stat-card__value-mono text-accent" id="sum-cost">—</div>
            </div>
          </div>

          <div class="grid grid--2 mb-lg">
            <!-- 预算估算工具 -->
            <div class="card">
              <div class="card__header">
                <div>
                  <div class="card__title">预算估算</div>
                  <div class="card__subtitle">按学位与模式预估会话成本</div>
                </div>
                <i data-lucide="calculator" style="color:var(--accent-primary);"></i>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label" for="est-degree">学位<span class="required">*</span></label>
                  <select class="form-control" id="est-degree">
                    <option value="master">硕士</option>
                    <option value="doctor">博士</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label" for="est-mode">模式<span class="required">*</span></label>
                  <select class="form-control" id="est-mode">
                    <option value="quick">快速 (quick)</option>
                    <option value="deep">深度 (deep)</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label" for="est-count">生成数量<span class="required">*</span></label>
                  <input type="number" class="form-control" id="est-count" value="3" min="1" max="20" />
                </div>
              </div>
              <button class="btn btn-primary btn-block" id="est-btn">
                <i data-lucide="sparkles"></i><span>开始估算</span>
              </button>
              <div id="est-result" class="mt-md"></div>
            </div>

            <!-- 按模型分组统计（含三类 token 用量） -->
            <div class="card">
              <div class="card__header">
                <div>
                  <div class="card__title">按模型分组</div>
                  <div class="card__subtitle">调用次数与三类 token 用量</div>
                </div>
                <i data-lucide="bar-chart-3" style="color:var(--accent-primary);"></i>
              </div>
              <div class="table-wrap">
                <table class="table">
                  <thead>
                    <tr>
                      <th>模型</th>
                      <th>调用次数</th>
                      <th>输入(缓存)</th>
                      <th>输入(未命中)</th>
                      <th>输出</th>
                      <th>总Token</th>
                      <th>费用</th>
                    </tr>
                  </thead>
                  <tbody id="by-model-tbody">
                    <tr><td colspan="7" class="text-center text-muted py-md">加载中…</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- 账本明细表格 -->
          <div class="card">
            <div class="card__header">
              <div>
                <div class="card__title">账本明细</div>
                <div class="card__subtitle">最近 50 条调用记录</div>
              </div>
              <button class="btn btn-secondary btn-sm" id="ledger-refresh">
                <i data-lucide="refresh-cw"></i><span>刷新</span>
              </button>
            </div>
            <div class="table-wrap">
              <table class="table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>会话</th>
                    <th>模型</th>
                    <th>用途</th>
                    <th>输入</th>
                    <th>缓存命中</th>
                    <th>输出</th>
                    <th>总计</th>
                    <th>费用</th>
                  </tr>
                </thead>
                <tbody id="ledger-body">
                  ${skeletonRows()}
                </tbody>
              </table>
            </div>
            <div id="ledger-empty" class="hidden"></div>
          </div>
        </div>
      `;
    },

    // app.js 调用入口
    async init() {
      const container = document.getElementById('app-content');
      if (container) await this.mount(container);
    },

    // 挂载：绑定事件并并行加载数据
    async mount(container) {
      container.querySelector('#est-btn')?.addEventListener('click', () => this.estimate());
      container.querySelector('#ledger-refresh')?.addEventListener('click', () => this.loadLedger());
      await Promise.all([this.getCurrency(), this.loadSummary(), this.loadLedger()]);
    },

    // 获取并缓存货币类型（页面加载时拉取一次，后续调用直接返回缓存值）
    async getCurrency() {
      if (this._currencyLoaded) return this.currency;
      try {
        const config = await API.getConfig();
        this.currency = config.currency || 'CNY';
      } catch {
        this.currency = 'CNY';
      }
      this._currencyLoaded = true;
      return this.currency;
    },

    // 加载汇总统计（填充 5 张顶部卡片 + 按模型分组表）
    async loadSummary() {
      const ids = ['sum-calls', 'sum-input-cached', 'sum-input-uncached', 'sum-output', 'sum-cost'];
      try {
        const data = await API.getBudgetSummary();
        // 货币已缓存时立即返回，否则拉取一次
        const currency = await this.getCurrency();
        document.getElementById('sum-calls').textContent = String(data.total_calls || 0);
        document.getElementById('sum-input-cached').textContent = (data.input_cached || 0).toLocaleString();
        document.getElementById('sum-input-uncached').textContent = (data.input_uncached || 0).toLocaleString();
        document.getElementById('sum-output').textContent = (data.output || 0).toLocaleString();
        document.getElementById('sum-cost').textContent = formatCost(data.total_cost || 0, currency);
        // 渲染按模型分组统计（含三类 token）
        this.renderByModel(data.by_model || {});
      } catch (err) {
        ids.forEach((id) => {
          const el = document.getElementById(id);
          if (el) el.textContent = '—';
        });
        const tbody = document.getElementById('by-model-tbody');
        if (tbody) {
          tbody.innerHTML = `<tr><td colspan="7">${this.errorState(err)}</td></tr>`;
          refreshIcons(tbody);
        }
        showToast(err.message || '加载汇总失败', 'error');
      }
    },

    // 渲染按模型分组统计表格（含三类 token：缓存命中 / 未命中 / 输出）
    renderByModel(byModel) {
      const tbody = document.getElementById('by-model-tbody');
      if (!tbody) return;
      const entries = Object.entries(byModel || {});
      if (entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-md">暂无数据</td></tr>';
        return;
      }
      tbody.innerHTML = entries
        .map(([model, stats]) => `
          <tr>
            <td class="text-xs">${escapeHtml(model)}</td>
            <td class="text-xs text-mono">${stats.calls || 0}</td>
            <td class="text-xs text-mono text-accent">${(stats.input_cached || 0).toLocaleString()}</td>
            <td class="text-xs text-mono">${(stats.input_uncached || 0).toLocaleString()}</td>
            <td class="text-xs text-mono">${(stats.output || 0).toLocaleString()}</td>
            <td class="text-xs text-mono font-medium">${(stats.tokens || 0).toLocaleString()}</td>
            <td class="text-xs text-mono text-accent">${formatCost(stats.cost || 0, this.currency)}</td>
          </tr>`)
        .join('');
    },

    // 加载账本明细
    async loadLedger() {
      const body = document.getElementById('ledger-body');
      const emptyEl = document.getElementById('ledger-empty');
      if (!body) return;
      body.innerHTML = skeletonRows();
      try {
        // 确保货币已加载（已缓存时无额外请求）
        const currency = await this.getCurrency();
        const data = await API.getLedger(null, 50, 0);
        const entries = (data && data.entries) || [];
        if (entries.length === 0) {
          body.innerHTML = '';
          if (emptyEl) {
            emptyEl.classList.remove('hidden');
            emptyEl.innerHTML = `
              <div class="empty-state">
                <div class="empty-state__icon" data-lucide="receipt"></div>
                <div class="empty-state__title">暂无消耗记录</div>
                <p class="empty-state__desc">生成论题后，每次 AI 调用的明细将在此呈现。</p>
              </div>`;
            refreshIcons(emptyEl);
          }
          return;
        }
        if (emptyEl) emptyEl.classList.add('hidden');
        body.innerHTML = entries.map((e) => this.ledgerRow(e, currency)).join('');
        refreshIcons(body);
      } catch (err) {
        body.innerHTML = '';
        if (emptyEl) {
          emptyEl.classList.remove('hidden');
          emptyEl.innerHTML = this.errorState(err);
          refreshIcons(emptyEl);
        }
        showToast(err.message || '加载账本失败', 'error');
      }
    },

    // 账本明细行（含「缓存命中」列，费用按货币显示前缀）
    ledgerRow(e, currency) {
      return `<tr>
        <td class="text-xs text-muted">${formatDate(e.created_at, false)}</td>
        <td class="text-xs text-mono">${escapeHtml((e.session_id || '—').slice(0, 8))}</td>
        <td class="text-xs">${escapeHtml(e.model || '—')}</td>
        <td class="text-xs">${escapeHtml(e.purpose || '—')}</td>
        <td class="text-xs text-mono">${(e.prompt_tokens || 0).toLocaleString()}</td>
        <td class="text-xs text-mono text-accent">${(e.cached_prompt_tokens || 0).toLocaleString()}</td>
        <td class="text-xs text-mono">${(e.completion_tokens || 0).toLocaleString()}</td>
        <td class="text-xs text-mono font-medium">${(e.total_tokens || 0).toLocaleString()}</td>
        <td class="text-xs text-mono text-accent">${formatCost(e.cost, currency)}</td>
      </tr>`;
    },

    // 预算估算
    async estimate() {
      const degree = document.getElementById('est-degree').value;
      const mode = document.getElementById('est-mode').value;
      const count = parseInt(document.getElementById('est-count').value, 10);
      const resultEl = document.getElementById('est-result');
      const btn = document.getElementById('est-btn');

      // 表单校验
      if (!count || count < 1) {
        showToast('请输入有效的生成数量（≥1）', 'warning');
        return;
      }

      const original = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = `<div class="spinner"></div><span>估算中…</span>`;
      refreshIcons(btn);

      try {
        const data = await API.estimateBudget({ degree, mode, count });
        resultEl.innerHTML = this.estimateResultHtml(data);
        refreshIcons(resultEl);
        showToast('估算完成', 'success');
      } catch (err) {
        resultEl.innerHTML = `
          <div class="card card--accent" style="background:var(--bg-primary);">
            <p class="text-danger text-sm">${escapeHtml(err.message || '估算失败')}</p>
          </div>`;
        showToast(err.message || '估算失败', 'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = original;
        refreshIcons(btn);
      }
    },

    // 估算结果 HTML（费用按当前货币显示前缀）
    estimateResultHtml(data) {
      const perCall = data.estimated_tokens_per_call || {};
      const total = data.estimated_total_tokens || {};
      return `
        <div class="card card--accent" style="background:var(--bg-primary);">
          <div class="flex items-center justify-between mb-md">
            <span class="text-xs text-muted">推荐模型</span>
            <span class="badge badge--accent">${escapeHtml(data.model || '—')}</span>
          </div>
          <div class="grid grid--2" style="gap:var(--space-md);">
            <div>
              <div class="text-xs text-muted mb-xs">单次调用 Token</div>
              <div class="text-mono text-sm" style="color:var(--text-primary);">${(perCall.total_tokens || 0).toLocaleString()}</div>
            </div>
            <div>
              <div class="text-xs text-muted mb-xs">总 Token</div>
              <div class="text-mono text-sm" style="color:var(--text-primary);">${(total.total_tokens || 0).toLocaleString()}</div>
            </div>
          </div>
          <hr class="divider" />
          <div class="flex items-center justify-between">
            <span class="text-sm text-secondary">预计总费用</span>
            <span class="text-display text-accent" style="font-size:1.3rem;font-weight:600;">${formatCost(data.estimated_cost, this.currency)}</span>
          </div>
        </div>`;
    },

    // 错误状态
    errorState(err) {
      return `
        <div class="empty-state" style="padding:var(--space-lg);">
          <div class="empty-state__icon text-danger" data-lucide="alert-triangle"></div>
          <div class="empty-state__title">加载失败</div>
          <p class="empty-state__desc">${escapeHtml(err.message || '未知错误')}</p>
        </div>`;
    },
  };
})();
