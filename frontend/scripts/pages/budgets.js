/* ==========================================================================
   ThesisMiner v6.0 - 预算看板页面
   汇总调用成本、估算会话预算、展示账本明细与按模型分组统计
   页面注册到 window.Pages.budgets，由 app.js 路由系统动态加载
   ========================================================================== */
(function () {
  'use strict';

  // 表格骨架行
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
      </tr>`;
    }
    return rows;
  }

  window.Pages = window.Pages || {};
  window.Pages.budgets = {
    // 同步返回页面骨架
    render() {
      return `
        <header class="page-header">
          <div class="page-header__eyebrow">ThesisMiner · Budgets</div>
          <h1 class="page-header__title">预算看板</h1>
          <p class="page-header__desc">透明记录每一次 AI 调用的 token 用量与费用，估算会话成本，掌控学术投入。</p>
        </header>
        <div class="page-body">
          <!-- 顶部汇总卡片 -->
          <div class="grid grid--3 mb-lg">
            <div class="stat-card">
              <div class="stat-card__icon" data-lucide="hash"></div>
              <div class="stat-card__label">总调用次数</div>
              <div class="stat-card__value" id="sum-calls">—</div>
            </div>
            <div class="stat-card">
              <div class="stat-card__icon" data-lucide="cpu"></div>
              <div class="stat-card__label">总 Token 数</div>
              <div class="stat-card__value stat-card__value-mono" id="sum-tokens">—</div>
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

            <!-- 按模型分组统计 -->
            <div class="card">
              <div class="card__header">
                <div>
                  <div class="card__title">按模型分组</div>
                  <div class="card__subtitle">调用次数与费用占比</div>
                </div>
                <i data-lucide="bar-chart-3" style="color:var(--accent-primary);"></i>
              </div>
              <div id="by-model-list" class="flex flex-col gap-md">
                <div class="skeleton skeleton--block"></div>
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
                    <th>会话 ID</th>
                    <th>模型</th>
                    <th>Prompt</th>
                    <th>Completion</th>
                    <th>总 Tokens</th>
                    <th>费用</th>
                    <th>用途</th>
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
      await Promise.all([this.loadSummary(), this.loadLedger()]);
    },

    // 加载汇总统计
    async loadSummary() {
      const callsEl = document.getElementById('sum-calls');
      const tokensEl = document.getElementById('sum-tokens');
      const costEl = document.getElementById('sum-cost');
      try {
        const data = await API.getBudgetSummary();
        const calls = data.total_calls || 0;
        const tokens = data.total_tokens || 0;
        const cost = data.total_cost || 0;
        if (callsEl) callsEl.textContent = String(calls);
        if (tokensEl) tokensEl.textContent = tokens.toLocaleString();
        if (costEl) costEl.textContent = formatCost(cost);
        this.renderByModel(data.by_model || {});
      } catch (err) {
        if (callsEl) callsEl.textContent = '—';
        if (tokensEl) tokensEl.textContent = '—';
        if (costEl) costEl.textContent = '—';
        const el = document.getElementById('by-model-list');
        if (el) {
          el.innerHTML = this.errorState(err);
          refreshIcons(el);
        }
        showToast(err.message || '加载汇总失败', 'error');
      }
    },

    // 渲染按模型分组（含 div 宽度模拟的柱状图）
    renderByModel(byModel) {
      const el = document.getElementById('by-model-list');
      if (!el) return;
      const entries = Object.entries(byModel || {});
      if (entries.length === 0) {
        el.innerHTML = `
          <div class="empty-state" style="padding:var(--space-lg);">
            <div class="empty-state__icon" data-lucide="bar-chart-3"></div>
            <div class="empty-state__title">暂无消耗记录</div>
          </div>`;
        refreshIcons(el);
        return;
      }
      // 以费用最大值为柱长基准
      const maxCost = Math.max(...entries.map(([, v]) => v.cost || 0), 0.0001);
      el.innerHTML = entries
        .map(([model, v]) => {
          const widthPct = Math.max(4, Math.round(((v.cost || 0) / maxCost) * 100));
          return `
            <div>
              <div class="flex items-center justify-between mb-sm">
                <span class="text-mono text-sm" style="color:var(--text-primary);">${escapeHtml(model)}</span>
                <span class="text-xs text-muted">${v.calls || 0} 次 · ${formatCost(v.cost || 0)}</span>
              </div>
              <div class="progress"><div class="progress__bar" style="width:${widthPct}%;"></div></div>
            </div>`;
        })
        .join('');
      refreshIcons(el);
    },

    // 加载账本明细
    async loadLedger() {
      const body = document.getElementById('ledger-body');
      const emptyEl = document.getElementById('ledger-empty');
      if (!body) return;
      body.innerHTML = skeletonRows();
      try {
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
        body.innerHTML = entries.map((e) => this.ledgerRow(e)).join('');
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

    // 账本明细行
    ledgerRow(e) {
      return `<tr>
        <td class="text-xs">${formatDate(e.created_at)}</td>
        <td class="table__cell-mono text-xs">${escapeHtml((e.session_id || '—').slice(0, 8))}</td>
        <td><span class="badge badge--default">${escapeHtml(e.model || '—')}</span></td>
        <td class="table__cell-mono">${(e.prompt_tokens || 0).toLocaleString()}</td>
        <td class="table__cell-mono">${(e.completion_tokens || 0).toLocaleString()}</td>
        <td class="table__cell-mono">${(e.total_tokens || 0).toLocaleString()}</td>
        <td class="table__cell-mono text-accent">${formatCost(e.cost)}</td>
        <td class="text-xs">${escapeHtml(e.purpose || '—')}</td>
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

    // 估算结果 HTML
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
            <span class="text-display text-accent" style="font-size:1.3rem;font-weight:600;">${formatCost(data.estimated_cost)}</span>
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
