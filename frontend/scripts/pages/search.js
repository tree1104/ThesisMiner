/* ==========================================================================
   ThesisMiner v9.0 - 会话历史检索页面（Task 12）
   全文关键词 + 多条件筛选（时间范围 / 会话 / Agent / 阶段）
   支持关键词高亮、分页、导出结果，点击结果跳转会话详情
   页面注册到 window.Pages.search，由 app.js 路由系统动态加载
   ========================================================================== */
(function () {
  'use strict';

  // Agent 配色与标签（与 sessions.js 保持一致）
  const AGENT_COLORS = {
    orchestrator: '#4F46E5',
    reasoner: '#3B82F6',
    mentor: '#10B981',
    critic: '#F59E0B',
    writer: '#8B5CF6',
    searcher: '#EC4899',
  };

  const AGENT_LABELS = {
    orchestrator: 'Orchestrator',
    reasoner: 'Reasoner',
    mentor: 'Mentor',
    critic: 'Critic',
    writer: 'Writer',
    searcher: 'Searcher',
  };

  // 阶段标签与徽章配色
  const STAGE_LABELS = {
    info_confirm: { label: '信息确权', cls: 'badge--info' },
    creativity: { label: '谱系创意', cls: 'badge--accent' },
    validation: { label: '重复度校验', cls: 'badge--warning' },
    generation: { label: '内容生成', cls: 'badge--success' },
    deep_assist: { label: '深度辅助', cls: 'badge--default' },
    thesis_writing: { label: '论文撰写', cls: 'badge--accent' },
    defense_prep: { label: '答辩准备', cls: 'badge--info' },
    completed: { label: '已完成', cls: 'badge--success' },
  };

  // 内容片段截断长度
  const SNIPPET_LENGTH = 200;
  // 关键词输入防抖延迟
  const KEYWORD_DEBOUNCE = 350;

  // 页面状态
  const state = {
    keyword: '',
    sessionId: '',
    agentId: '',
    stage: '',
    dateFrom: '',
    dateTo: '',
    page: 1,
    pageSize: 20,
    total: 0,
    results: [],
    sessions: [],
    loading: false,
    searched: false,
    filtersOpen: true,
    expandedIds: new Set(),
  };

  // 取 Agent 配色
  function agentColor(agentId) {
    return AGENT_COLORS[agentId] || '#4F46E5';
  }

  // 取 Agent 标签
  function agentLabel(agentId) {
    return AGENT_LABELS[agentId] || (agentId || 'Agent');
  }

  // hex 转 rgba
  function hexToRgba(hex, alpha) {
    const h = (hex || '#4F46E5').replace('#', '');
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + (alpha || 0.15) + ')';
  }

  // 阶段徽章 HTML
  function stageBadge(stage) {
    if (!stage) return '';
    const cfg = STAGE_LABELS[stage] || { label: stage, cls: 'badge--default' };
    return '<span class="badge ' + cfg.cls + '"><span class="badge__dot"></span>' + escapeHtml(cfg.label) + '</span>';
  }

  // 关键词高亮：将匹配的关键词包裹在 <mark> 中（大小写不敏感）
  function highlightKeyword(text, keyword) {
    const safe = escapeHtml(text || '');
    if (!keyword || !keyword.trim()) return safe;
    const kw = keyword.trim();
    // 转义正则特殊字符
    const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    try {
      const re = new RegExp('(' + escaped + ')', 'gi');
      return safe.replace(re, '<mark class="search-highlight">$1</mark>');
    } catch (_) {
      return safe;
    }
  }

  // 生成内容片段：长文本截断到 SNIPPET_LENGTH 字符
  function makeSnippet(text, expanded) {
    if (!text) return '';
    const str = String(text);
    if (expanded || str.length <= SNIPPET_LENGTH) return str;
    return str.slice(0, SNIPPET_LENGTH).trimEnd() + '…';
  }

  window.Pages = window.Pages || {};
  window.Pages.search = {
    // 同步返回页面骨架
    render() {
      return '' +
        '<header class="page-header">' +
          '<div class="page-header__eyebrow">ThesisMiner · Search</div>' +
          '<h1 class="page-header__title">会话检索</h1>' +
          '<p class="page-header__desc">在全量会话历史中按关键词、时间、会话、Agent 与阶段检索消息，快速定位历史交互。</p>' +
        '</header>' +
        '<div class="page-body">' +
          // 搜索栏
          '<div class="search-bar">' +
            '<div class="search-bar__input-wrap">' +
              '<i data-lucide="search" class="search-bar__icon"></i>' +
              '<input type="text" class="form-control search-bar__input" id="search-keyword" ' +
                'placeholder="输入关键词检索消息内容…" autocomplete="off" />' +
              '<button class="btn btn-ghost btn-icon btn-sm search-bar__clear" id="search-clear-input" ' +
                'title="清空关键词" aria-label="清空关键词" hidden>' +
                '<i data-lucide="x" style="width:14px;height:14px;"></i>' +
              '</button>' +
            '</div>' +
            '<button class="btn btn-primary" id="search-submit">' +
              '<i data-lucide="search"></i><span>搜索</span>' +
            '</button>' +
            '<button class="btn btn-secondary" id="search-toggle-filters">' +
              '<i data-lucide="sliders-horizontal"></i><span>筛选</span>' +
            '</button>' +
          '</div>' +
          // 筛选面板
          '<div class="search-filters" id="search-filters">' +
            '<div class="search-filters__grid">' +
              '<div class="form-group">' +
                '<label class="form-label" for="filter-session">会话</label>' +
                '<select class="form-control" id="filter-session">' +
                  '<option value="">全部会话</option>' +
                '</select>' +
              '</div>' +
              '<div class="form-group">' +
                '<label class="form-label" for="filter-agent">Agent 类型</label>' +
                '<select class="form-control" id="filter-agent">' +
                  '<option value="">全部 Agent</option>' +
                  Object.keys(AGENT_LABELS).map((k) =>
                    '<option value="' + k + '">' + escapeHtml(AGENT_LABELS[k]) + '</option>'
                  ).join('') +
                '</select>' +
              '</div>' +
              '<div class="form-group">' +
                '<label class="form-label" for="filter-stage">阶段</label>' +
                '<select class="form-control" id="filter-stage">' +
                  '<option value="">全部阶段</option>' +
                  Object.keys(STAGE_LABELS).map((k) =>
                    '<option value="' + k + '">' + escapeHtml(STAGE_LABELS[k].label) + '</option>'
                  ).join('') +
                '</select>' +
              '</div>' +
              '<div class="form-group">' +
                '<label class="form-label" for="filter-date-from">起始日期</label>' +
                '<input type="date" class="form-control" id="filter-date-from" />' +
              '</div>' +
              '<div class="form-group">' +
                '<label class="form-label" for="filter-date-to">截止日期</label>' +
                '<input type="date" class="form-control" id="filter-date-to" />' +
              '</div>' +
            '</div>' +
            '<div class="search-filters__actions">' +
              '<button class="btn btn-ghost btn-sm" id="search-reset">' +
                '<i data-lucide="rotate-ccw"></i><span>清除筛选</span>' +
              '</button>' +
              '<button class="btn btn-ghost btn-sm" id="search-export" disabled>' +
                '<i data-lucide="download"></i><span>导出结果</span>' +
              '</button>' +
            '</div>' +
          '</div>' +
          // 结果区域
          '<div class="search-results" id="search-results">' +
            this.resultsPlaceholderHtml() +
          '</div>' +
        '</div>';
    },

    // 初始占位（未搜索时的引导状态）
    resultsPlaceholderHtml() {
      return '' +
        '<div class="empty-state">' +
          '<div class="empty-state__icon" data-lucide="search"></div>' +
          '<div class="empty-state__title">开始检索</div>' +
          '<p class="empty-state__desc">输入关键词或设置筛选条件，检索全量会话历史消息。</p>' +
        '</div>';
    },

    // 加载中骨架
    resultsLoadingHtml() {
      let cards = '';
      for (let i = 0; i < 4; i++) {
        cards += '' +
          '<div class="search-card search-card--skeleton">' +
            '<div class="skeleton skeleton--title" style="width:40%;"></div>' +
            '<div class="skeleton skeleton--text" style="width:90%;"></div>' +
            '<div class="skeleton skeleton--text" style="width:75%;"></div>' +
            '<div class="skeleton skeleton--text" style="width:60%;"></div>' +
          '</div>';
      }
      return cards;
    },

    // 空结果状态
    resultsEmptyHtml() {
      return '' +
        '<div class="empty-state">' +
          '<div class="empty-state__icon" data-lucide="inbox"></div>' +
          '<div class="empty-state__title">未找到匹配结果</div>' +
          '<p class="empty-state__desc">尝试更换关键词或调整筛选条件。</p>' +
        '</div>';
    },

    // 错误状态
    resultsErrorHtml(err) {
      return '' +
        '<div class="empty-state">' +
          '<div class="empty-state__icon text-danger" data-lucide="alert-triangle"></div>' +
          '<div class="empty-state__title">检索失败</div>' +
          '<p class="empty-state__desc">' + escapeHtml(err.message || '未知错误') + '</p>' +
        '</div>';
    },

    // app.js 调用入口
    async init() {
      const container = document.getElementById('app-content');
      if (container) await this.mount(container);
    },

    // 挂载：绑定事件并加载会话下拉
    async mount(container) {
      this.bindEvents(container);
      await this.loadSessions();
      // 首次进入自动加载第一页（无关键词，展示全部）
      await this.search();
    },

    // 绑定所有事件
    bindEvents(container) {
      const keywordInput = container.querySelector('#search-keyword');
      const clearInputBtn = container.querySelector('#search-clear-input');
      const submitBtn = container.querySelector('#search-submit');
      const toggleFiltersBtn = container.querySelector('#search-toggle-filters');
      const resetBtn = container.querySelector('#search-reset');
      const exportBtn = container.querySelector('#search-export');
      const sessionFilter = container.querySelector('#filter-session');
      const agentFilter = container.querySelector('#filter-agent');
      const stageFilter = container.querySelector('#filter-stage');
      const dateFromFilter = container.querySelector('#filter-date-from');
      const dateToFilter = container.querySelector('#filter-date-to');

      // 关键词输入：防抖实时搜索 + 清空按钮显隐
      const debouncedSearch = debounce(() => {
        state.page = 1;
        this.search();
      }, KEYWORD_DEBOUNCE);

      if (keywordInput) {
        keywordInput.addEventListener('input', () => {
          state.keyword = keywordInput.value;
          if (clearInputBtn) clearInputBtn.hidden = !state.keyword;
          debouncedSearch();
        });
        // 回车立即搜索
        keywordInput.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            state.page = 1;
            this.search();
          }
        });
      }

      // 清空关键词按钮
      if (clearInputBtn) {
        clearInputBtn.addEventListener('click', () => {
          if (keywordInput) {
            keywordInput.value = '';
            state.keyword = '';
            clearInputBtn.hidden = true;
            state.page = 1;
            this.search();
            keywordInput.focus();
          }
        });
      }

      // 搜索按钮
      if (submitBtn) {
        submitBtn.addEventListener('click', () => {
          state.page = 1;
          this.search();
        });
      }

      // 折叠/展开筛选面板
      if (toggleFiltersBtn) {
        toggleFiltersBtn.addEventListener('click', () => {
          state.filtersOpen = !state.filtersOpen;
          const panel = container.querySelector('#search-filters');
          if (panel) panel.classList.toggle('search-filters--collapsed', !state.filtersOpen);
        });
      }

      // 筛选项变更：实时触发搜索
      const onFilterChange = () => {
        state.sessionId = sessionFilter ? sessionFilter.value : '';
        state.agentId = agentFilter ? agentFilter.value : '';
        state.stage = stageFilter ? stageFilter.value : '';
        state.dateFrom = dateFromFilter ? dateFromFilter.value : '';
        state.dateTo = dateToFilter ? dateToFilter.value : '';
        state.page = 1;
        this.search();
      };
      [sessionFilter, agentFilter, stageFilter, dateFromFilter, dateToFilter].forEach((el) => {
        if (el) el.addEventListener('change', onFilterChange);
      });

      // 清除筛选
      if (resetBtn) {
        resetBtn.addEventListener('click', () => {
          state.keyword = '';
          state.sessionId = '';
          state.agentId = '';
          state.stage = '';
          state.dateFrom = '';
          state.dateTo = '';
          state.page = 1;
          state.expandedIds = new Set();
          if (keywordInput) keywordInput.value = '';
          if (clearInputBtn) clearInputBtn.hidden = true;
          if (sessionFilter) sessionFilter.value = '';
          if (agentFilter) agentFilter.value = '';
          if (stageFilter) stageFilter.value = '';
          if (dateFromFilter) dateFromFilter.value = '';
          if (dateToFilter) dateToFilter.value = '';
          this.search();
          showToast('已清除全部筛选条件', 'info');
        });
      }

      // 导出结果
      if (exportBtn) {
        exportBtn.addEventListener('click', () => this.exportResults());
      }
    },

    // 加载会话下拉列表
    async loadSessions() {
      const sessionFilter = document.getElementById('filter-session');
      if (!sessionFilter) return;
      try {
        const data = await API.getSearchSessions();
        state.sessions = (data && data.sessions) || [];
        const options = '<option value="">全部会话</option>' +
          state.sessions.map((s) =>
            '<option value="' + escapeHtml(s.id) + '">' + escapeHtml(s.title || '未命名会话') + '</option>'
          ).join('');
        sessionFilter.innerHTML = options;
        // 恢复选中状态
        if (state.sessionId) sessionFilter.value = state.sessionId;
      } catch (err) {
        // 静默失败，下拉仅保留默认项
        console.warn('[Search] 加载会话列表失败', err);
      }
    },

    // 收集当前筛选参数
    buildParams() {
      return {
        q: state.keyword || '',
        session_id: state.sessionId || '',
        agent_id: state.agentId || '',
        stage: state.stage || '',
        date_from: state.dateFrom || '',
        date_to: state.dateTo || '',
        page: state.page,
        page_size: state.pageSize,
      };
    },

    // 执行搜索
    async search() {
      const resultsEl = document.getElementById('search-results');
      const exportBtn = document.getElementById('search-export');
      if (!resultsEl) return;

      state.loading = true;
      resultsEl.innerHTML = this.resultsLoadingHtml();
      refreshIcons(resultsEl);

      try {
        const data = await API.searchMessages(this.buildParams());
        state.results = (data && data.results) || [];
        state.total = (data && data.total) || 0;
        state.searched = true;
        this.renderResults();
      } catch (err) {
        state.results = [];
        state.total = 0;
        resultsEl.innerHTML = this.resultsErrorHtml(err);
        refreshIcons(resultsEl);
        showToast(err.message || '检索失败', 'error');
      } finally {
        state.loading = false;
        if (exportBtn) exportBtn.disabled = state.results.length === 0;
      }
    },

    // 渲染结果列表
    renderResults() {
      const resultsEl = document.getElementById('search-results');
      if (!resultsEl) return;

      if (state.results.length === 0) {
        resultsEl.innerHTML = this.resultsEmptyHtml();
        refreshIcons(resultsEl);
        return;
      }

      const resultsHtml = state.results.map((r) => this.resultCardHtml(r)).join('');
      const paginationHtml = this.paginationHtml();
      const summaryHtml = '' +
        '<div class="search-summary">' +
          '<span class="text-sm text-secondary">共 <strong class="text-accent">' + state.total + '</strong> 条结果' +
          (state.total > state.pageSize ? '，第 ' + state.page + ' 页' : '') +
          '</span>' +
        '</div>';

      resultsEl.innerHTML = summaryHtml + '<div class="search-list">' + resultsHtml + '</div>' + paginationHtml;
      refreshIcons(resultsEl);

      // 绑定结果卡片事件
      resultsEl.querySelectorAll('[data-result-id]').forEach((el) => {
        const id = el.dataset.resultId;
        const sessionId = el.dataset.sessionId;
        // 点击卡片跳转到会话历史页
        el.addEventListener('click', (e) => {
          if (e.target.closest('[data-action]')) return;
          this.jumpToSession(sessionId);
        });
        // 展开全文
        const expandBtn = el.querySelector('[data-action="expand"]');
        if (expandBtn) {
          expandBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            state.expandedIds.add(id);
            this.renderResults();
          });
        }
        // 收起全文
        const collapseBtn = el.querySelector('[data-action="collapse"]');
        if (collapseBtn) {
          collapseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            state.expandedIds.delete(id);
            this.renderResults();
          });
        }
      });

      // 绑定分页按钮
      const prevBtn = resultsEl.querySelector('[data-action="prev-page"]');
      if (prevBtn) prevBtn.addEventListener('click', (e) => { e.preventDefault(); this.changePage(state.page - 1); });
      const nextBtn = resultsEl.querySelector('[data-action="next-page"]');
      if (nextBtn) nextBtn.addEventListener('click', (e) => { e.preventDefault(); this.changePage(state.page + 1); });
      resultsEl.querySelectorAll('[data-action="goto-page"]').forEach((el) => {
        el.addEventListener('click', (e) => {
          e.preventDefault();
          this.changePage(parseInt(el.dataset.page, 10));
        });
      });
    },

    // 单条结果卡片 HTML
    resultCardHtml(r) {
      const id = r.id || '';
      const sessionId = r.session_id || '';
      const sessionName = r.session_name || '未命名会话';
      const conversationTitle = r.conversation_title || '';
      const agentId = r.agent_id || '';
      const role = r.role || '';
      const content = r.content || '';
      const created = r.created_at || '';
      const stage = r.stage || '';
      const color = agentColor(agentId);
      const label = agentLabel(agentId);
      const expanded = state.expandedIds.has(id);
      const isLong = content.length > SNIPPET_LENGTH;
      const snippet = makeSnippet(content, expanded);
      const highlighted = highlightKeyword(snippet, state.keyword);
      const isUser = role === 'user';

      // 展开/收起按钮
      let expandBtn = '';
      if (isLong) {
        expandBtn = expanded
          ? '<button class="btn btn-ghost btn-sm search-card__expand" data-action="collapse"><i data-lucide="chevron-up"></i><span>收起</span></button>'
          : '<button class="btn btn-ghost btn-sm search-card__expand" data-action="expand"><i data-lucide="chevron-down"></i><span>展开全文</span></button>';
      }

      return '' +
        '<div class="search-card" data-result-id="' + escapeHtml(id) + '" data-session-id="' + escapeHtml(sessionId) + '">' +
          '<div class="search-card__header">' +
            '<span class="search-card__agent" style="background:' + hexToRgba(color, 0.15) + ';color:' + color + ';border:1px solid ' + hexToRgba(color, 0.3) + ';">' +
              '<span style="width:6px;height:6px;border-radius:50%;background:' + color + ';"></span>' +
              escapeHtml(label) +
            '</span>' +
            '<span class="badge badge--default">' + (isUser ? '用户' : escapeHtml(role)) + '</span>' +
            (stage ? stageBadge(stage) : '') +
            '<span class="search-card__time">' +
              '<i data-lucide="clock" style="width:12px;height:12px;"></i>' +
              escapeHtml(formatDate(created)) +
            '</span>' +
          '</div>' +
          '<div class="search-card__content">' + highlighted + '</div>' +
          '<div class="search-card__footer">' +
            '<div class="search-card__session">' +
              '<i data-lucide="messages-square" style="width:13px;height:13px;"></i>' +
              '<span class="search-card__session-name">' + escapeHtml(sessionName) + '</span>' +
              (conversationTitle ? '<span class="search-card__conv-title">· ' + escapeHtml(conversationTitle) + '</span>' : '') +
            '</div>' +
            '<div class="search-card__actions">' +
              expandBtn +
              '<button class="btn btn-ghost btn-sm" data-action="jump" title="查看会话">' +
                '<i data-lucide="external-link"></i><span>查看会话</span>' +
              '</button>' +
            '</div>' +
          '</div>' +
        '</div>';
    },

    // 分页 HTML
    paginationHtml() {
      const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
      if (state.total <= state.pageSize) return '';

      const prevDisabled = state.page <= 1;
      const nextDisabled = state.page >= totalPages;

      // 生成页码按钮（最多显示 7 个）
      let pages = [];
      const maxButtons = 7;
      if (totalPages <= maxButtons) {
        for (let i = 1; i <= totalPages; i++) pages.push(i);
      } else {
        pages.push(1);
        const left = Math.max(2, state.page - 2);
        const right = Math.min(totalPages - 1, state.page + 2);
        if (left > 2) pages.push('...');
        for (let i = left; i <= right; i++) pages.push(i);
        if (right < totalPages - 1) pages.push('...');
        pages.push(totalPages);
      }

      const pageButtons = pages.map((p) => {
        if (p === '...') return '<span class="search-pagination__ellipsis">…</span>';
        const active = p === state.page;
        return '<button class="search-pagination__btn' + (active ? ' search-pagination__btn--active' : '') + '" ' +
          'data-action="goto-page" data-page="' + p + '">' + p + '</button>';
      }).join('');

      return '' +
        '<div class="search-pagination">' +
          '<button class="btn btn-ghost btn-sm search-pagination__nav" data-action="prev-page" ' +
            (prevDisabled ? 'disabled' : '') + '>' +
            '<i data-lucide="chevron-left"></i><span>上一页</span>' +
          '</button>' +
          '<div class="search-pagination__pages">' + pageButtons + '</div>' +
          '<button class="btn btn-ghost btn-sm search-pagination__nav" data-action="next-page" ' +
            (nextDisabled ? 'disabled' : '') + '>' +
            '<span>下一页</span><i data-lucide="chevron-right"></i>' +
          '</button>' +
        '</div>';
    },

    // 切换页码
    async changePage(page) {
      const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
      if (page < 1 || page > totalPages || page === state.page) return;
      state.page = page;
      await this.search();
      // 滚动到结果顶部
      const resultsEl = document.getElementById('search-results');
      if (resultsEl) resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },

    // 跳转到会话历史页
    jumpToSession(sessionId) {
      if (!sessionId) {
        showToast('该消息未关联会话', 'warning');
        return;
      }
      navigate('sessions');
    },

    // 导出结果为 JSON 文件
    exportResults() {
      if (state.results.length === 0) {
        showToast('没有可导出的结果', 'warning');
        return;
      }
      try {
        const exportData = state.results.map((r) => ({
          id: r.id,
          session_id: r.session_id,
          session_name: r.session_name,
          conversation_title: r.conversation_title,
          agent_id: r.agent_id,
          role: r.role,
          content: r.content,
          stage: r.stage || '',
          created_at: r.created_at,
        }));
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'thesisminer-search-' + new Date().toISOString().slice(0, 10) + '.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('已导出 ' + exportData.length + ' 条结果', 'success');
      } catch (err) {
        showToast('导出失败：' + (err.message || err), 'error');
      }
    },
  };
})();
