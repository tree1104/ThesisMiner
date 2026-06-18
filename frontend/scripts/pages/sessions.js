/* ==========================================================================
   ThesisMiner v6.0 - 会话历史页面
   展示会话列表、统计指标、详情抽屉与关联论题
   页面注册到 window.Pages.sessions，由 app.js 路由系统动态加载
   ========================================================================== */
(function () {
  'use strict';

  // 学位 / 学科中文标签映射
  const DEGREE_LABELS = { master: '硕士', doctor: '博士' };
  const DISCIPLINE_LABELS = {
    humanities_social: '人文社科',
    science_engineering: '理工',
  };

  // 状态徽章配置：active=绿、completed=蓝、failed=红
  const STATUS_BADGE = {
    active: { cls: 'badge--success', label: '进行中' },
    completed: { cls: 'badge--info', label: '已完成' },
    failed: { cls: 'badge--danger', label: '已失败' },
    closed: { cls: 'badge--default', label: '已关闭' },
  };

  // 生成状态徽章 HTML
  function statusBadge(status) {
    const cfg = STATUS_BADGE[status] || { cls: 'badge--default', label: status || '未知' };
    return `<span class="badge ${cfg.cls}"><span class="badge__dot"></span>${escapeHtml(cfg.label)}</span>`;
  }

  // 学位徽章
  function degreeBadge(degree) {
    const label = DEGREE_LABELS[degree] || degree || '—';
    return `<span class="badge badge--accent">${escapeHtml(label)}</span>`;
  }

  // 学科徽章
  function disciplineBadge(discipline) {
    const label = DISCIPLINE_LABELS[discipline] || discipline || '—';
    return `<span class="badge badge--default">${escapeHtml(label)}</span>`;
  }

  // 列表骨架屏
  function skeletonList(n) {
    let rows = '';
    for (let i = 0; i < (n || 5); i++) {
      rows += `
        <div class="list-item">
          <div class="skeleton" style="width:36px;height:36px;border-radius:6px;flex-shrink:0;"></div>
          <div class="flex-1">
            <div class="skeleton skeleton--title"></div>
            <div class="skeleton skeleton--text" style="width:45%;"></div>
          </div>
          <div class="skeleton" style="width:64px;height:22px;border-radius:6px;"></div>
        </div>`;
    }
    return rows;
  }

  window.Pages = window.Pages || {};
  window.Pages.sessions = {
    // 同步返回页面骨架，供 app.js 直接注入
    render() {
      return `
        <header class="page-header">
          <div class="page-header__eyebrow">ThesisMiner · Sessions</div>
          <h1 class="page-header__title">会话历史</h1>
          <p class="page-header__desc">查阅历次论题生成会话，追踪状态演进与关联论题产出。</p>
        </header>
        <div class="page-body">
          <!-- 顶部统计栏 -->
          <div class="grid grid--2 mb-lg">
            <div class="stat-card">
              <div class="stat-card__icon" data-lucide="layers"></div>
              <div class="stat-card__label">总会话数</div>
              <div class="stat-card__value" id="stat-total">—</div>
            </div>
            <div class="stat-card">
              <div class="stat-card__icon" data-lucide="activity"></div>
              <div class="stat-card__label">活跃会话</div>
              <div class="stat-card__value text-success" id="stat-active">—</div>
            </div>
          </div>

          <!-- 会话列表 -->
          <div class="card">
            <div class="card__header">
              <div>
                <div class="card__title">会话记录</div>
                <div class="card__subtitle">按创建时间倒序排列</div>
              </div>
              <button class="btn btn-secondary btn-sm" id="sessions-refresh">
                <i data-lucide="refresh-cw"></i><span>刷新</span>
              </button>
            </div>
            <div id="sessions-list" class="list stagger">
              ${skeletonList()}
            </div>
          </div>
        </div>
      `;
    },

    // app.js 调用入口：委托给 mount(container)
    async init() {
      const container = document.getElementById('app-content');
      if (container) await this.mount(container);
    },

    // 挂载到主内容区：绑定事件并加载数据
    async mount(container) {
      const refreshBtn = container.querySelector('#sessions-refresh');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => this.loadSessions());
      }
      await this.loadSessions();
    },

    // 加载会话列表
    async loadSessions() {
      const listEl = document.getElementById('sessions-list');
      const totalEl = document.getElementById('stat-total');
      const activeEl = document.getElementById('stat-active');
      if (!listEl) return;

      listEl.innerHTML = skeletonList();
      refreshIcons(listEl);

      try {
        const data = await API.getSessions(20, 0);
        const sessions = (data && data.sessions) || [];
        const total = sessions.length;
        const active = sessions.filter((s) => s.status === 'active').length;
        if (totalEl) totalEl.textContent = String(total);
        if (activeEl) activeEl.textContent = String(active);

        if (sessions.length === 0) {
          listEl.innerHTML = this.emptyState();
          refreshIcons(listEl);
          // 绑定空状态引导按钮
          const gotoBtn = listEl.querySelector('#empty-goto-generate');
          if (gotoBtn) gotoBtn.addEventListener('click', () => navigate('generate'));
          return;
        }

        listEl.innerHTML = sessions.map((s) => this.sessionCard(s)).join('');
        // 绑定行内事件
        listEl.querySelectorAll('[data-session-id]').forEach((el) => {
          const id = el.dataset.sessionId;
          const viewBtn = el.querySelector('[data-action="view"]');
          const delBtn = el.querySelector('[data-action="delete"]');
          if (viewBtn) viewBtn.addEventListener('click', (e) => { e.stopPropagation(); this.showDetail(id); });
          if (delBtn) delBtn.addEventListener('click', (e) => { e.stopPropagation(); this.confirmDelete(id); });
          el.addEventListener('click', () => this.showDetail(id));
        });
        refreshIcons(listEl);
      } catch (err) {
        listEl.innerHTML = this.errorState(err);
        refreshIcons(listEl);
        showToast(err.message || '加载会话失败', 'error');
      }
    },

    // 单条会话卡片
    sessionCard(s) {
      const title = escapeHtml(s.title || '未命名会话');
      const time = formatDate(s.created_at);
      const shortId = escapeHtml((s.id || '').slice(0, 8));
      return `
        <div class="list-item list-item--clickable" data-session-id="${escapeHtml(s.id)}">
          <span class="flex items-center justify-center" style="width:36px;height:36px;border-radius:var(--radius-sm);background:var(--bg-elevated);color:var(--accent-primary);flex-shrink:0;">
            <i data-lucide="history"></i>
          </span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-sm flex-wrap mb-sm">
              <span class="text-display font-semibold" style="color:var(--text-primary);font-size:0.95rem;">${title}</span>
              ${degreeBadge(s.degree)}
              ${disciplineBadge(s.discipline)}
            </div>
            <div class="flex items-center gap-md text-xs text-muted flex-wrap">
              <span class="flex items-center gap-xs"><i data-lucide="clock" style="width:12px;height:12px;"></i>${time}</span>
              <span class="text-mono">#${shortId}</span>
            </div>
          </div>
          <div class="flex items-center gap-sm">
            ${statusBadge(s.status)}
            <button class="btn btn-ghost btn-sm btn-icon" data-action="view" title="查看详情" aria-label="查看详情">
              <i data-lucide="eye"></i>
            </button>
            <button class="btn btn-ghost btn-sm btn-icon" data-action="delete" title="删除会话" aria-label="删除会话" style="color:var(--danger);">
              <i data-lucide="trash-2"></i>
            </button>
          </div>
        </div>`;
    },

    // 空状态
    emptyState() {
      return `
        <div class="empty-state">
          <div class="empty-state__icon" data-lucide="inbox"></div>
          <div class="empty-state__title">暂无会话记录</div>
          <p class="empty-state__desc">开始生成论题以创建会话，所有会话将在此处归档。</p>
          <button class="btn btn-primary mt-md" id="empty-goto-generate">
            <i data-lucide="sparkles"></i><span>前往论题生成</span>
          </button>
        </div>`;
    },

    // 错误状态
    errorState(err) {
      return `
        <div class="empty-state">
          <div class="empty-state__icon text-danger" data-lucide="alert-triangle"></div>
          <div class="empty-state__title">加载失败</div>
          <p class="empty-state__desc">${escapeHtml(err.message || '未知错误')}</p>
        </div>`;
    },

    // 打开详情抽屉：先展示骨架，数据到达后填充
    async showDetail(sessionId) {
      const { drawer } = showDrawer({
        title: '会话详情',
        bodyHtml: `<div class="loading-overlay"><div class="spinner spinner--lg"></div><div>正在加载会话详情…</div></div>`,
      });
      try {
        const [session, proposalsData] = await Promise.all([
          API.getSession(sessionId),
          API.getProposals(20, 0, sessionId),
        ]);
        const proposals = (proposalsData && proposalsData.proposals) || [];
        const body = drawer && drawer.querySelector('.drawer__body');
        if (body) {
          body.innerHTML = this.detailBodyHtml(session, proposals);
          refreshIcons(drawer);
        }
      } catch (err) {
        const body = drawer && drawer.querySelector('.drawer__body');
        if (body) {
          body.innerHTML = this.errorState(err);
          refreshIcons(drawer);
        }
        showToast(err.message || '加载详情失败', 'error');
      }
    },

    // 详情抽屉主体 HTML
    detailBodyHtml(session, proposals) {
      return `
        <div class="flex flex-col gap-md">
          <div>
            <div class="text-xs text-muted mb-sm" style="letter-spacing:0.08em;text-transform:uppercase;">论题标题</div>
            <div class="text-display" style="font-size:1.15rem;color:var(--text-primary);line-height:1.4;">${escapeHtml(session.title || '未命名会话')}</div>
          </div>
          <div class="flex items-center gap-sm flex-wrap">
            ${degreeBadge(session.degree)}
            ${disciplineBadge(session.discipline)}
            ${statusBadge(session.status)}
          </div>
          <div class="grid grid--2" style="gap:var(--space-md);">
            <div>
              <div class="text-xs text-muted mb-xs">会话 ID</div>
              <div class="text-mono text-sm" style="color:var(--text-primary);">${escapeHtml(session.id || '—')}</div>
            </div>
            <div>
              <div class="text-xs text-muted mb-xs">创建时间</div>
              <div class="text-sm">${formatDate(session.created_at)}</div>
            </div>
            <div>
              <div class="text-xs text-muted mb-xs">更新时间</div>
              <div class="text-sm">${formatDate(session.updated_at)}</div>
            </div>
            <div>
              <div class="text-xs text-muted mb-xs">导师信息</div>
              <div class="text-sm">${escapeHtml(session.mentor_info || '—')}</div>
            </div>
          </div>
          <hr class="divider" />
          <div>
            <div class="flex items-center justify-between mb-md">
              <h4 class="text-display" style="font-size:1rem;">关联论题</h4>
              <span class="badge badge--accent">${proposals.length} 条</span>
            </div>
            ${proposals.length === 0 ? `
              <div class="empty-state" style="padding:var(--space-lg);">
                <div class="empty-state__icon" data-lucide="file-text"></div>
                <div class="empty-state__title">暂无论题</div>
                <p class="empty-state__desc">该会话尚未生成论题。</p>
              </div>
            ` : `
              <div class="list">
                ${proposals.map((p) => this.proposalItem(p)).join('')}
              </div>
            `}
          </div>
        </div>
      `;
    },

    // 关联论题条目
    proposalItem(p) {
      const score = typeof p.confidence_score === 'number'
        ? Math.round(p.confidence_score * 100)
        : null;
      return `
        <div class="list-item flex-col" style="align-items:stretch;">
          <div class="text-display font-semibold" style="color:var(--text-primary);font-size:0.9rem;line-height:1.4;">
            ${escapeHtml(p.title || '未命名论题')}
          </div>
          <div class="flex items-center gap-sm flex-wrap mt-sm">
            ${score !== null ? `<span class="badge badge--default">置信度 ${score}%</span>` : ''}
            ${p.auto_rewritten ? `<span class="badge badge--accent">已改写</span>` : ''}
            <span class="text-xs text-muted">${formatDate(p.created_at, false)}</span>
          </div>
        </div>`;
    },

    // 删除确认抽屉
    confirmDelete(sessionId) {
      showDrawer({
        title: '删除会话',
        bodyHtml: `
          <div class="flex items-start gap-md">
            <div class="text-danger" data-lucide="alert-triangle" style="width:24px;height:24px;flex-shrink:0;"></div>
            <div>
              <p class="font-medium" style="color:var(--text-primary);margin-bottom:var(--space-sm);">确定要删除该会话吗？</p>
              <p class="text-sm text-secondary">删除后无法恢复，关联的论题记录可能仍保留。</p>
            </div>
          </div>
        `,
        footerHtml: `
          <button class="btn btn-secondary" data-action="cancel">取消</button>
          <button class="btn btn-danger" data-action="confirm">
            <i data-lucide="trash-2"></i><span>确认删除</span>
          </button>
        `,
        onMount: (drawer) => {
          const cancelBtn = drawer.querySelector('[data-action="cancel"]');
          const confirmBtn = drawer.querySelector('[data-action="confirm"]');
          if (cancelBtn) cancelBtn.addEventListener('click', () => closeDrawer());
          if (confirmBtn) confirmBtn.addEventListener('click', async () => {
            confirmBtn.disabled = true;
            try {
              await API.deleteSession(sessionId);
              closeDrawer();
              showToast('会话已删除', 'success');
              this.loadSessions();
            } catch (err) {
              confirmBtn.disabled = false;
              showToast(err.message || '删除失败', 'error');
            }
          });
        },
      });
    },
  };
})();
