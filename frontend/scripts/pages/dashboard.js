/* ==========================================================================
   ThesisMiner v6.0 - 仪表盘页面
   学术仪表盘：统计概览、最近论题、快速操作与预算概览
   ========================================================================== */
(function () {
  'use strict';

  // 学位/学科标签映射
  const DEGREE_LABELS = { master: '硕士', doctor: '博士' };
  const DISCIPLINE_LABELS = {
    humanities_social: '人文社科',
    science_engineering: '理工科',
  };

  /**
   * 根据置信度评分返回等级标识
   * @param {number} score 0-1
   * @returns {'high'|'mid'|'low'}
   */
  function confidenceLevel(score) {
    const s = Number(score) || 0;
    if (s >= 0.7) return 'high';
    if (s >= 0.4) return 'mid';
    return 'low';
  }

  /** 统计卡片骨架屏 */
  function statSkeleton() {
    return (
      '<div class="stat-card">' +
      '<div class="skeleton skeleton--text" style="width:45%"></div>' +
      '<div class="skeleton skeleton--title"></div>' +
      '<div class="skeleton skeleton--text" style="width:60%"></div>' +
      '</div>'
    );
  }

  /** 论题列表骨架屏 */
  function proposalSkeleton() {
    return (
      '<div class="card">' +
      '<div class="skeleton skeleton--title"></div>' +
      '<div class="skeleton skeleton--text"></div>' +
      '<div class="skeleton skeleton--text" style="width:55%"></div>' +
      '</div>'
    );
  }

  /**
   * 渲染单个统计卡片
   * @param {string} icon Lucide 图标名
   * @param {string} label 标签
   * @param {string} value 数值
   * @param {string} subtitle 副标题
   * @param {string} [valueClass] 数值附加类
   */
  function statCard(icon, label, value, subtitle, valueClass) {
    return (
      '<div class="stat-card">' +
      '<div class="stat-card__icon"><i data-lucide="' + icon + '"></i></div>' +
      '<div class="stat-card__label">' + label + '</div>' +
      '<div class="stat-card__value ' + (valueClass || '') + '">' + value + '</div>' +
      '<div class="stat-card__delta text-muted">' + subtitle + '</div>' +
      '</div>'
    );
  }

  /**
   * 渲染最近论题条目
   * @param {object} p 论题对象
   * @param {string} [degreeLabel] 学位标签
   */
  function proposalItem(p, degreeLabel) {
    const score = Number(p.confidence_score) || 0;
    const pct = Math.round(score * 100);
    const level = confidenceLevel(score);
    const badge = degreeLabel
      ? '<span class="badge badge--accent">' + escapeHtml(degreeLabel) + '</span>'
      : '';
    const desc = p.problem_awareness || p.inspiration_source || '';
    return (
      '<div class="card card--interactive" data-proposal-id="' + escapeHtml(p.id) + '">' +
      '<div class="flex items-start justify-between gap-md mb-sm">' +
      '<h4 class="text-display" style="font-size:1rem;line-height:1.4;flex:1">' +
      escapeHtml(p.title || '未命名论题') + '</h4>' +
      badge +
      '</div>' +
      (desc
        ? '<p class="text-sm text-muted line-clamp-2 mb-md">' + escapeHtml(desc) + '</p>'
        : '') +
      '<div class="flex items-center justify-between gap-md">' +
      '<div class="confidence-bar" style="flex:1;max-width:220px">' +
      '<div class="confidence-bar__track">' +
      '<div class="confidence-bar__fill confidence-bar__fill--' + level +
      '" style="width:' + pct + '%"></div>' +
      '</div>' +
      '<span class="confidence-bar__value">' + pct + '%</span>' +
      '</div>' +
      '<span class="text-xs text-muted text-mono">' +
      formatDate(p.created_at, false) + '</span>' +
      '</div>' +
      '</div>'
    );
  }

  /** 预算概览行 */
  function budgetRow(label, value) {
    return (
      '<div class="flex items-center justify-between">' +
      '<span class="text-sm text-secondary">' + label + '</span>' +
      '<span class="text-mono text-sm">' + value + '</span>' +
      '</div>'
    );
  }

  /**
   * 在抽屉中展示论题完整详情
   * @param {object} p 论题对象
   */
  function showProposalDrawer(p) {
    const sig = p.research_significance || {};
    const theoretical =
      sig && typeof sig === 'object' ? sig.theoretical || '—' : String(sig || '—');
    const practical =
      sig && typeof sig === 'object' ? sig.practical || '—' : '—';
    const content = Array.isArray(p.research_content) ? p.research_content : [];
    const score = Number(p.confidence_score) || 0;
    const pct = Math.round(score * 100);
    const level = confidenceLevel(score);

    const bodyHtml =
      '<div class="flex flex-col gap-md">' +
      '<div>' +
      '<span class="badge badge--accent mb-sm">置信度 ' + pct + '%</span>' +
      (p.auto_rewritten ? '<span class="badge badge--warning ml-sm">已自动改写</span>' : '') +
      '<h3 class="text-display mt-sm" style="font-size:1.25rem;line-height:1.4">' +
      escapeHtml(p.title || '未命名论题') + '</h3>' +
      '</div>' +

      '<div class="confidence-bar">' +
      '<div class="confidence-bar__track">' +
      '<div class="confidence-bar__fill confidence-bar__fill--' + level +
      '" style="width:' + pct + '%"></div>' +
      '</div>' +
      '<span class="confidence-bar__value">' + pct + '%</span>' +
      '</div>' +

      (p.inspiration_source
        ? '<div><h6>灵感来源</h6><p class="text-sm text-secondary">' +
          escapeHtml(p.inspiration_source) + '</p></div>'
        : '') +

      (p.problem_awareness
        ? '<div><h6>问题意识</h6><div class="quote-block">' +
          escapeHtml(p.problem_awareness) + '</div></div>'
        : '') +

      '<div><h6 class="mb-sm">研究意义</h6>' +
      '<div class="flex flex-col gap-sm">' +
      '<div class="card" style="padding:var(--space-md)"><h6 class="text-info">理论意义</h6>' +
      '<p class="text-sm text-secondary mt-sm">' + escapeHtml(theoretical) + '</p></div>' +
      '<div class="card" style="padding:var(--space-md)"><h6 class="text-success">实际意义</h6>' +
      '<p class="text-sm text-secondary mt-sm">' + escapeHtml(practical) + '</p></div>' +
      '</div></div>' +

      (p.literature_review_outline
        ? '<div><h6>文献综述大纲</h6><p class="text-sm text-secondary">' +
          escapeHtml(p.literature_review_outline) + '</p></div>'
        : '') +

      (p.differentiation
        ? '<div><h6>差异化声明</h6><div class="quote-block">' +
          escapeHtml(p.differentiation) + '</div></div>'
        : '') +

      (content.length
        ? '<div><h6 class="mb-sm">研究内容</h6><ol class="flex flex-col gap-sm" style="list-style:decimal inside">' +
          content
            .map(
              (c) =>
                '<li class="text-sm text-secondary">' + escapeHtml(c) + '</li>',
            )
            .join('') +
          '</ol></div>'
        : '') +

      (p.feasibility_analysis
        ? '<div><h6>可行性分析</h6><p class="text-sm text-secondary">' +
          escapeHtml(p.feasibility_analysis) + '</p></div>'
        : '') +
      '</div>';

    showDrawer({ title: '论题详情', bodyHtml: bodyHtml });
  }

  window.Pages = window.Pages || {};
  window.Pages.dashboard = {
    /** 渲染页面骨架（同步返回 HTML 字符串） */
    render() {
      return (
        '<header class="page-header">' +
        '<div class="page-header__eyebrow">ThesisMiner · Dashboard</div>' +
        '<h1 class="page-header__title">学术仪表盘</h1>' +
        '<p class="page-header__desc">纵览论题生成、会话演进与预算消耗的全局态势，洞察学术创作的每一次脉动。</p>' +
        '</header>' +
        '<div class="page-body">' +
        '<!-- 统计卡片 -->' +
        '<div class="grid grid--4 stagger" id="dash-stats">' +
        statSkeleton() + statSkeleton() + statSkeleton() + statSkeleton() +
        '</div>' +
        '<!-- 主体两列 -->' +
        '<div class="grid mt-lg" style="grid-template-columns:2fr 1fr;gap:var(--space-lg)" id="dash-main">' +
        '<section>' +
        '<div class="flex items-center justify-between mb-md">' +
        '<h2 class="heading-accent" style="font-size:1.1rem">最近论题</h2>' +
        '<button class="btn btn-ghost btn-sm" data-action="goto-sessions">' +
        '<i data-lucide="history"></i> 查看历史' +
        '</button>' +
        '</div>' +
        '<div id="dash-proposals" class="list stagger">' +
        proposalSkeleton() + proposalSkeleton() + proposalSkeleton() +
        '</div>' +
        '</section>' +
        '<aside class="flex flex-col gap-lg">' +
        '<div class="card">' +
        '<div class="card__header"><h3 class="card__title">快速操作</h3></div>' +
        '<div class="flex flex-col gap-sm">' +
        '<button class="btn btn-primary btn-block" data-action="goto-generate">' +
        '<i data-lucide="sparkles"></i> 生成论题</button>' +
        '<button class="btn btn-secondary btn-block" data-action="goto-lineage">' +
        '<i data-lucide="git-fork"></i> 导入谱系</button>' +
        '<button class="btn btn-secondary btn-block" data-action="goto-sessions">' +
        '<i data-lucide="history"></i> 查看历史</button>' +
        '</div>' +
        '</div>' +
        '<div class="card">' +
        '<div class="card__header">' +
        '<h3 class="card__title">预算概览</h3>' +
        '<i data-lucide="wallet" style="width:18px;height:18px;color:var(--accent-primary)"></i>' +
        '</div>' +
        '<div id="dash-budget" class="flex flex-col gap-md">' +
        '<div class="skeleton skeleton--text"></div>' +
        '<div class="skeleton skeleton--text"></div>' +
        '<div class="skeleton skeleton--text"></div>' +
        '</div>' +
        '</div>' +
        '</aside>' +
        '</div>' +
        '</div>'
      );
    },

    /** app.js 调用入口：委托给 mount(container) */
    async init() {
      const container = document.getElementById('app-content');
      if (container) await this.mount(container);
    },

    /** 挂载到主内容区：绑定事件并加载数据 */
    async mount(container) {
      refreshIcons();
      this.bindActions(container);
      // 并行加载各部分数据，互不阻塞
      this.loadStats();
      this.loadProposals();
      this.loadBudget();
    },

    /** 绑定快速操作按钮 */
    bindActions(root) {
      if (!root) return;
      root.querySelectorAll('[data-action]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const action = btn.dataset.action;
          if (action === 'goto-generate') navigate('generate');
          else if (action === 'goto-lineage') navigate('lineage');
          else if (action === 'goto-sessions') navigate('sessions');
        });
      });
    },

    /** 加载统计卡片数据 */
    async loadStats() {
      const wrap = document.getElementById('dash-stats');
      if (!wrap) return;
      try {
        const [proposalsRes, sessionsRes, budgetRes, statusRes] = await Promise.all([
          API.getProposals(1000, 0).catch(() => ({ proposals: [], count: 0 })),
          API.getSessions(1000, 0).catch(() => ({ sessions: [], count: 0 })),
          API.getBudgetSummary().catch(() => ({})),
          API.getStatus().catch(() => ({})),
        ]);

        const proposalCount = (proposalsRes && proposalsRes.count) || 0;
        const sessionCount = (sessionsRes && sessionsRes.count) || 0;
        const totalCost = (budgetRes && budgetRes.total_cost) || 0;
        const aiConfigured = !!(statusRes && statusRes.ai_configured);

        wrap.innerHTML =
          statCard('file-text', '论题总数', proposalCount, '已生成论题提案') +
          statCard('history', '会话总数', sessionCount, '累计创作会话') +
          statCard(
            'wallet',
            '预算消耗',
            '<span class="stat-card__value-mono">' + formatCost(totalCost) + '</span>',
            'API 调用总费用',
          ) +
          statCard(
            'cpu',
            'AI 状态',
            aiConfigured ? '已就绪' : '未配置',
            aiConfigured ? '可正常生成论题' : '请前往设置配置',
            aiConfigured ? 'text-success' : 'text-danger',
          );
        refreshIcons();
      } catch (err) {
        wrap.innerHTML =
          '<div class="empty-state" style="grid-column:1/-1">' +
          '<div class="empty-state__icon" data-lucide="alert-circle"></div>' +
          '<div class="empty-state__title">统计数据加载失败</div>' +
          '<p class="empty-state__desc">' + escapeHtml(err.message || String(err)) + '</p>' +
          '</div>';
        refreshIcons();
      }
    },

    /** 加载最近论题列表 */
    async loadProposals() {
      const wrap = document.getElementById('dash-proposals');
      if (!wrap) return;
      try {
        const [proposalsRes, sessionsRes] = await Promise.all([
          API.getProposals(1000, 0).catch(() => ({ proposals: [], count: 0 })),
          API.getSessions(1000, 0).catch(() => ({ sessions: [], count: 0 })),
        ]);

        const proposals = (proposalsRes && proposalsRes.proposals) || [];
        const sessions = (sessionsRes && sessionsRes.sessions) || [];
        // 构建 session_id -> degree 映射，用于显示学位标签
        const degreeMap = {};
        sessions.forEach((s) => {
          if (s && s.id) degreeMap[s.id] = s.degree;
        });

        const recent = proposals.slice(0, 5);

        if (!recent.length) {
          wrap.innerHTML =
            '<div class="empty-state">' +
            '<div class="empty-state__icon" data-lucide="file-text"></div>' +
            '<div class="empty-state__title">尚未生成论题</div>' +
            '<p class="empty-state__desc">前往「论题生成」页面，输入导师信息即可开启第一次学术创作。</p>' +
            '<button class="btn btn-primary btn-sm mt-md" data-action="goto-generate">' +
            '<i data-lucide="sparkles"></i> 立即生成</button>' +
            '</div>';
          refreshIcons();
          // 仅绑定空状态内的按钮，避免重复绑定全局操作
          const genBtn = wrap.querySelector('[data-action="goto-generate"]');
          if (genBtn) genBtn.addEventListener('click', () => navigate('generate'));
          return;
        }

        wrap.innerHTML = recent
          .map((p) => {
            const deg = degreeMap[p.session_id];
            return proposalItem(p, deg ? DEGREE_LABELS[deg] || deg : '');
          })
          .join('');
        refreshIcons();

        // 点击论题打开详情抽屉
        wrap.querySelectorAll('[data-proposal-id]').forEach((el) => {
          el.addEventListener('click', () => {
            const id = el.dataset.proposalId;
            const target = proposals.find((x) => x.id === id);
            if (target) showProposalDrawer(target);
          });
        });
      } catch (err) {
        wrap.innerHTML =
          '<div class="empty-state">' +
          '<div class="empty-state__icon" data-lucide="alert-circle"></div>' +
          '<div class="empty-state__title">论题加载失败</div>' +
          '<p class="empty-state__desc">' + escapeHtml(err.message || String(err)) + '</p>' +
          '</div>';
        refreshIcons();
      }
    },

    /** 加载预算概览卡片 */
    async loadBudget() {
      const wrap = document.getElementById('dash-budget');
      if (!wrap) return;
      try {
        const res = await API.getBudgetSummary();
        const calls = (res && res.total_calls) || 0;
        const tokens = (res && res.total_tokens) || 0;
        const cost = (res && res.total_cost) || 0;
        wrap.innerHTML =
          budgetRow('总调用次数', calls.toLocaleString()) +
          budgetRow('总 Token', Number(tokens).toLocaleString()) +
          budgetRow('总费用', formatCost(cost));
      } catch (err) {
        wrap.innerHTML =
          '<p class="text-sm text-danger">' +
          escapeHtml(err.message || String(err)) + '</p>';
      }
    },
  };
})();
