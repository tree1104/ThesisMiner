/* ==========================================================================
   ThesisMiner v7.0 - 系统设置页面
   多模型管理、步骤路由、货币切换、默认模型快捷配置、
   学术约束常量展示、模型定价表与关于信息
   页面注册到 window.Pages.settings，由 app.js 路由系统动态加载
   ========================================================================== */
(function () {
  'use strict';

  // 学位中文标签
  const DEGREE_LABELS = { master: '硕士', doctor: '博士' };

  // 步骤路由配置项（v7.0 新增）
  const STEPS = [
    { key: 'reasoner', label: '论题生成 (Reasoner)' },
    { key: 'mentor', label: '导师评审 (Mentor)' },
    { key: 'inspire', label: '创意涌现 (Inspire)' },
    { key: 'report', label: '开题报告 (Report)' },
    { key: 'search', label: '文献检索 (Search)' },
  ];

  window.Pages = window.Pages || {};
  window.Pages.settings = {
    // 缓存模型列表与货币，供步骤路由下拉与货币高亮复用
    _models: [],
    _currency: 'CNY',

    // 同步返回页面骨架
    render() {
      return `
        <header class="page-header">
          <div class="page-header__eyebrow">ThesisMiner · Settings</div>
          <h1 class="page-header__title">系统设置</h1>
          <p class="page-header__desc">管理多模型接入、步骤路由与计价货币，查看学术约束常量与模型定价，掌控系统运行参数。</p>
        </header>
        <div class="page-body">
          <div class="grid grid--2 mb-lg">
            <!-- 模型管理卡片（v7.0 替换原 AI 配置卡片） -->
            <div class="card">
              <div class="card__header">
                <div>
                  <div class="card__title">模型管理</div>
                  <div class="card__subtitle">多模型注册表 · 新增 / 编辑 / 删除</div>
                </div>
                <button class="btn btn-primary btn-sm" id="cfg-add-model" type="button">
                  <i data-lucide="plus"></i><span>新增模型</span>
                </button>
              </div>
              <div id="model-list" class="flex flex-col gap-sm">
                <div class="skeleton skeleton--text"></div>
                <div class="skeleton skeleton--text"></div>
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

          <!-- 默认模型快捷配置卡片（保留原 API Key / Base URL 作为回退默认） -->
          <div class="card mb-lg">
            <div class="card__header">
              <div>
                <div class="card__title">默认模型快捷配置</div>
                <div class="card__subtitle">全局回退 Key 与 Base URL · 同步至 models[0] 或作为兜底</div>
              </div>
              <span class="badge badge--default" id="ai-status-badge"><span class="badge__dot"></span>检测中</span>
            </div>
            <div class="grid grid--2">
              <div class="form-group">
                <label class="form-label" for="cfg-apikey">API Key</label>
                <div class="flex gap-sm">
                  <input type="password" class="form-control" id="cfg-apikey" placeholder="sk-..." autocomplete="off" />
                  <button class="btn btn-secondary btn-icon" id="cfg-apikey-toggle" type="button" title="显示/隐藏" aria-label="显示/隐藏 API Key">
                    <i data-lucide="eye"></i>
                  </button>
                </div>
                <div class="form-hint">密钥仅存储于本地 data/config.json，不会上传。留空则不修改。</div>
              </div>
              <div class="form-group">
                <label class="form-label" for="cfg-baseurl">Base URL</label>
                <input type="text" class="form-control" id="cfg-baseurl" placeholder="https://api.openai.com/v1" value="https://api.openai.com/v1" />
                <div class="form-hint">OpenAI 兼容接口地址，需以 http(s):// 开头。</div>
              </div>
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

          <!-- 步骤路由 + 货币切换 -->
          <div class="grid grid--2 mb-lg">
            <!-- 步骤路由卡片（v7.0 新增） -->
            <div class="card">
              <div class="card__header">
                <div>
                  <div class="card__title">步骤路由</div>
                  <div class="card__subtitle">为各执行步骤指定模型</div>
                </div>
                <i data-lucide="route" style="color:var(--accent-primary);"></i>
              </div>
              <div id="step-routing-list" class="flex flex-col gap-sm">
                <div class="skeleton skeleton--text"></div>
              </div>
            </div>

            <!-- 货币切换卡片（v7.0 新增） -->
            <div class="card">
              <div class="card__header">
                <div>
                  <div class="card__title">计价货币</div>
                  <div class="card__subtitle">切换预算看板与账本的货币单位</div>
                </div>
                <i data-lucide="coins" style="color:var(--accent-primary);"></i>
              </div>
              <div class="flex gap-sm">
                <button class="btn btn-secondary flex-1" id="currency-cny" type="button">人民币 (¥)</button>
                <button class="btn btn-secondary flex-1" id="currency-usd" type="button">美元 ($)</button>
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
              <span class="badge badge--accent">v7.0</span>
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

    // 挂载：绑定事件并并行加载配置、模型、路由、定价与状态
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

      // 新增模型按钮
      container.querySelector('#cfg-add-model')?.addEventListener('click', () => this.openModelDrawer(null));

      // 模型列表事件委托：编辑 / 删除
      const modelList = container.querySelector('#model-list');
      if (modelList) {
        modelList.addEventListener('click', (e) => {
          const editBtn = e.target.closest('[data-edit-model]');
          const delBtn = e.target.closest('[data-delete-model]');
          if (editBtn) {
            const id = editBtn.dataset.editModel;
            const model = (this._models || []).find((m) => m.id === id);
            if (model) this.openModelDrawer(model);
          } else if (delBtn) {
            this.confirmDeleteModel(delBtn.dataset.deleteModel);
          }
        });
      }

      // 货币切换
      container.querySelector('#currency-cny')?.addEventListener('click', () => this.switchCurrency('CNY'));
      container.querySelector('#currency-usd')?.addEventListener('click', () => this.switchCurrency('USD'));

      // 真实文献检索开关
      const searchToggle = container.querySelector('#cfg-real-search-toggle');
      if (searchToggle) {
        searchToggle.addEventListener('click', () => this.toggleRealSearch());
      }

      await Promise.all([
        this.loadConfig(),
        this.loadModels(),
        this.loadPricing(),
        this.refreshStatus(),
        this.loadSearchStatus(),
      ]);
      // 模型列表加载完成后再加载步骤路由（下拉依赖 _models 缓存）
      await this.loadStepModels();
      // 货币默认高亮（后端默认 CNY）
      this.renderCurrency(this._currency || 'CNY');
    },

    // 加载默认配置并填充快捷表单与约束常量
    async loadConfig() {
      try {
        const cfg = await API.getConfig();
        const baseUrl = document.getElementById('cfg-baseurl');
        const apikey = document.getElementById('cfg-apikey');
        if (baseUrl && cfg.ai_base_url) baseUrl.value = cfg.ai_base_url;
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

    /* ----------------------------------------------------------------------
       v7.0 模型管理
       ---------------------------------------------------------------------- */

    // 加载模型列表并渲染
    async loadModels() {
      const listEl = document.getElementById('model-list');
      if (!listEl) return;
      try {
        const data = await API.getModels();
        const models = (data && data.models) || [];
        this._models = models;
        this.renderModels(models);
      } catch (err) {
        listEl.innerHTML = `<div class="empty-state text-danger" style="padding:var(--space-lg);">
          <div class="empty-state__icon" data-lucide="alert-triangle"></div>
          <div class="empty-state__title">加载失败</div>
          <p class="empty-state__desc">${escapeHtml(err.message || '未知错误')}</p>
        </div>`;
        refreshIcons(listEl);
        showToast(err.message || '加载模型失败', 'error');
      }
    },

    // 渲染模型卡片列表
    renderModels(models) {
      const listEl = document.getElementById('model-list');
      if (!listEl) return;
      if (!models || models.length === 0) {
        listEl.innerHTML = `<div class="empty-state" style="padding:var(--space-lg);">
          <div class="empty-state__icon" data-lucide="boxes"></div>
          <div class="empty-state__title">暂无模型</div>
          <p class="empty-state__desc">点击「新增模型」添加第一个模型配置。</p>
        </div>`;
        refreshIcons(listEl);
        return;
      }
      listEl.innerHTML = models.map((m) => this.modelCard(m)).join('');
      refreshIcons(listEl);
    },

    // 单个模型卡片
    modelCard(m) {
      const pricing = m.pricing || {};
      const badges = [];
      if (m.supports_streaming) badges.push('<span class="badge badge--default" style="font-size:0.6rem">流式</span>');
      if (m.supports_thinking) badges.push('<span class="badge badge--default" style="font-size:0.6rem">思考</span>');
      if (m.supports_web_search) badges.push('<span class="badge badge--default" style="font-size:0.6rem">联网</span>');

      return `
        <div class="card mb-sm" data-model-id="${escapeHtml(m.id)}" style="padding:var(--space-md);">
          <div class="card__header" style="padding:0;">
            <div class="flex-1">
              <div class="flex items-center gap-sm">
                <span class="text-sm font-medium">${escapeHtml(m.label || m.id)}</span>
                <span class="text-xs text-muted text-mono">${escapeHtml(m.id)}</span>
              </div>
              <div class="flex gap-xs mt-xs">
                ${badges.join('')}
              </div>
            </div>
            <div class="flex gap-xs">
              <button class="btn btn-ghost btn-icon btn-sm" data-edit-model="${escapeHtml(m.id)}" title="编辑">
                <i data-lucide="pencil" style="width:14px;height:14px"></i>
              </button>
              <button class="btn btn-ghost btn-icon btn-sm" data-delete-model="${escapeHtml(m.id)}" title="删除">
                <i data-lucide="trash-2" style="width:14px;height:14px;color:var(--danger)"></i>
              </button>
            </div>
          </div>
          <div class="text-xs text-muted" style="margin-top:var(--space-xs);">
            输入 ¥${pricing.input_cny_per_million || 0}/百万 · 输出 ¥${pricing.output_cny_per_million || 0}/百万 · 上下文 ${m.max_context || 32768}
          </div>
        </div>
      `;
    },

    // 打开模型新增/编辑抽屉
    openModelDrawer(model) {
      const isEdit = !!model;
      const m = model || {
        id: '',
        label: '',
        base_url: '',
        api_key: '',
        pricing: { input_cny_per_million: 0, output_cny_per_million: 0 },
        supports_streaming: true,
        supports_thinking: false,
        supports_web_search: false,
        max_context: 32768,
        default_temperature: 0.7,
      };
      const pricing = m.pricing || {};

      showDrawer({
        title: isEdit ? '编辑模型' : '新增模型',
        bodyHtml: `
          <div class="form-group">
            <label class="form-label" for="m-id">模型 ID<span class="required">*</span></label>
            <input type="text" class="form-control" id="m-id" value="${escapeHtml(m.id)}" ${isEdit ? 'disabled' : ''} placeholder="如 gpt-4.1-mini" />
            <div class="form-hint">唯一标识，创建后不可修改。</div>
          </div>
          <div class="form-group">
            <label class="form-label" for="m-label">显示名称</label>
            <input type="text" class="form-control" id="m-label" value="${escapeHtml(m.label || '')}" placeholder="如 GPT-4.1 Mini" />
          </div>
          <div class="form-group">
            <label class="form-label" for="m-baseurl">Base URL</label>
            <input type="text" class="form-control" id="m-baseurl" value="${escapeHtml(m.base_url || '')}" placeholder="https://api.openai.com/v1" />
          </div>
          <div class="form-group">
            <label class="form-label" for="m-apikey">API Key</label>
            <input type="password" class="form-control" id="m-apikey" value="${escapeHtml(m.api_key || '')}" placeholder="留空使用默认 Key" autocomplete="off" />
          </div>
          <div class="grid grid--2">
            <div class="form-group">
              <label class="form-label" for="m-input">输入价格（¥/百万 token）</label>
              <input type="number" class="form-control" id="m-input" value="${pricing.input_cny_per_million || 0}" step="0.01" min="0" />
            </div>
            <div class="form-group">
              <label class="form-label" for="m-output">输出价格（¥/百万 token）</label>
              <input type="number" class="form-control" id="m-output" value="${pricing.output_cny_per_million || 0}" step="0.01" min="0" />
            </div>
          </div>
          <div class="grid grid--2">
            <div class="form-group">
              <label class="form-label" for="m-context">最大上下文</label>
              <input type="number" class="form-control" id="m-context" value="${m.max_context || 32768}" step="1" min="1" />
            </div>
            <div class="form-group">
              <label class="form-label" for="m-temp">默认温度</label>
              <input type="number" class="form-control" id="m-temp" value="${m.default_temperature != null ? m.default_temperature : 0.7}" step="0.1" min="0" max="2" />
            </div>
          </div>
          <div class="form-group" style="margin-bottom:0;">
            <div class="flex flex-col gap-sm">
              <label class="flex items-center gap-sm" style="cursor:pointer;">
                <input type="checkbox" id="m-stream" ${m.supports_streaming ? 'checked' : ''} />
                <span class="text-sm">支持流式输出</span>
              </label>
              <label class="flex items-center gap-sm" style="cursor:pointer;">
                <input type="checkbox" id="m-think" ${m.supports_thinking ? 'checked' : ''} />
                <span class="text-sm">支持思考模式</span>
              </label>
              <label class="flex items-center gap-sm" style="cursor:pointer;">
                <input type="checkbox" id="m-web" ${m.supports_web_search ? 'checked' : ''} />
                <span class="text-sm">支持联网搜索</span>
              </label>
            </div>
          </div>
        `,
        footerHtml: `
          <button class="btn btn-ghost" id="m-cancel" type="button">取消</button>
          <button class="btn btn-primary" id="m-save" type="button"><i data-lucide="save"></i><span>保存</span></button>
        `,
        onMount: (drawer) => {
          drawer.querySelector('#m-save')?.addEventListener('click', () => this.saveModelFromDrawer(isEdit, model));
          drawer.querySelector('#m-cancel')?.addEventListener('click', () => closeDrawer());
        },
      });
    },

    // 从抽屉表单收集数据并保存（新增或更新）
    async saveModelFromDrawer(isEdit, originalModel) {
      const idEl = document.getElementById('m-id');
      const id = (idEl && idEl.value || '').trim();
      if (!id) {
        showToast('请填写模型 ID', 'warning');
        return;
      }
      const payload = {
        id: id,
        label: (document.getElementById('m-label').value || '').trim(),
        base_url: (document.getElementById('m-baseurl').value || '').trim(),
        api_key: (document.getElementById('m-apikey').value || '').trim(),
        pricing: {
          input_cny_per_million: Number(document.getElementById('m-input').value || 0),
          output_cny_per_million: Number(document.getElementById('m-output').value || 0),
        },
        supports_streaming: document.getElementById('m-stream').checked,
        supports_thinking: document.getElementById('m-think').checked,
        supports_web_search: document.getElementById('m-web').checked,
        max_context: Number(document.getElementById('m-context').value || 32768),
        default_temperature: Number(document.getElementById('m-temp').value || 0.7),
      };
      // 编辑时若 api_key 留空，保留原 key
      if (isEdit && !payload.api_key && originalModel) {
        payload.api_key = originalModel.api_key || '';
      }
      const btn = document.getElementById('m-save');
      if (btn) btn.disabled = true;
      try {
        if (isEdit) {
          await API.updateModel(originalModel.id, payload);
          showToast('模型已更新', 'success');
        } else {
          await API.addModel(payload);
          showToast('模型已新增', 'success');
        }
        closeDrawer();
        await this.loadModels();
        await this.loadStepModels();
      } catch (err) {
        showToast(err.message || '保存模型失败', 'error');
      } finally {
        if (btn) btn.disabled = false;
      }
    },

    // 删除模型（带确认）
    async confirmDeleteModel(modelId) {
      if (!window.confirm(`确定删除模型「${modelId}」？此操作不可撤销。`)) return;
      try {
        await API.deleteModel(modelId);
        showToast('模型已删除', 'success');
        await this.loadModels();
        await this.loadStepModels();
      } catch (err) {
        showToast(err.message || '删除模型失败', 'error');
      }
    },

    /* ----------------------------------------------------------------------
       v7.0 步骤路由
       ---------------------------------------------------------------------- */

    // 加载步骤路由配置并渲染下拉
    async loadStepModels() {
      const container = document.getElementById('step-routing-list');
      if (!container) return;
      try {
        const data = await API.getStepModels();
        const stepModels = (data && data.step_models) || {};
        this.renderStepModels(stepModels);
      } catch (err) {
        container.innerHTML = `<div class="text-xs text-danger">${escapeHtml(err.message || '加载步骤路由失败')}</div>`;
      }
    },

    // 渲染步骤路由下拉列表
    renderStepModels(stepModels) {
      const container = document.getElementById('step-routing-list');
      if (!container) return;
      const models = this._models || [];
      const options = models
        .map((m) => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.label || m.id)}</option>`)
        .join('');
      container.innerHTML = STEPS.map((step) => `
        <div class="form-group" style="margin-bottom:0;">
          <label class="form-label" for="step-${step.key}">${escapeHtml(step.label)}</label>
          <select class="form-control" id="step-${step.key}" data-step-key="${step.key}">
            ${options || '<option value="">暂无可用模型</option>'}
          </select>
        </div>
      `).join('');
      // 设置当前值
      STEPS.forEach((step) => {
        const sel = container.querySelector(`#step-${step.key}`);
        if (sel) sel.value = stepModels[step.key] || '';
      });
      // 绑定 change 事件
      container.querySelectorAll('select[data-step-key]').forEach((sel) => {
        sel.addEventListener('change', () => this.updateStepModel(sel.dataset.stepKey, sel.value));
      });
    },

    // 更新单个步骤的路由模型
    async updateStepModel(key, modelId) {
      try {
        await API.updateStepModels({ [key]: modelId });
        showToast('步骤路由已更新', 'success');
      } catch (err) {
        showToast(err.message || '更新步骤路由失败', 'error');
        await this.loadStepModels();
      }
    },

    /* ----------------------------------------------------------------------
       v7.0 货币切换
       ---------------------------------------------------------------------- */

    // 渲染货币高亮状态
    renderCurrency(currency) {
      const cnyBtn = document.getElementById('currency-cny');
      const usdBtn = document.getElementById('currency-usd');
      if (cnyBtn) {
        cnyBtn.classList.toggle('btn-primary', currency === 'CNY');
        cnyBtn.classList.toggle('btn-secondary', currency !== 'CNY');
      }
      if (usdBtn) {
        usdBtn.classList.toggle('btn-primary', currency === 'USD');
        usdBtn.classList.toggle('btn-secondary', currency !== 'USD');
      }
    },

    // 切换计价货币
    async switchCurrency(currency) {
      if (currency === this._currency) return;
      try {
        await API.updateCurrency(currency);
        this._currency = currency;
        this.renderCurrency(currency);
        showToast(`计价货币已切换为 ${currency === 'CNY' ? '人民币' : '美元'}`, 'success');
      } catch (err) {
        showToast(err.message || '切换货币失败', 'error');
      }
    },

    /* ----------------------------------------------------------------------
       定价表 / 状态 / 检索
       ---------------------------------------------------------------------- */

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

    /* ----------------------------------------------------------------------
       默认模型快捷配置：校验 / 保存 / 测试
       ---------------------------------------------------------------------- */

    // 表单校验：返回 { baseUrl, apikey } 或 null
    validate() {
      const baseUrl = (document.getElementById('cfg-baseurl').value || '').trim();
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
      const apikey = (document.getElementById('cfg-apikey').value || '').trim();
      return { baseUrl, apikey };
    },

    // 保存默认配置
    async save() {
      const validated = this.validate();
      if (!validated) return;
      const { baseUrl, apikey } = validated;
      const btn = document.getElementById('cfg-save');
      const original = btn ? btn.innerHTML : '';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<div class="spinner"></div><span>保存中…</span>`;
        refreshIcons(btn);
      }
      try {
        const payload = { ai_base_url: baseUrl };
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
        // 同步全局顶栏徽章
        if (typeof window.updateApiStatus === 'function') {
          window.updateApiStatus();
        }
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

    // 测试连接：检查 ai_configured，并同步全局徽章
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
        // 同步全局顶栏 API 状态徽章（Task 10.2）
        if (typeof window.updateApiStatus === 'function') {
          window.updateApiStatus();
        }
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
