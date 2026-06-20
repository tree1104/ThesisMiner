/* ==========================================================================
   ThesisMiner v9.0 - 论文撰写页面（Task 13）
   会话选择 → 大纲生成 → 章节撰写（分栏）→ 查重降重 → 答辩准备
   页面注册到 window.Pages.thesis，由 app.js 路由系统动态加载
   ========================================================================== */
(function () {
  'use strict';

  // 学位类型选项
  const DEGREES = [
    { value: 'bachelor', label: '本科' },
    { value: 'master', label: '硕士' },
    { value: 'doctor', label: '博士' },
  ];

  // 章节状态配置（徽章配色与中文标签）
  const CHAPTER_STATUS = {
    pending: { cls: 'badge--default', label: '待撰写' },
    draft: { cls: 'badge--warning', label: '草稿' },
    revised: { cls: 'badge--info', label: '已修订' },
    final: { cls: 'badge--success', label: '已完成' },
  };

  // 中文章节序号
  const CN_NUMS = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
    '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十'];

  // 页面状态
  const state = {
    sessions: [],
    sessionId: '',
    session: null,
    proposal: null,
    degree: 'master',
    outline: null,            // { title, chapters: [{ id, number, title, description }] }
    outlineLocked: false,
    chapters: [],             // [{ id, number, title, content, word_count, status }]
    activeChapterId: '',
    editing: false,
    plagiarism: null,         // { score, high_risk_sections: [], suggestions: [] }
    reducedContent: '',
    timeline: [],             // [{ action, time, detail }]
    loadingSessions: false,
    loadingOutline: false,
    loadingChapter: false,
    loadingPlagiarism: false,
    loadingDefense: {},
    defense: { ppt: null, questions: [], speech: '', evalFeedback: '' },
    activeQuestionIdx: null,
  };

  // 取章节状态徽章
  function statusBadge(status) {
    const cfg = CHAPTER_STATUS[status] || CHAPTER_STATUS.pending;
    return '<span class="badge ' + cfg.cls + '"><span class="badge__dot"></span>' + escapeHtml(cfg.label) + '</span>';
  }

  // 中文章节序号
  function cnNumber(n) {
    const i = parseInt(n, 10);
    if (i >= 1 && i <= CN_NUMS.length) return CN_NUMS[i - 1];
    return String(i);
  }

  // 字数统计
  function countWords(text) {
    if (!text) return 0;
    return String(text).replace(/\s+/g, '').length;
  }

  // 查重风险等级
  function plagiarismLevel(score) {
    const s = Number(score) || 0;
    if (s < 15) return { level: 'safe', color: 'var(--success)', label: '安全', cls: 'thesis-gauge--safe' };
    if (s <= 30) return { level: 'warning', color: 'var(--warning)', label: '警示', cls: 'thesis-gauge--warning' };
    return { level: 'danger', color: 'var(--danger)', label: '高风险', cls: 'thesis-gauge--danger' };
  }

  /* ----------------------------------------------------------------------
     轻量 Markdown 渲染器（标题 / 粗体 / 斜体 / 列表 / 段落 / 代码）
     ---------------------------------------------------------------------- */
  function renderMarkdown(md) {
    if (!md) return '';
    const text = String(md);
    // 先转义 HTML
    let html = escapeHtml(text);
    // 代码块 ```...```
    html = html.replace(/```([\s\S]*?)```/g, function (_, code) {
      return '<pre class="thesis-md-code">' + code + '</pre>';
    });
    // 行内代码 `code`
    html = html.replace(/`([^`]+)`/g, '<code class="thesis-md-inline">$1</code>');
    // 标题 ### ## #
    html = html.replace(/^###\s+(.+)$/gm, '<h4 class="thesis-md-h">$1</h4>');
    html = html.replace(/^##\s+(.+)$/gm, '<h3 class="thesis-md-h">$1</h3>');
    html = html.replace(/^#\s+(.+)$/gm, '<h2 class="thesis-md-h">$1</h2>');
    // 粗体 **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // 斜体 *text*
    html = html.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');
    // 无序列表项
    const lines = html.split('\n');
    let out = [];
    let inList = false;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const listMatch = line.match(/^\s*[-*]\s+(.+)$/);
      if (listMatch) {
        if (!inList) { out.push('<ul class="thesis-md-list">'); inList = true; }
        out.push('<li>' + listMatch[1] + '</li>');
      } else {
        if (inList) { out.push('</ul>'); inList = false; }
        out.push(line);
      }
    }
    if (inList) out.push('</ul>');
    html = out.join('\n');
    // 段落：连续非空非标签行包裹 <p>
    html = html.split(/\n{2,}/).map(function (block) {
      const trimmed = block.trim();
      if (!trimmed) return '';
      if (/^<(h\d|ul|ol|pre|blockquote|p)/.test(trimmed)) return trimmed;
      return '<p class="thesis-md-p">' + trimmed.replace(/\n/g, '<br>') + '</p>';
    }).join('\n');
    return html;
  }

  // 记录时间线动作
  function logTimeline(action, detail) {
    state.timeline.unshift({
      action: action,
      time: new Date().toISOString(),
      detail: detail || '',
    });
    if (state.timeline.length > 12) state.timeline.length = 12;
  }

  // 计算进度统计
  function computeStats() {
    const total = state.chapters.length;
    let completed = 0, inProgress = 0, notStarted = 0, totalWords = 0;
    let scores = [];
    state.chapters.forEach(function (c) {
      const wc = c.word_count || countWords(c.content);
      totalWords += wc;
      if (c.status === 'final') completed++;
      else if (c.status === 'draft' || c.status === 'revised') inProgress++;
      else notStarted++;
      if (typeof c.plagiarism_score === 'number') scores.push(c.plagiarism_score);
    });
    const avgScore = scores.length
      ? Math.round(scores.reduce(function (a, b) { return a + b; }, 0) / scores.length)
      : null;
    return { total: total, completed: completed, inProgress: inProgress, notStarted: notStarted, totalWords: totalWords, avgScore: avgScore };
  }

  window.Pages = window.Pages || {};
  window.Pages.thesis = {
    /** 渲染页面骨架 */
    render() {
      return (
        '<header class="page-header">' +
          '<div class="page-header__eyebrow">ThesisMiner · Thesis</div>' +
          '<h1 class="page-header__title">论文撰写</h1>' +
          '<p class="page-header__desc">从大纲生成到章节撰写、查重降重，再到答辩准备的一站式论文工作台。</p>' +
        '</header>' +
        '<div class="page-body">' +
          // 进度仪表盘
          '<div id="thesis-dashboard"></div>' +
          // 会话选择
          '<div class="form-section" id="thesis-session-section" style="margin-bottom:var(--space-lg);">' +
            '<div class="form-section__title">会话选择</div>' +
            '<div id="thesis-session-body">' +
              '<div class="empty-state">' +
                '<div class="spinner spinner--lg"></div>' +
                '<div class="empty-state__title mt-md">正在加载会话…</div>' +
              '</div>' +
            '</div>' +
          '</div>' +
          // 论文工作区（选中会话后显示）
          '<div id="thesis-workspace" class="hidden"></div>' +
        '</div>'
      );
    },

    /** app.js 调用入口 */
    async init() {
      const container = document.getElementById('app-content');
      if (container) await this.mount(container);
    },

    /** 挂载：加载数据 */
    async mount(container) {
      this.renderDashboard();
      await this.loadSessions();
    },

    /* ----------------------------------------------------------------------
       进度仪表盘（SubTask 13.4）
       ---------------------------------------------------------------------- */
    renderDashboard() {
      const el = document.getElementById('thesis-dashboard');
      if (!el) return;
      const stats = computeStats();
      const hasData = stats.total > 0;
      const completionPct = stats.total ? Math.round((stats.completed / stats.total) * 100) : 0;
      const lvl = stats.avgScore !== null ? plagiarismLevel(stats.avgScore) : null;

      let cards = '' +
        '<div class="thesis-stat-card">' +
          '<div class="thesis-stat-card__icon" style="color:var(--accent-primary);"><i data-lucide="book-open"></i></div>' +
          '<div class="thesis-stat-card__value">' + stats.total + '</div>' +
          '<div class="thesis-stat-card__label">章节总数</div>' +
        '</div>' +
        '<div class="thesis-stat-card">' +
          '<div class="thesis-stat-card__icon" style="color:var(--success);"><i data-lucide="check-circle-2"></i></div>' +
          '<div class="thesis-stat-card__value">' + stats.completed + '</div>' +
          '<div class="thesis-stat-card__label">已完成</div>' +
        '</div>' +
        '<div class="thesis-stat-card">' +
          '<div class="thesis-stat-card__icon" style="color:var(--warning);"><i data-lucide="edit-3"></i></div>' +
          '<div class="thesis-stat-card__value">' + stats.inProgress + '</div>' +
          '<div class="thesis-stat-card__label">进行中</div>' +
        '</div>' +
        '<div class="thesis-stat-card">' +
          '<div class="thesis-stat-card__icon" style="color:var(--text-muted);"><i data-lucide="circle-dashed"></i></div>' +
          '<div class="thesis-stat-card__value">' + stats.notStarted + '</div>' +
          '<div class="thesis-stat-card__label">待撰写</div>' +
        '</div>' +
        '<div class="thesis-stat-card">' +
          '<div class="thesis-stat-card__icon" style="color:var(--info);"><i data-lucide="type"></i></div>' +
          '<div class="thesis-stat-card__value">' + stats.totalWords.toLocaleString() + '</div>' +
          '<div class="thesis-stat-card__label">总字数</div>' +
        '</div>' +
        '<div class="thesis-stat-card">' +
          '<div class="thesis-stat-card__icon" style="color:' + (lvl ? lvl.color : 'var(--text-muted)') + ';"><i data-lucide="shield-check"></i></div>' +
          '<div class="thesis-stat-card__value">' + (stats.avgScore !== null ? stats.avgScore + '%' : '—') + '</div>' +
          '<div class="thesis-stat-card__label">平均查重</div>' +
        '</div>';

      let timelineHtml = '';
      if (state.timeline.length > 0) {
        timelineHtml = '<div class="thesis-timeline">' +
          '<div class="thesis-timeline__title"><i data-lucide="activity" style="width:13px;height:13px;"></i> 最近动态</div>' +
          state.timeline.slice(0, 6).map(function (t) {
            return '<div class="thesis-timeline__item">' +
              '<span class="thesis-timeline__dot"></span>' +
              '<div class="thesis-timeline__content">' +
                '<div class="thesis-timeline__action">' + escapeHtml(t.action) + '</div>' +
                (t.detail ? '<div class="thesis-timeline__detail">' + escapeHtml(t.detail) + '</div>' : '') +
                '<div class="thesis-timeline__time">' + escapeHtml(formatDate(t.time)) + '</div>' +
              '</div>' +
            '</div>';
          }).join('') +
        '</div>';
      }

      el.innerHTML = '' +
        '<div class="thesis-dashboard">' +
          '<div class="thesis-dashboard__cards">' + cards + '</div>' +
          '<div class="thesis-dashboard__progress">' +
            '<div class="thesis-progress-head">' +
              '<span class="text-sm text-secondary">整体完成度</span>' +
              '<span class="text-sm font-medium" style="color:var(--accent-primary);">' + completionPct + '%</span>' +
            '</div>' +
            '<div class="thesis-progress-bar">' +
              '<div class="thesis-progress-bar__fill" style="width:' + completionPct + '%;"></div>' +
            '</div>' +
            (hasData ? '<div class="text-xs text-muted mt-sm">已完成 ' + stats.completed + ' / ' + stats.total + ' 章</div>' : '') +
          '</div>' +
          timelineHtml +
        '</div>';
      refreshIcons(el);
    },

    /* ----------------------------------------------------------------------
       会话选择（Section 1）
       ---------------------------------------------------------------------- */
    async loadSessions() {
      const body = document.getElementById('thesis-session-body');
      if (!body) return;
      state.loadingSessions = true;
      try {
        const data = await API.getSessions(100, 0);
        state.sessions = (data && data.sessions) || [];
        this.renderSessionSelector();
      } catch (err) {
        body.innerHTML = '' +
          '<div class="empty-state">' +
            '<div class="empty-state__icon text-danger" data-lucide="alert-triangle"></div>' +
            '<div class="empty-state__title">会话加载失败</div>' +
            '<p class="empty-state__desc">' + escapeHtml(err.message || '未知错误') + '</p>' +
            '<button class="btn btn-secondary btn-sm mt-sm" id="thesis-retry-sessions"><i data-lucide="refresh-cw"></i><span>重试</span></button>' +
          '</div>';
        refreshIcons(body);
        const retry = body.querySelector('#thesis-retry-sessions');
        if (retry) retry.addEventListener('click', () => this.loadSessions());
      } finally {
        state.loadingSessions = false;
      }
    },

    renderSessionSelector() {
      const body = document.getElementById('thesis-session-body');
      if (!body) return;
      if (state.sessions.length === 0) {
        body.innerHTML = '' +
          '<div class="empty-state">' +
            '<div class="empty-state__icon" data-lucide="inbox"></div>' +
            '<div class="empty-state__title">暂无会话</div>' +
            '<p class="empty-state__desc">请先前往「论题生成」创建会话，再回来撰写论文。</p>' +
            '<button class="btn btn-primary btn-sm mt-sm" id="thesis-goto-generate"><i data-lucide="sparkles"></i><span>前往生成</span></button>' +
          '</div>';
        refreshIcons(body);
        const btn = body.querySelector('#thesis-goto-generate');
        if (btn) btn.addEventListener('click', () => navigate('generate'));
        return;
      }

      const options = '<option value="">请选择会话…</option>' +
        state.sessions.map((s) =>
          '<option value="' + escapeHtml(s.id) + '"' + (s.id === state.sessionId ? ' selected' : '') + '>' +
            escapeHtml(s.title || '未命名会话') + '</option>'
        ).join('');

      const degreeBtns = DEGREES.map((d) =>
        '<button class="btn ' + (d.value === state.degree ? 'btn-primary' : 'btn-secondary') + '" data-degree="' + d.value + '" style="flex:1">' + d.label + '</button>'
      ).join('');

      body.innerHTML = '' +
        '<div class="grid grid--2">' +
          '<div class="form-group">' +
            '<label class="form-label" for="thesis-session-select">选择会话</label>' +
            '<select class="form-control" id="thesis-session-select">' + options + '</select>' +
            '<div class="form-hint">选择一个已生成论题的会话作为论文撰写基础。</div>' +
          '</div>' +
          '<div class="form-group">' +
            '<label class="form-label">学位类型</label>' +
            '<div class="flex gap-sm" id="thesis-degree-group">' + degreeBtns + '</div>' +
            '<div class="form-hint">不同学位对应不同的篇幅与规范要求。</div>' +
          '</div>' +
        '</div>' +
        '<div id="thesis-proposal-info"></div>';

      refreshIcons(body);

      const select = body.querySelector('#thesis-session-select');
      if (select) {
        select.addEventListener('change', () => this.onSessionChange(select.value));
      }
      // 学位切换
      body.querySelectorAll('[data-degree]').forEach((btn) => {
        btn.addEventListener('click', () => {
          state.degree = btn.dataset.degree;
          body.querySelectorAll('[data-degree]').forEach((b) => {
            const active = b.dataset.degree === state.degree;
            b.classList.toggle('btn-primary', active);
            b.classList.toggle('btn-secondary', !active);
          });
        });
      });
    },

    // 会话切换：加载会话详情与论题信息
    async onSessionChange(sessionId) {
      state.sessionId = sessionId;
      const infoEl = document.getElementById('thesis-proposal-info');
      const wsEl = document.getElementById('thesis-workspace');
      if (!sessionId) {
        state.session = null;
        state.proposal = null;
        if (infoEl) infoEl.innerHTML = '';
        if (wsEl) wsEl.classList.add('hidden');
        return;
      }

      // 加载会话详情与论题
      if (infoEl) {
        infoEl.innerHTML = '<div class="empty-state" style="padding:var(--space-md);"><div class="spinner spinner--lg"></div><div class="empty-state__title mt-md">加载会话信息…</div></div>';
      }
      try {
        const [session, proposalsData] = await Promise.all([
          API.getSession(sessionId),
          API.getProposals(5, 0, sessionId),
        ]);
        state.session = session;
        const proposals = (proposalsData && proposalsData.proposals) || [];
        state.proposal = proposals[0] || null;
        this.renderProposalInfo();
        // 加载已有章节
        await this.loadChapters();
        this.renderWorkspace();
      } catch (err) {
        if (infoEl) {
          infoEl.innerHTML = '' +
            '<div class="card card--accent" style="border-left-color:var(--danger)">' +
              '<div class="card__body"><p class="text-danger text-sm">' + escapeHtml(err.message || '加载失败') + '</p></div>' +
            '</div>';
        }
        showToast('加载会话信息失败：' + (err.message || err), 'error');
      }
    },

    // 渲染论题/开题报告信息
    renderProposalInfo() {
      const el = document.getElementById('thesis-proposal-info');
      if (!el) return;
      if (!state.proposal) {
        el.innerHTML = '' +
          '<div class="card card--accent" style="border-left-color:var(--warning)">' +
            '<div class="card__body">' +
              '<div class="flex items-start gap-sm">' +
                '<i data-lucide="alert-triangle" style="width:18px;height:18px;color:var(--warning);flex-shrink:0;margin-top:2px"></i>' +
                '<div>' +
                  '<p class="text-sm font-medium" style="color:var(--text-primary);">该会话暂无论题</p>' +
                  '<p class="text-xs text-secondary mt-xs">请先在「论题生成」中为该会话生成论题，再进行论文撰写。</p>' +
                '</div>' +
              '</div>' +
            '</div>' +
          '</div>';
        refreshIcons(el);
        return;
      }
      const p = state.proposal;
      const score = typeof p.confidence_score === 'number' ? Math.round(p.confidence_score * 100) : null;
      el.innerHTML = '' +
        '<div class="card card--accent">' +
          '<div class="card__body">' +
            '<div class="text-xs text-muted mb-xs">当前论题</div>' +
            '<div class="text-display" style="font-size:1.05rem;color:var(--text-primary);line-height:1.4;">' + escapeHtml(p.title || '未命名论题') + '</div>' +
            '<div class="flex items-center gap-sm flex-wrap mt-sm">' +
              (score !== null ? '<span class="badge badge--accent">置信度 ' + score + '%</span>' : '') +
              (p.auto_rewritten ? '<span class="badge badge--default">已改写</span>' : '') +
              '<span class="badge badge--info">' + escapeHtml(this.degreeLabel()) + '</span>' +
            '</div>' +
            (p.problem_awareness ? '<p class="text-sm text-secondary mt-sm">' + escapeHtml(truncate(p.problem_awareness, 160)) + '</p>' : '') +
          '</div>' +
        '</div>';
      refreshIcons(el);
    },

    degreeLabel() {
      const d = DEGREES.find((x) => x.value === state.degree);
      return d ? d.label : '硕士';
    },

    /* ----------------------------------------------------------------------
       加载已有章节
       ---------------------------------------------------------------------- */
    async loadChapters() {
      if (!state.sessionId) return;
      try {
        const data = await API.getChapters(state.sessionId);
        const chapters = (data && (data.chapters || data.data)) || [];
        state.chapters = chapters.map((c, idx) => this.normalizeChapter(c, idx));
        // 若后端返回了大纲，同步到 state.outline
        if (data && data.outline && !state.outline) {
          state.outline = data.outline;
          state.outlineLocked = true;
        }
      } catch (_) {
        // 端点可能尚未有数据，静默处理
        state.chapters = [];
      }
    },

    // 规范化章节字段（兼容多种后端返回结构）
    normalizeChapter(c, idx) {
      return {
        id: c.id || ('ch-' + (idx + 1)),
        number: c.number || (idx + 1),
        title: c.title || ('第' + cnNumber(idx + 1) + '章'),
        description: c.description || c.summary || '',
        content: c.content || c.text || '',
        word_count: c.word_count || countWords(c.content || c.text),
        status: c.status || (c.content ? 'draft' : 'pending'),
        plagiarism_score: typeof c.plagiarism_score === 'number' ? c.plagiarism_score : (typeof c.similarity_score === 'number' ? c.similarity_score : null),
      };
    },

    /* ----------------------------------------------------------------------
       论文工作区（选中会话后渲染）
       ---------------------------------------------------------------------- */
    renderWorkspace() {
      const ws = document.getElementById('thesis-workspace');
      if (!ws) return;
      if (!state.sessionId) {
        ws.classList.add('hidden');
        return;
      }
      ws.classList.remove('hidden');

      ws.innerHTML = '' +
        // 大纲生成区
        '<div class="form-section" id="thesis-outline-section" style="margin-bottom:var(--space-lg);">' +
          '<div class="form-section__title">大纲生成</div>' +
          '<div id="thesis-outline-body">' + this.renderOutlineBody() + '</div>' +
        '</div>' +
        // 章节撰写区（分栏）
        '<div class="form-section" id="thesis-chapter-section" style="margin-bottom:var(--space-lg);">' +
          '<div class="form-section__title">章节撰写</div>' +
          '<div id="thesis-chapter-body">' + this.renderChapterBody() + '</div>' +
        '</div>' +
        // 查重降重区
        '<div class="form-section" id="thesis-plagiarism-section" style="margin-bottom:var(--space-lg);">' +
          '<div class="form-section__title">查重检测与降重</div>' +
          '<div id="thesis-plagiarism-body">' + this.renderPlagiarismBody() + '</div>' +
        '</div>' +
        // 答辩准备区
        '<div class="form-section" id="thesis-defense-section">' +
          '<div class="form-section__title">答辩准备</div>' +
          '<div id="thesis-defense-body">' + this.renderDefenseBody() + '</div>' +
        '</div>';

      refreshIcons(ws);
      this.bindWorkspaceActions();
      this.renderDashboard();
    },

    /* ----------------------------------------------------------------------
       Section 2：大纲生成
       ---------------------------------------------------------------------- */
    renderOutlineBody() {
      if (!state.outline) {
        return '' +
          '<div class="empty-state">' +
            '<div class="empty-state__icon" data-lucide="list-tree"></div>' +
            '<div class="empty-state__title">尚未生成大纲</div>' +
            '<p class="empty-state__desc">点击下方按钮，AI 将基于论题生成论文大纲。</p>' +
            '<button class="btn btn-primary mt-sm" id="thesis-gen-outline"><i data-lucide="sparkles"></i><span>生成大纲</span></button>' +
          '</div>';
      }

      const chapters = (state.outline.chapters || []);
      let listHtml = '';
      chapters.forEach((ch, idx) => {
        const num = ch.number || (idx + 1);
        const editable = !state.outlineLocked;
        listHtml += '' +
          '<div class="thesis-outline-item">' +
            '<div class="thesis-outline-item__num">第' + cnNumber(num) + '章</div>' +
            '<div class="thesis-outline-item__body">' +
              (editable
                ? '<input class="form-control thesis-outline-item__title" data-outline-idx="' + idx + '" data-field="title" value="' + escapeHtml(ch.title || '') + '" placeholder="章节标题" />'
                : '<div class="thesis-outline-item__title thesis-outline-item__title--locked">' + escapeHtml(ch.title || '') + '</div>'
              ) +
              (editable
                ? '<textarea class="form-control thesis-outline-item__desc" data-outline-idx="' + idx + '" data-field="description" rows="2" placeholder="章节描述">' + escapeHtml(ch.description || '') + '</textarea>'
                : (ch.description ? '<div class="thesis-outline-item__desc">' + escapeHtml(ch.description) + '</div>' : '')
              ) +
            '</div>' +
          '</div>';
      });

      return '' +
        '<div class="thesis-outline">' + listHtml + '</div>' +
        '<div class="flex gap-sm mt-md">' +
          (state.outlineLocked
            ? '<span class="badge badge--success"><span class="badge__dot"></span>大纲已确认</span>' +
              '<button class="btn btn-secondary btn-sm" id="thesis-edit-outline"><i data-lucide="edit-3"></i><span>解锁编辑</span></button>'
            : '<button class="btn btn-primary" id="thesis-confirm-outline"><i data-lucide="check-circle-2"></i><span>确认大纲</span></button>' +
              '<button class="btn btn-secondary" id="thesis-regen-outline"><i data-lucide="refresh-cw"></i><span>重新生成</span></button>'
          ) +
        '</div>';
    },

    // 绑定大纲编辑事件
    bindOutlineActions() {
      const body = document.getElementById('thesis-outline-body');
      if (!body) return;
      const genBtn = body.querySelector('#thesis-gen-outline');
      if (genBtn) genBtn.addEventListener('click', () => this.handleGenerateOutline());
      const regenBtn = body.querySelector('#thesis-regen-outline');
      if (regenBtn) regenBtn.addEventListener('click', () => this.handleGenerateOutline());
      const confirmBtn = body.querySelector('#thesis-confirm-outline');
      if (confirmBtn) confirmBtn.addEventListener('click', () => this.handleConfirmOutline());
      const editBtn = body.querySelector('#thesis-edit-outline');
      if (editBtn) editBtn.addEventListener('click', () => { state.outlineLocked = false; this.rerenderOutline(); });

      // 大纲编辑输入
      body.querySelectorAll('[data-outline-idx]').forEach((input) => {
        input.addEventListener('input', () => {
          const idx = parseInt(input.dataset.outlineIdx, 10);
          const field = input.dataset.field;
          if (state.outline && state.outline.chapters && state.outline.chapters[idx]) {
            state.outline.chapters[idx][field] = input.value;
          }
        });
      });
    },

    rerenderOutline() {
      const body = document.getElementById('thesis-outline-body');
      if (body) {
        body.innerHTML = this.renderOutlineBody();
        refreshIcons(body);
        this.bindOutlineActions();
      }
    },

    async handleGenerateOutline() {
      if (state.loadingOutline || !state.sessionId) return;
      if (!state.proposal) {
        showToast('该会话暂无论题，无法生成大纲', 'warning');
        return;
      }
      state.loadingOutline = true;
      const body = document.getElementById('thesis-outline-body');
      if (body) {
        body.innerHTML = '' +
          '<div class="empty-state">' +
            '<div class="spinner spinner--lg"></div>' +
            '<div class="empty-state__title mt-md">正在生成大纲…</div>' +
            '<p class="empty-state__desc">AI 正在规划论文章节结构，请稍候。</p>' +
          '</div>';
        refreshIcons(body);
      }
      try {
        const res = await API.generateOutline(state.sessionId, {
          degree: state.degree,
          title: state.proposal.title || '',
        });
        // 兼容多种返回结构
        const outline = (res && (res.outline || res.data)) || res || {};
        const chapters = outline.chapters || outline.chapter_list || [];
        state.outline = {
          title: outline.title || (state.proposal && state.proposal.title) || '',
          chapters: chapters.map((c, idx) => ({
            id: c.id || ('ch-' + (idx + 1)),
            number: c.number || (idx + 1),
            title: c.title || c.name || ('第' + cnNumber(idx + 1) + '章'),
            description: c.description || c.summary || c.content || '',
          })),
        };
        state.outlineLocked = false;
        this.rerenderOutline();
        logTimeline('生成大纲', state.outline.chapters.length + ' 个章节');
        showToast('大纲已生成，可编辑后确认', 'success');
      } catch (err) {
        if (body) {
          body.innerHTML = '' +
            '<div class="card card--accent" style="border-left-color:var(--danger)">' +
              '<div class="card__body"><p class="text-danger text-sm">' + escapeHtml(err.message || '生成失败') + '</p></div>' +
            '</div>' +
            '<button class="btn btn-primary btn-sm mt-sm" id="thesis-gen-outline"><i data-lucide="refresh-cw"></i><span>重试生成</span></button>';
          refreshIcons(body);
          this.bindOutlineActions();
        }
        showToast('大纲生成失败：' + (err.message || err), 'error');
      } finally {
        state.loadingOutline = false;
      }
    },

    handleConfirmOutline() {
      if (!state.outline || !state.outline.chapters || state.outline.chapters.length === 0) {
        showToast('请先生成大纲', 'warning');
        return;
      }
      state.outlineLocked = true;
      // 同步大纲到章节列表（保留已有内容）
      const existing = {};
      state.chapters.forEach((c) => { existing[c.id] = c; });
      state.chapters = state.outline.chapters.map((ch, idx) => {
        const prev = existing[ch.id];
        return {
          id: ch.id,
          number: ch.number || (idx + 1),
          title: ch.title,
          description: ch.description || '',
          content: prev ? prev.content : '',
          word_count: prev ? prev.word_count : 0,
          status: prev ? prev.status : 'pending',
          plagiarism_score: prev ? prev.plagiarism_score : null,
        };
      });
      if (state.chapters.length > 0 && !state.activeChapterId) {
        state.activeChapterId = state.chapters[0].id;
      }
      this.rerenderOutline();
      this.rerenderChapters();
      this.renderDashboard();
      logTimeline('确认大纲', state.chapters.length + ' 个章节已锁定');
      showToast('大纲已确认，可开始撰写章节', 'success');
    },

    /* ----------------------------------------------------------------------
       Section 3：章节撰写（分栏布局，SubTask 13.2）
       ---------------------------------------------------------------------- */
    renderChapterBody() {
      if (!state.outlineLocked && state.chapters.length === 0) {
        return '' +
          '<div class="empty-state">' +
            '<div class="empty-state__icon" data-lucide="lock"></div>' +
            '<div class="empty-state__title">请先确认大纲</div>' +
            '<p class="empty-state__desc">确认大纲后即可开始逐章撰写。</p>' +
          '</div>';
      }
      if (state.chapters.length === 0) {
        return '' +
          '<div class="empty-state">' +
            '<div class="empty-state__icon" data-lucide="inbox"></div>' +
            '<div class="empty-state__title">暂无章节</div>' +
            '<p class="empty-state__desc">请先生成并确认大纲。</p>' +
          '</div>';
      }

      // 章节进度条
      const stats = computeStats();
      const completionPct = stats.total ? Math.round((stats.completed / stats.total) * 100) : 0;
      const progressHtml = '' +
        '<div class="thesis-chapter-progress">' +
          '<div class="thesis-progress-head">' +
            '<span class="text-sm text-secondary">撰写进度</span>' +
            '<span class="text-sm font-medium" style="color:var(--accent-primary);">' + stats.completed + ' / ' + stats.total + ' 章 · ' + completionPct + '%</span>' +
          '</div>' +
          '<div class="thesis-progress-bar"><div class="thesis-progress-bar__fill" style="width:' + completionPct + '%;"></div></div>' +
        '</div>';

      // 左侧章节列表
      const listHtml = state.chapters.map((c) => {
        const isActive = c.id === state.activeChapterId;
        const wc = c.word_count || countWords(c.content);
        return '' +
          '<div class="thesis-chapter-item' + (isActive ? ' thesis-chapter-item--active' : '') + '" data-chapter-id="' + escapeHtml(c.id) + '">' +
            '<div class="thesis-chapter-item__head">' +
              '<span class="thesis-chapter-item__num">第' + cnNumber(c.number) + '章</span>' +
              statusBadge(c.status) +
            '</div>' +
            '<div class="thesis-chapter-item__title">' + escapeHtml(c.title) + '</div>' +
            '<div class="thesis-chapter-item__meta">' +
              '<span><i data-lucide="type" style="width:11px;height:11px;"></i> ' + wc + ' 字</span>' +
              (c.plagiarism_score !== null ? '<span><i data-lucide="shield-check" style="width:11px;height:11px;"></i> ' + c.plagiarism_score + '%</span>' : '') +
            '</div>' +
          '</div>';
      }).join('');

      // 右侧编辑器
      const active = state.chapters.find((c) => c.id === state.activeChapterId) || state.chapters[0];
      const editorHtml = active ? this.renderChapterEditor(active) : this.chapterEditorEmpty();

      return '' +
        progressHtml +
        '<div class="thesis-split">' +
          '<aside class="thesis-split__list">' + listHtml + '</aside>' +
          '<section class="thesis-split__editor" id="thesis-chapter-editor">' + editorHtml + '</section>' +
        '</div>';
    },

    chapterEditorEmpty() {
      return '' +
        '<div class="empty-state">' +
          '<div class="empty-state__icon" data-lucide="file-text"></div>' +
          '<div class="empty-state__title">选择章节</div>' +
          '<p class="empty-state__desc">从左侧选择一个章节开始撰写。</p>' +
        '</div>';
    },

    renderChapterEditor(ch) {
      const hasContent = !!(ch.content && ch.content.trim());
      const wc = ch.word_count || countWords(ch.content);

      // 编辑模式：textarea；查看模式：渲染 markdown
      let contentHtml;
      if (state.editing) {
        contentHtml = '<textarea class="form-control thesis-chapter-textarea" id="thesis-chapter-edit-area" rows="18" placeholder="输入或编辑章节内容（支持 Markdown）…">' + escapeHtml(ch.content || '') + '</textarea>';
      } else if (hasContent) {
        contentHtml = '<div class="thesis-chapter-content thesis-md">' + renderMarkdown(ch.content) + '</div>';
      } else {
        contentHtml = '' +
          '<div class="empty-state" style="padding:var(--space-lg);">' +
            '<div class="empty-state__icon" data-lucide="pen-line"></div>' +
            '<div class="empty-state__title">本章尚未撰写</div>' +
            '<p class="empty-state__desc">点击「撰写本章」由 AI 生成初稿，或切换编辑模式手动输入。</p>' +
          '</div>';
      }

      // 修订反馈区
      const reviseHtml = '' +
        '<div class="thesis-revise" id="thesis-revise-area" style="display:none;">' +
          '<div class="form-group" style="margin-bottom:var(--space-sm);">' +
            '<label class="form-label">修订反馈</label>' +
            '<textarea class="form-control" id="thesis-revise-feedback" rows="3" placeholder="输入修订意见，例如：补充文献支撑、调整论证逻辑、增加案例…"></textarea>' +
          '</div>' +
          '<div class="flex gap-sm">' +
            '<button class="btn btn-primary btn-sm" id="thesis-submit-revise"><i data-lucide="send"></i><span>提交修订</span></button>' +
            '<button class="btn btn-ghost btn-sm" id="thesis-cancel-revise">取消</button>' +
          '</div>' +
        '</div>';

      return '' +
        '<div class="thesis-editor">' +
          '<div class="thesis-editor__head">' +
            '<div>' +
              '<div class="thesis-editor__num">第' + cnNumber(ch.number) + '章</div>' +
              '<div class="thesis-editor__title">' + escapeHtml(ch.title) + '</div>' +
            '</div>' +
            '<div class="flex items-center gap-sm flex-wrap">' +
              statusBadge(ch.status) +
              '<span class="badge badge--default"><i data-lucide="type" style="width:11px;height:11px;"></i> ' + wc + ' 字</span>' +
            '</div>' +
          '</div>' +
          (ch.description ? '<p class="text-sm text-secondary thesis-editor__desc">' + escapeHtml(ch.description) + '</p>' : '') +
          '<div class="thesis-editor__body">' + contentHtml + '</div>' +
          reviseHtml +
          '<div class="thesis-editor__actions">' +
            (state.editing
              ? '<button class="btn btn-primary btn-sm" id="thesis-save-chapter"><i data-lucide="save"></i><span>保存</span></button>' +
                '<button class="btn btn-secondary btn-sm" id="thesis-cancel-edit"><i data-lucide="x"></i><span>取消</span></button>'
              : '<button class="btn btn-primary btn-sm" id="thesis-write-chapter"><i data-lucide="sparkles"></i><span>' + (hasContent ? '重新撰写' : '撰写本章') + '</span></button>' +
                (hasContent ? '<button class="btn btn-secondary btn-sm" id="thesis-edit-chapter"><i data-lucide="edit-3"></i><span>编辑</span></button>' : '') +
                (hasContent ? '<button class="btn btn-secondary btn-sm" id="thesis-revise-chapter"><i data-lucide="refresh-cw"></i><span>修订本章</span></button>' : '') +
                (hasContent ? '<button class="btn btn-ghost btn-sm" id="thesis-check-chapter"><i data-lucide="shield-check"></i><span>查重</span></button>' : '')
            ) +
          '</div>' +
        '</div>';
    },

    rerenderChapters() {
      const body = document.getElementById('thesis-chapter-body');
      if (body) {
        body.innerHTML = this.renderChapterBody();
        refreshIcons(body);
        this.bindChapterActions();
      }
    },

    // 仅刷新右侧编辑器
    rerenderChapterEditor() {
      const el = document.getElementById('thesis-chapter-editor');
      if (!el) return;
      const active = state.chapters.find((c) => c.id === state.activeChapterId) || state.chapters[0];
      el.innerHTML = active ? this.renderChapterEditor(active) : this.chapterEditorEmpty();
      refreshIcons(el);
      this.bindChapterActions();
    },

    bindChapterActions() {
      const body = document.getElementById('thesis-chapter-body');
      if (!body) return;
      // 选择章节
      body.querySelectorAll('[data-chapter-id]').forEach((el) => {
        el.addEventListener('click', () => {
          state.activeChapterId = el.dataset.chapterId;
          state.editing = false;
          this.rerenderChapters();
        });
      });
      // 编辑器内动作
      const editor = body.querySelector('#thesis-chapter-editor');
      if (editor) {
        const writeBtn = editor.querySelector('#thesis-write-chapter');
        if (writeBtn) writeBtn.addEventListener('click', () => this.handleWriteChapter());
        const editBtn = editor.querySelector('#thesis-edit-chapter');
        if (editBtn) editBtn.addEventListener('click', () => { state.editing = true; this.rerenderChapterEditor(); });
        const cancelEdit = editor.querySelector('#thesis-cancel-edit');
        if (cancelEdit) cancelEdit.addEventListener('click', () => { state.editing = false; this.rerenderChapterEditor(); });
        const saveBtn = editor.querySelector('#thesis-save-chapter');
        if (saveBtn) saveBtn.addEventListener('click', () => this.handleSaveChapter());
        const reviseBtn = editor.querySelector('#thesis-revise-chapter');
        if (reviseBtn) reviseBtn.addEventListener('click', () => this.toggleReviseArea(true));
        const cancelRevise = editor.querySelector('#thesis-cancel-revise');
        if (cancelRevise) cancelRevise.addEventListener('click', () => this.toggleReviseArea(false));
        const submitRevise = editor.querySelector('#thesis-submit-revise');
        if (submitRevise) submitRevise.addEventListener('click', () => this.handleReviseChapter());
        const checkBtn = editor.querySelector('#thesis-check-chapter');
        if (checkBtn) checkBtn.addEventListener('click', () => this.handleCheckPlagiarism());
      }
    },

    toggleReviseArea(show) {
      const area = document.getElementById('thesis-revise-area');
      if (area) area.style.display = show ? 'block' : 'none';
      if (show) {
        const ta = document.getElementById('thesis-revise-feedback');
        if (ta) ta.focus();
      }
    },

    // 撰写章节
    async handleWriteChapter() {
      if (state.loadingChapter || !state.sessionId) return;
      const ch = state.chapters.find((c) => c.id === state.activeChapterId);
      if (!ch) return;
      state.loadingChapter = true;
      const editor = document.getElementById('thesis-chapter-editor');
      if (editor) {
        editor.innerHTML = '' +
          '<div class="empty-state" style="padding:var(--space-xl);">' +
            '<div class="spinner spinner--lg"></div>' +
            '<div class="empty-state__title mt-md">正在撰写第' + cnNumber(ch.number) + '章…</div>' +
            '<p class="empty-state__desc">AI 正在生成章节内容，请稍候。</p>' +
          '</div>';
        refreshIcons(editor);
      }
      try {
        const res = await API.generateChapter(state.sessionId, {
          chapter_id: ch.id,
          number: ch.number,
          title: ch.title,
          description: ch.description || '',
          degree: state.degree,
        });
        const content = (res && (res.content || res.text || (res.chapter && res.chapter.content))) || '';
        const wordCount = (res && (res.word_count || (res.chapter && res.chapter.word_count))) || countWords(content);
        ch.content = content;
        ch.word_count = wordCount;
        ch.status = 'draft';
        state.editing = false;
        this.rerenderChapters();
        this.renderDashboard();
        logTimeline('撰写章节', '第' + cnNumber(ch.number) + '章 · ' + wordCount + ' 字');
        showToast('第' + cnNumber(ch.number) + '章已生成', 'success');
      } catch (err) {
        showToast('章节撰写失败：' + (err.message || err), 'error');
        this.rerenderChapterEditor();
      } finally {
        state.loadingChapter = false;
      }
    },

    // 保存章节（编辑模式）
    async handleSaveChapter() {
      const ch = state.chapters.find((c) => c.id === state.activeChapterId);
      if (!ch) return;
      const ta = document.getElementById('thesis-chapter-edit-area');
      if (ta) ch.content = ta.value;
      ch.word_count = countWords(ch.content);
      if (ch.status === 'pending') ch.status = 'draft';
      const btn = document.getElementById('thesis-save-chapter');
      if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span><span>保存中…</span>'; }
      try {
        await API.updateChapter(state.sessionId, ch.id, {
          title: ch.title,
          content: ch.content,
          status: ch.status,
        });
        state.editing = false;
        this.rerenderChapters();
        this.renderDashboard();
        logTimeline('保存章节', '第' + cnNumber(ch.number) + '章');
        showToast('章节已保存', 'success');
      } catch (err) {
        // 保存失败仍保留本地修改
        state.editing = false;
        this.rerenderChapters();
        showToast('保存到服务端失败，本地修改已保留：' + (err.message || err), 'warning');
      }
    },

    // 修订章节
    async handleReviseChapter() {
      const ch = state.chapters.find((c) => c.id === state.activeChapterId);
      if (!ch) return;
      const feedbackEl = document.getElementById('thesis-revise-feedback');
      const feedback = (feedbackEl && feedbackEl.value.trim()) || '';
      if (!feedback) {
        showToast('请输入修订意见', 'warning');
        if (feedbackEl) feedbackEl.focus();
        return;
      }
      const btn = document.getElementById('thesis-submit-revise');
      if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span><span>修订中…</span>'; }
      try {
        const res = await API.reviseChapter(state.sessionId, {
          chapter_id: ch.id,
          number: ch.number,
          title: ch.title,
          content: ch.content,
          feedback: feedback,
        });
        const content = (res && (res.content || res.text || (res.chapter && res.chapter.content))) || '';
        if (content) {
          ch.content = content;
          ch.word_count = countWords(content);
          ch.status = 'revised';
        }
        this.toggleReviseArea(false);
        this.rerenderChapters();
        this.renderDashboard();
        logTimeline('修订章节', '第' + cnNumber(ch.number) + '章');
        showToast('章节已修订', 'success');
      } catch (err) {
        showToast('修订失败：' + (err.message || err), 'error');
      } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i data-lucide="send"></i><span>提交修订</span>'; refreshIcons(btn); }
      }
    },

    /* ----------------------------------------------------------------------
       Section 4：查重检测与降重（SubTask 13.3）
       ---------------------------------------------------------------------- */
    renderPlagiarismBody() {
      const hasChapters = state.chapters.some((c) => c.content && c.content.trim());
      if (!hasChapters) {
        return '' +
          '<div class="empty-state">' +
            '<div class="empty-state__icon" data-lucide="shield-check"></div>' +
            '<div class="empty-state__title">暂无可查重内容</div>' +
            '<p class="empty-state__desc">请先撰写至少一章内容，再进行查重检测。</p>' +
          '</div>';
      }

      // 章节选择下拉
      const chapterOpts = state.chapters
        .filter((c) => c.content && c.content.trim())
        .map((c) => '<option value="' + escapeHtml(c.id) + '"' + (c.id === state.activeChapterId ? ' selected' : '') + '>第' + cnNumber(c.number) + '章 ' + escapeHtml(c.title) + '</option>')
        .join('');

      let resultHtml = '';
      if (state.plagiarism) {
        resultHtml = this.renderPlagiarismResult();
      } else {
        resultHtml = '' +
          '<div class="empty-state" style="padding:var(--space-lg);">' +
            '<div class="empty-state__icon" data-lucide="search"></div>' +
            '<div class="empty-state__title">尚未检测</div>' +
            '<p class="empty-state__desc">选择章节后点击「查重检测」查看相似度。</p>' +
          '</div>';
      }

      return '' +
        '<div class="thesis-plagiarism">' +
          '<div class="flex items-end gap-sm flex-wrap mb-md">' +
            '<div class="form-group" style="margin-bottom:0;flex:1;min-width:220px;">' +
              '<label class="form-label">检测章节</label>' +
              '<select class="form-control" id="thesis-plagiarism-chapter">' + chapterOpts + '</select>' +
            '</div>' +
            '<button class="btn btn-primary" id="thesis-run-plagiarism"><i data-lucide="shield-check"></i><span>查重检测</span></button>' +
          '</div>' +
          '<div id="thesis-plagiarism-result">' + resultHtml + '</div>' +
        '</div>';
    },

    renderPlagiarismResult() {
      const p = state.plagiarism || {};
      const score = typeof p.score === 'number' ? p.score : (typeof p.similarity_score === 'number' ? p.similarity_score : 0);
      const lvl = plagiarismLevel(score);
      const highRisk = p.high_risk_sections || p.risk_sections || [];
      const suggestions = p.suggestions || [];

      // 圆环仪表
      const radius = 52;
      const circ = 2 * Math.PI * radius;
      const offset = circ - (score / 100) * circ;
      const gaugeHtml = '' +
        '<div class="thesis-gauge ' + lvl.cls + '">' +
          '<svg viewBox="0 0 120 120" class="thesis-gauge__svg">' +
            '<circle cx="60" cy="60" r="' + radius + '" class="thesis-gauge__track" />' +
            '<circle cx="60" cy="60" r="' + radius + '" class="thesis-gauge__value" stroke="' + lvl.color + '" stroke-dasharray="' + circ + '" stroke-dashoffset="' + offset + '" />' +
          '</svg>' +
          '<div class="thesis-gauge__center">' +
            '<div class="thesis-gauge__score">' + score + '%</div>' +
            '<div class="thesis-gauge__label">' + lvl.label + '</div>' +
          '</div>' +
        '</div>';

      // 高风险片段
      let riskHtml = '';
      if (highRisk.length > 0) {
        riskHtml = '' +
          '<div class="thesis-risk-list">' +
            '<div class="thesis-risk-list__title"><i data-lucide="alert-triangle" style="width:14px;height:14px;color:var(--danger);"></i> 高风险片段（' + highRisk.length + '）</div>' +
            highRisk.map((r, idx) => {
              const text = typeof r === 'string' ? r : (r.text || r.snippet || r.content || '');
              const rScore = typeof r === 'object' ? (r.score || r.similarity) : null;
              const rSug = typeof r === 'object' ? (r.suggestion || r.advice) : '';
              return '' +
                '<div class="thesis-risk-item">' +
                  '<div class="thesis-risk-item__head">' +
                    '<span class="thesis-risk-item__idx">#' + (idx + 1) + '</span>' +
                    (rScore !== null && rScore !== undefined ? '<span class="badge badge--danger">相似度 ' + rScore + '%</span>' : '') +
                  '</div>' +
                  '<div class="thesis-risk-item__text">' + escapeHtml(truncate(text, 220)) + '</div>' +
                  (rSug ? '<div class="thesis-risk-item__sug"><i data-lucide="lightbulb" style="width:12px;height:12px;color:var(--warning);"></i> ' + escapeHtml(rSug) + '</div>' : '') +
                '</div>';
            }).join('') +
          '</div>';
      }

      // 建议
      let sugHtml = '';
      if (suggestions.length > 0) {
        sugHtml = '' +
          '<div class="thesis-risk-list">' +
            '<div class="thesis-risk-list__title"><i data-lucide="lightbulb" style="width:14px;height:14px;color:var(--warning);"></i> 降重建议</div>' +
            suggestions.map((s) => {
              const text = typeof s === 'string' ? s : (s.text || s.message || s.description || '');
              return '<div class="thesis-suggestion"><i data-lucide="chevron-right" style="width:12px;height:12px;"></i> ' + escapeHtml(text) + '</div>';
            }).join('') +
          '</div>';
      }

      // 降重结果
      let reducedHtml = '';
      if (state.reducedContent) {
        reducedHtml = '' +
          '<div class="thesis-reduced">' +
            '<div class="thesis-reduced__title"><i data-lucide="check-circle-2" style="width:14px;height:14px;color:var(--success);"></i> 降重后内容</div>' +
            '<div class="thesis-reduced__content thesis-md">' + renderMarkdown(state.reducedContent) + '</div>' +
          '</div>';
      }

      return '' +
        '<div class="thesis-plagiarism-result">' +
          '<div class="thesis-plagiarism-head">' +
            gaugeHtml +
            '<div class="thesis-plagiarism-actions">' +
              (score >= 15
                ? '<button class="btn btn-primary" id="thesis-reduce-similarity"><i data-lucide="wand-2"></i><span>一键降重</span></button>'
                : '<div class="badge badge--success"><i data-lucide="check-circle-2" style="width:12px;height:12px;"></i> 相似度在安全范围内</div>'
              ) +
              (state.reducedContent ? '<button class="btn btn-secondary btn-sm" id="thesis-apply-reduced"><i data-lucide="check"></i><span>应用降重内容</span></button>' : '') +
            '</div>' +
          '</div>' +
          riskHtml +
          sugHtml +
          reducedHtml +
        '</div>';
    },

    rerenderPlagiarism() {
      const body = document.getElementById('thesis-plagiarism-body');
      if (body) {
        body.innerHTML = this.renderPlagiarismBody();
        refreshIcons(body);
        this.bindPlagiarismActions();
      }
    },

    bindPlagiarismActions() {
      const body = document.getElementById('thesis-plagiarism-body');
      if (!body) return;
      const select = body.querySelector('#thesis-plagiarism-chapter');
      if (select) {
        select.addEventListener('change', () => {
          state.activeChapterId = select.value;
          state.plagiarism = null;
          state.reducedContent = '';
          this.rerenderPlagiarism();
        });
      }
      const runBtn = body.querySelector('#thesis-run-plagiarism');
      if (runBtn) runBtn.addEventListener('click', () => this.handleCheckPlagiarism());
      const reduceBtn = body.querySelector('#thesis-reduce-similarity');
      if (reduceBtn) reduceBtn.addEventListener('click', () => this.handleReduceSimilarity());
      const applyBtn = body.querySelector('#thesis-apply-reduced');
      if (applyBtn) applyBtn.addEventListener('click', () => this.handleApplyReduced());
    },

    async handleCheckPlagiarism() {
      if (state.loadingPlagiarism || !state.sessionId) return;
      const ch = state.chapters.find((c) => c.id === state.activeChapterId);
      if (!ch || !ch.content) {
        showToast('请先选择已撰写内容的章节', 'warning');
        return;
      }
      state.loadingPlagiarism = true;
      state.plagiarism = null;
      state.reducedContent = '';
      const resultEl = document.getElementById('thesis-plagiarism-result');
      if (resultEl) {
        resultEl.innerHTML = '' +
          '<div class="empty-state" style="padding:var(--space-lg);">' +
            '<div class="spinner spinner--lg"></div>' +
            '<div class="empty-state__title mt-md">正在检测查重…</div>' +
            '<p class="empty-state__desc">AI 正在比对相似度，请稍候。</p>' +
          '</div>';
        refreshIcons(resultEl);
      }
      try {
        const res = await API.checkPlagiarism(state.sessionId, {
          chapter_id: ch.id,
          number: ch.number,
          title: ch.title,
          content: ch.content,
        });
        state.plagiarism = {
          score: (res && (res.score !== undefined ? res.score : res.similarity_score)) || 0,
          high_risk_sections: (res && (res.high_risk_sections || res.risk_sections)) || [],
          suggestions: (res && res.suggestions) || [],
        };
        ch.plagiarism_score = state.plagiarism.score;
        this.rerenderPlagiarism();
        this.rerenderChapters();
        this.renderDashboard();
        logTimeline('查重检测', '第' + cnNumber(ch.number) + '章 · ' + state.plagiarism.score + '%');
        showToast('查重完成，相似度 ' + state.plagiarism.score + '%', 'success');
      } catch (err) {
        if (resultEl) {
          resultEl.innerHTML = '' +
            '<div class="card card--accent" style="border-left-color:var(--danger)">' +
              '<div class="card__body"><p class="text-danger text-sm">' + escapeHtml(err.message || '检测失败') + '</p></div>' +
            '</div>';
        }
        showToast('查重检测失败：' + (err.message || err), 'error');
      } finally {
        state.loadingPlagiarism = false;
      }
    },

    async handleReduceSimilarity() {
      if (state.loadingPlagiarism || !state.sessionId) return;
      const ch = state.chapters.find((c) => c.id === state.activeChapterId);
      if (!ch) return;
      const btn = document.getElementById('thesis-reduce-similarity');
      if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span><span>降重中…</span>'; }
      try {
        const res = await API.reduceSimilarity(state.sessionId, {
          chapter_id: ch.id,
          number: ch.number,
          title: ch.title,
          content: ch.content,
          feedback: state.plagiarism && state.plagiarism.suggestions ? state.plagiarism.suggestions.join('；') : '',
        });
        const newContent = (res && (res.content || res.text || res.reduced_content)) || '';
        const newScore = (res && (res.score !== undefined ? res.score : res.similarity_score));
        state.reducedContent = newContent;
        if (typeof newScore === 'number' && state.plagiarism) {
          state.plagiarism.score = newScore;
        }
        this.rerenderPlagiarism();
        logTimeline('降重改写', '第' + cnNumber(ch.number) + '章');
        showToast('降重完成，可点击「应用降重内容」更新章节', 'success');
      } catch (err) {
        showToast('降重失败：' + (err.message || err), 'error');
      } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i data-lucide="wand-2"></i><span>一键降重</span>'; refreshIcons(btn); }
      }
    },

    handleApplyReduced() {
      const ch = state.chapters.find((c) => c.id === state.activeChapterId);
      if (!ch || !state.reducedContent) return;
      ch.content = state.reducedContent;
      ch.word_count = countWords(ch.content);
      if (ch.status === 'draft') ch.status = 'revised';
      state.reducedContent = '';
      // 保存到后端
      API.updateChapter(state.sessionId, ch.id, {
        title: ch.title,
        content: ch.content,
        status: ch.status,
      }).catch(() => {});
      this.rerenderChapters();
      this.rerenderPlagiarism();
      this.renderDashboard();
      logTimeline('应用降重', '第' + cnNumber(ch.number) + '章');
      showToast('降重内容已应用到章节', 'success');
    },

    /* ----------------------------------------------------------------------
       Section 5：答辩准备（SubTask 13.5）
       ---------------------------------------------------------------------- */
    renderDefenseBody() {
      const hasContent = state.chapters.some((c) => c.content && c.content.trim());
      if (!hasContent && !state.outlineLocked) {
        return '' +
          '<div class="empty-state">' +
            '<div class="empty-state__icon" data-lucide="presentation"></div>' +
            '<div class="empty-state__title">先完成论文撰写</div>' +
            '<p class="empty-state__desc">撰写并确认章节内容后，即可进入答辩准备。</p>' +
          '</div>';
      }

      // PPT 大纲
      let pptHtml = '';
      if (state.defense.ppt) {
        const slides = state.defense.ppt.slides || state.defense.ppt.outline || [];
        pptHtml = '' +
          '<div class="thesis-defense-result">' +
            '<div class="thesis-defense-result__title"><i data-lucide="presentation" style="width:14px;height:14px;"></i> 答辩 PPT 大纲</div>' +
            '<div class="thesis-defense-slides">' +
              slides.map((s, idx) => {
                const title = typeof s === 'string' ? s : (s.title || s.slide_title || ('第 ' + (idx + 1) + ' 页'));
                const content = typeof s === 'string' ? '' : (s.content || s.points || s.bullets || '');
                return '' +
                  '<div class="thesis-slide">' +
                    '<div class="thesis-slide__num">' + (idx + 1) + '</div>' +
                    '<div class="thesis-slide__body">' +
                      '<div class="thesis-slide__title">' + escapeHtml(title) + '</div>' +
                      (content ? '<div class="thesis-slide__content">' + escapeHtml(content) + '</div>' : '') +
                    '</div>' +
                  '</div>';
              }).join('') +
            '</div>' +
          '</div>';
      }

      // 答辩问题
      let questionsHtml = '';
      if (state.defense.questions.length > 0) {
        questionsHtml = '' +
          '<div class="thesis-defense-result">' +
            '<div class="thesis-defense-result__title"><i data-lucide="help-circle" style="width:14px;height:14px;"></i> 答辩问题（' + state.defense.questions.length + '）</div>' +
            '<div class="thesis-questions">' +
              state.defense.questions.map((q, idx) => {
                const text = typeof q === 'string' ? q : (q.question || q.text || q.content || '');
                const cat = typeof q === 'object' ? (q.category || q.type) : '';
                const isActive = idx === state.activeQuestionIdx;
                return '' +
                  '<div class="thesis-question' + (isActive ? ' thesis-question--active' : '') + '" data-q-idx="' + idx + '">' +
                    '<div class="thesis-question__head">' +
                      '<span class="thesis-question__num">Q' + (idx + 1) + '</span>' +
                      (cat ? '<span class="badge badge--default">' + escapeHtml(cat) + '</span>' : '') +
                    '</div>' +
                    '<div class="thesis-question__text">' + escapeHtml(text) + '</div>' +
                  '</div>';
              }).join('') +
            '</div>' +
            (state.activeQuestionIdx !== null ? this.renderMockDefense() : '') +
          '</div>';
      }

      // 演讲稿
      let speechHtml = '';
      if (state.defense.speech) {
        speechHtml = '' +
          '<div class="thesis-defense-result">' +
            '<div class="thesis-defense-result__title"><i data-lucide="mic" style="width:14px;height:14px;"></i> 答辩演讲稿</div>' +
            '<div class="thesis-defense-speech thesis-md">' + renderMarkdown(state.defense.speech) + '</div>' +
          '</div>';
      }

      return '' +
        '<div class="thesis-defense">' +
          '<div class="thesis-defense__actions">' +
            '<button class="btn btn-primary" id="thesis-gen-ppt"' + (state.loadingDefense.ppt ? ' disabled' : '') + '>' +
              (state.loadingDefense.ppt ? '<span class="spinner"></span>' : '<i data-lucide="presentation"></i>') +
              '<span>生成答辩PPT</span></button>' +
            '<button class="btn btn-primary" id="thesis-gen-questions"' + (state.loadingDefense.questions ? ' disabled' : '') + '>' +
              (state.loadingDefense.questions ? '<span class="spinner"></span>' : '<i data-lucide="help-circle"></i>') +
              '<span>生成答辩问题</span></button>' +
            '<button class="btn btn-primary" id="thesis-gen-speech"' + (state.loadingDefense.speech ? ' disabled' : '') + '>' +
              (state.loadingDefense.speech ? '<span class="spinner"></span>' : '<i data-lucide="mic"></i>') +
              '<span>生成答辩演讲稿</span></button>' +
          '</div>' +
          pptHtml +
          questionsHtml +
          speechHtml +
        '</div>';
    },

    renderMockDefense() {
      const q = state.defense.questions[state.activeQuestionIdx];
      const qText = typeof q === 'string' ? q : (q.question || q.text || '');
      return '' +
        '<div class="thesis-mock-defense">' +
          '<div class="thesis-mock-defense__q">' +
            '<span class="text-xs text-muted">当前问题</span>' +
            '<div class="text-sm font-medium" style="color:var(--text-primary);">' + escapeHtml(qText) + '</div>' +
          '</div>' +
          '<div class="form-group" style="margin-bottom:var(--space-sm);">' +
            '<label class="form-label">你的回答</label>' +
            '<textarea class="form-control" id="thesis-mock-answer" rows="4" placeholder="输入你的答辩回答…"></textarea>' +
          '</div>' +
          '<div class="flex gap-sm">' +
            '<button class="btn btn-primary btn-sm" id="thesis-submit-mock"><i data-lucide="send"></i><span>提交评估</span></button>' +
          '</div>' +
          (state.defense.evalFeedback ? '' +
            '<div class="thesis-mock-feedback">' +
              '<div class="thesis-mock-feedback__title"><i data-lucide="message-square" style="width:13px;height:13px;"></i> 评估反馈</div>' +
              '<div class="thesis-mock-feedback__body thesis-md">' + renderMarkdown(state.defense.evalFeedback) + '</div>' +
            '</div>' : ''
          ) +
        '</div>';
    },

    rerenderDefense() {
      const body = document.getElementById('thesis-defense-body');
      if (body) {
        body.innerHTML = this.renderDefenseBody();
        refreshIcons(body);
        this.bindDefenseActions();
      }
    },

    bindDefenseActions() {
      const body = document.getElementById('thesis-defense-body');
      if (!body) return;
      const pptBtn = body.querySelector('#thesis-gen-ppt');
      if (pptBtn) pptBtn.addEventListener('click', () => this.handleGenPpt());
      const qBtn = body.querySelector('#thesis-gen-questions');
      if (qBtn) qBtn.addEventListener('click', () => this.handleGenQuestions());
      const speechBtn = body.querySelector('#thesis-gen-speech');
      if (speechBtn) speechBtn.addEventListener('click', () => this.handleGenSpeech());
      // 选择问题
      body.querySelectorAll('[data-q-idx]').forEach((el) => {
        el.addEventListener('click', () => {
          state.activeQuestionIdx = parseInt(el.dataset.qIdx, 10);
          state.defense.evalFeedback = '';
          this.rerenderDefense();
        });
      });
      const submitMock = body.querySelector('#thesis-submit-mock');
      if (submitMock) submitMock.addEventListener('click', () => this.handleEvaluateAnswer());
    },

    async handleGenPpt() {
      if (state.loadingDefense.ppt || !state.sessionId) return;
      state.loadingDefense.ppt = true;
      this.rerenderDefense();
      try {
        const res = await API.generateDefensePpt(state.sessionId, {
          degree: state.degree,
          title: state.proposal ? state.proposal.title : '',
          chapters: state.chapters.map((c) => ({ title: c.title, summary: c.description })),
        });
        state.defense.ppt = (res && (res.ppt || res.data)) || res || null;
        this.rerenderDefense();
        logTimeline('生成答辩PPT', '');
        showToast('答辩 PPT 大纲已生成', 'success');
      } catch (err) {
        showToast('生成 PPT 失败：' + (err.message || err), 'error');
      } finally {
        state.loadingDefense.ppt = false;
        this.rerenderDefense();
      }
    },

    async handleGenQuestions() {
      if (state.loadingDefense.questions || !state.sessionId) return;
      state.loadingDefense.questions = true;
      this.rerenderDefense();
      try {
        const res = await API.generateDefenseQuestions(state.sessionId, {
          degree: state.degree,
          title: state.proposal ? state.proposal.title : '',
        });
        const questions = (res && (res.questions || res.data)) || [];
        state.defense.questions = questions;
        state.activeQuestionIdx = questions.length > 0 ? 0 : null;
        this.rerenderDefense();
        logTimeline('生成答辩问题', questions.length + ' 个问题');
        showToast('已生成 ' + questions.length + ' 个答辩问题', 'success');
      } catch (err) {
        showToast('生成问题失败：' + (err.message || err), 'error');
      } finally {
        state.loadingDefense.questions = false;
        this.rerenderDefense();
      }
    },

    async handleGenSpeech() {
      if (state.loadingDefense.speech || !state.sessionId) return;
      state.loadingDefense.speech = true;
      this.rerenderDefense();
      try {
        const res = await API.generateDefenseSpeech(state.sessionId, {
          degree: state.degree,
          title: state.proposal ? state.proposal.title : '',
        });
        state.defense.speech = (res && (res.speech || res.text || res.content)) || (typeof res === 'string' ? res : '');
        this.rerenderDefense();
        logTimeline('生成演讲稿', '');
        showToast('答辩演讲稿已生成', 'success');
      } catch (err) {
        showToast('生成演讲稿失败：' + (err.message || err), 'error');
      } finally {
        state.loadingDefense.speech = false;
        this.rerenderDefense();
      }
    },

    async handleEvaluateAnswer() {
      if (!state.sessionId || state.activeQuestionIdx === null) return;
      const q = state.defense.questions[state.activeQuestionIdx];
      const answerEl = document.getElementById('thesis-mock-answer');
      const answer = (answerEl && answerEl.value.trim()) || '';
      if (!answer) {
        showToast('请输入你的回答', 'warning');
        if (answerEl) answerEl.focus();
        return;
      }
      const btn = document.getElementById('thesis-submit-mock');
      if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span><span>评估中…</span>'; }
      try {
        const qText = typeof q === 'string' ? q : (q.question || q.text || '');
        const res = await API.evaluateDefenseAnswer(state.sessionId, {
          question: qText,
          answer: answer,
          degree: state.degree,
        });
        state.defense.evalFeedback = (res && (res.feedback || res.evaluation || res.text || res.content)) || (typeof res === 'string' ? res : '评估完成');
        this.rerenderDefense();
        logTimeline('模拟答辩', '已评估回答');
        showToast('评估反馈已生成', 'success');
      } catch (err) {
        showToast('评估失败：' + (err.message || err), 'error');
      } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i data-lucide="send"></i><span>提交评估</span>'; refreshIcons(btn); }
      }
    },

    /* ----------------------------------------------------------------------
       绑定工作区所有动作
       ---------------------------------------------------------------------- */
    bindWorkspaceActions() {
      this.bindOutlineActions();
      this.bindChapterActions();
      this.bindPlagiarismActions();
      this.bindDefenseActions();
    },
  };
})();
