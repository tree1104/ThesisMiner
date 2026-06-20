/* ==========================================================================
   ThesisMiner v8.0 - 会话历史页面（多对话管理 UI）
   左侧会话列表 + 右侧对话工作区（标签 / 消息 / 引用 / 流式输出）
   页面注册到 window.Pages.sessions，由 app.js 路由系统动态加载
   ========================================================================== */
(function () {
  'use strict';

  // Agent 配色与标签（与 main.css 中 --agent-* 令牌一致）
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

  // 状态徽章配置
  const STATUS_BADGE = {
    active: { cls: 'badge--success', label: '进行中' },
    completed: { cls: 'badge--info', label: '已完成' },
    failed: { cls: 'badge--danger', label: '已失败' },
    closed: { cls: 'badge--default', label: '已关闭' },
  };

  // sessionStorage 缓存键与 TTL：用于会话列表首屏加速
  const SESSIONS_CACHE_KEY = 'thesisminer_sessions_cache';
  const SESSIONS_CACHE_TTL = 30000;

  // 流式轮询配置
  const STREAM_POLL_INTERVAL = 1500;
  const STREAM_POLL_TIMEOUT = 90000;

  // 页面状态
  const state = {
    sessions: [],
    activeSessionId: null,
    conversations: [],
    activeConversationId: null,
    messages: [],
    agents: [],
    selectedAgent: 'orchestrator',
    sending: false,
    streaming: false,
    streamTimer: null,
    streamStart: 0,
    knownMessageIds: new Set(),
    // v9.0 Task 7：深度思考与联网搜索开关
    deepThinking: false,
    webSearching: false,
    // v9.0 Task 7：SSE 流式渲染的 DOM 引用与中断控制器
    streamAbortController: null,
    streamDomRefs: null,
  };

  // 取 Agent 配色，未知 Agent 回退到主色
  function agentColor(agentId) {
    return AGENT_COLORS[agentId] || '#4F46E5';
  }

  // 取 Agent 中文/英文标签
  function agentLabel(agentId) {
    return AGENT_LABELS[agentId] || (agentId || 'Agent');
  }

  // 状态徽章 HTML
  function statusBadge(status) {
    const cfg = STATUS_BADGE[status] || { cls: 'badge--default', label: status || '未知' };
    return '<span class="badge ' + cfg.cls + '"><span class="badge__dot"></span>' + escapeHtml(cfg.label) + '</span>';
  }

  // 会话列表骨架屏
  function skeletonSessions(n) {
    let rows = '';
    for (let i = 0; i < (n || 4); i++) {
      rows += '<div class="session-item">' +
        '<div class="skeleton skeleton--title" style="width:70%;"></div>' +
        '<div class="skeleton skeleton--text" style="width:45%;"></div>' +
        '</div>';
    }
    return rows;
  }

  window.Pages = window.Pages || {};
  window.Pages.sessions = {
    // 同步返回页面骨架
    render() {
      return '' +
        '<header class="page-header">' +
          '<div class="page-header__eyebrow">ThesisMiner · Sessions</div>' +
          '<h1 class="page-header__title">会话与对话</h1>' +
          '<p class="page-header__desc">管理历次会话，每个会话下可开启多个独立对话，按 Agent 类型路由，上下文完全隔离。</p>' +
        '</header>' +
        '<div class="page-body">' +
          '<div class="session-layout">' +
            // 左侧：会话列表
            '<aside class="session-sidebar">' +
              '<div class="session-sidebar__header">' +
                '<span class="session-sidebar__title">会话列表</span>' +
                '<button class="btn btn-ghost btn-sm btn-icon" id="sessions-refresh" title="刷新" aria-label="刷新">' +
                  '<i data-lucide="refresh-cw"></i>' +
                '</button>' +
              '</div>' +
              '<div id="sessions-list" class="session-sidebar__list">' + skeletonSessions() + '</div>' +
            '</aside>' +
            // 右侧：对话工作区
            '<section class="session-workspace" id="session-workspace">' +
              this.workspaceEmptyHtml() +
            '</section>' +
          '</div>' +
        '</div>';
    },

    // 对话工作区空状态
    workspaceEmptyHtml() {
      return '' +
        '<div class="session-empty" id="workspace-empty">' +
          '<div class="session-empty__icon" data-lucide="messages-square"></div>' +
          '<div class="session-empty__title">选择一个会话</div>' +
          '<p class="session-empty__desc">从左侧选择会话，即可管理其下的多个对话，按 Agent 类型发送消息。</p>' +
        '</div>';
    },

    // app.js 调用入口
    async init() {
      const container = document.getElementById('app-content');
      if (container) await this.mount(container);
    },

    // 挂载：绑定事件并加载数据
    async mount(container) {
      const refreshBtn = container.querySelector('#sessions-refresh');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => this.loadSessions());
      }
      // 并行加载会话列表与 Agent 列表
      await Promise.all([
        this.loadSessions(),
        this.loadAgents(),
      ]);
    },

    /* ----------------------------------------------------------------------
       会话列表
       ---------------------------------------------------------------------- */

    // 加载会话列表（优先 sessionStorage 缓存加速首屏）
    async loadSessions() {
      const listEl = document.getElementById('sessions-list');
      if (!listEl) return;

      let usedCache = false;
      try {
        const cached = sessionStorage.getItem(SESSIONS_CACHE_KEY);
        if (cached) {
          const parsed = JSON.parse(cached);
          const cachedData = parsed && parsed.data;
          const timestamp = parsed && parsed.timestamp;
          if (cachedData && timestamp && Date.now() - timestamp < SESSIONS_CACHE_TTL) {
            this.renderSessionList(cachedData.sessions || []);
            usedCache = true;
            this.refreshSessionsInBackground(true);
            return;
          }
          this.renderSessionList(cachedData.sessions || []);
          usedCache = true;
        }
      } catch (_) {}

      if (!usedCache) {
        listEl.innerHTML = skeletonSessions();
        refreshIcons(listEl);
      }
      await this.refreshSessionsInBackground(!usedCache);
    },

    // 后台静默刷新会话列表
    async refreshSessionsInBackground(silent) {
      const listEl = document.getElementById('sessions-list');
      if (!listEl) return;
      try {
        const data = await API.getSessions(50, 0);
        try {
          sessionStorage.setItem(
            SESSIONS_CACHE_KEY,
            JSON.stringify({ data: data, timestamp: Date.now() }),
          );
        } catch (_) {}
        this.renderSessionList((data && data.sessions) || []);
      } catch (err) {
        if (!silent || !listEl.children.length) {
          listEl.innerHTML = this.sessionListErrorHtml(err);
          refreshIcons(listEl);
        }
        showToast(err.message || '加载会话失败', 'error');
      }
    },

    // 渲染会话列表
    renderSessionList(sessions) {
      const listEl = document.getElementById('sessions-list');
      if (!listEl) return;
      state.sessions = sessions || [];

      if (state.sessions.length === 0) {
        listEl.innerHTML = '' +
          '<div class="session-empty" style="padding:var(--space-lg);">' +
            '<div class="session-empty__icon" data-lucide="inbox"></div>' +
            '<div class="session-empty__title">暂无会话</div>' +
            '<p class="session-empty__desc">前往论题生成创建会话。</p>' +
            '<button class="btn btn-primary btn-sm mt-sm" id="empty-goto-generate">' +
              '<i data-lucide="sparkles"></i><span>前往生成</span>' +
            '</button>' +
          '</div>';
        refreshIcons(listEl);
        const gotoBtn = listEl.querySelector('#empty-goto-generate');
        if (gotoBtn) gotoBtn.addEventListener('click', () => navigate('generate'));
        return;
      }

      listEl.innerHTML = state.sessions.map((s) => this.sessionItemHtml(s)).join('');
      refreshIcons(listEl);

      // 绑定事件
      listEl.querySelectorAll('[data-session-id]').forEach((el) => {
        const id = el.dataset.sessionId;
        el.addEventListener('click', (e) => {
          if (e.target.closest('[data-action]')) return;
          this.selectSession(id);
        });
        const delBtn = el.querySelector('[data-action="delete"]');
        if (delBtn) delBtn.addEventListener('click', (e) => { e.stopPropagation(); this.confirmDeleteSession(id); });
        const viewBtn = el.querySelector('[data-action="view"]');
        if (viewBtn) viewBtn.addEventListener('click', (e) => { e.stopPropagation(); this.showSessionDetail(id); });
      });
    },

    // 单条会话项
    sessionItemHtml(s) {
      const title = escapeHtml(s.title || '未命名会话');
      const time = formatDate(s.created_at, false);
      const isActive = s.id === state.activeSessionId;
      return '' +
        '<div class="session-item' + (isActive ? ' session-item--active' : '') + '" data-session-id="' + escapeHtml(s.id) + '">' +
          '<div class="session-item__title">' + title + '</div>' +
          '<div class="session-item__meta">' +
            '<span>' + time + '</span>' +
            statusBadge(s.status) +
            '<span style="margin-left:auto;display:flex;gap:2px;">' +
              '<button class="btn btn-ghost btn-icon btn-sm" data-action="view" title="详情" aria-label="详情" style="width:24px;height:24px;">' +
                '<i data-lucide="eye" style="width:13px;height:13px;"></i>' +
              '</button>' +
              '<button class="btn btn-ghost btn-icon btn-sm" data-action="delete" title="删除" aria-label="删除" style="width:24px;height:24px;color:var(--danger);">' +
                '<i data-lucide="trash-2" style="width:13px;height:13px;"></i>' +
              '</button>' +
            '</span>' +
          '</div>' +
        '</div>';
    },

    sessionListErrorHtml(err) {
      return '' +
        '<div class="session-empty" style="padding:var(--space-lg);">' +
          '<div class="session-empty__icon text-danger" data-lucide="alert-triangle"></div>' +
          '<div class="session-empty__title">加载失败</div>' +
          '<p class="session-empty__desc">' + escapeHtml(err.message || '未知错误') + '</p>' +
        '</div>';
    },

    // 选中会话：加载其对话列表
    async selectSession(sessionId) {
      if (!sessionId) return;
      state.activeSessionId = sessionId;
      state.activeConversationId = null;
      state.conversations = [];
      state.messages = [];

      // 更新左侧高亮
      document.querySelectorAll('[data-session-id]').forEach((el) => {
        el.classList.toggle('session-item--active', el.dataset.sessionId === sessionId);
      });

      // 渲染右侧工作区骨架
      const ws = document.getElementById('session-workspace');
      if (ws) {
        ws.innerHTML = this.workspaceSkeletonHtml();
        refreshIcons(ws);
        this.bindInputArea();
      }

      await this.loadConversations(sessionId);
    },

    // 工作区骨架
    workspaceSkeletonHtml() {
      return '' +
        '<div class="session-tabs" id="session-tabs"></div>' +
        '<div class="session-messages" id="session-messages">' +
          '<div class="session-empty">' +
            '<div class="spinner spinner--lg"></div>' +
            '<div class="session-empty__title">加载对话中…</div>' +
          '</div>' +
        '</div>' +
        this.inputAreaHtml();
    },

    /* ----------------------------------------------------------------------
       对话标签管理
       ---------------------------------------------------------------------- */

    // 加载会话下的对话列表
    async loadConversations(sessionId) {
      try {
        const data = await API.getConversations(sessionId);
        state.conversations = (data && data.conversations) || [];
        this.renderTabs();

        // 自动选中第一个对话或后端标记的活跃对话
        const activeConv = state.conversations.find((c) => c.is_active) || state.conversations[0];
        if (activeConv) {
          await this.selectConversation(activeConv.id);
        } else {
          this.renderMessagesEmpty();
        }
      } catch (err) {
        const msgEl = document.getElementById('session-messages');
        if (msgEl) {
          msgEl.innerHTML = '' +
            '<div class="session-empty">' +
              '<div class="session-empty__icon text-danger" data-lucide="alert-triangle"></div>' +
              '<div class="session-empty__title">对话加载失败</div>' +
              '<p class="session-empty__desc">' + escapeHtml(err.message || '未知错误') + '</p>' +
            '</div>';
          refreshIcons(msgEl);
        }
        showToast(err.message || '加载对话失败', 'error');
      }
    },

    // 渲染对话标签栏
    renderTabs() {
      const tabsEl = document.getElementById('session-tabs');
      if (!tabsEl) return;

      const tabsHtml = state.conversations.map((c) => {
        const isActive = c.id === state.activeConversationId;
        const color = agentColor(c.agent_id);
        return '' +
          '<div class="session-tab' + (isActive ? ' session-tab--active' : '') + '" data-conversation-id="' + escapeHtml(c.id) + '" title="' + escapeHtml(c.title || '') + '">' +
            '<span style="width:8px;height:8px;border-radius:50%;background:' + color + ';flex-shrink:0;"></span>' +
            '<span class="session-tab__label">' + escapeHtml(c.title || '新对话') + '</span>' +
            '<button class="session-tab__close" data-action="close-tab" title="关闭" aria-label="关闭对话">' +
              '<i data-lucide="x"></i>' +
            '</button>' +
          '</div>';
      }).join('');

      tabsEl.innerHTML = tabsHtml +
        '<button class="session-tab-new" id="tab-new" title="新建对话">' +
          '<i data-lucide="plus"></i><span>新对话</span>' +
        '</button>';

      refreshIcons(tabsEl);

      // 绑定标签事件
      tabsEl.querySelectorAll('[data-conversation-id]').forEach((el) => {
        const id = el.dataset.conversationId;
        el.addEventListener('click', (e) => {
          if (e.target.closest('[data-action="close-tab"]')) return;
          this.selectConversation(id);
        });
        const closeBtn = el.querySelector('[data-action="close-tab"]');
        if (closeBtn) closeBtn.addEventListener('click', (e) => { e.stopPropagation(); this.confirmCloseConversation(id); });
        // 双击重命名
        el.addEventListener('dblclick', (e) => {
          if (e.target.closest('[data-action]')) return;
          this.renameConversation(id);
        });
      });

      const newBtn = tabsEl.querySelector('#tab-new');
      if (newBtn) newBtn.addEventListener('click', () => this.openNewConversationDrawer());
    },

    // 选中对话：切换上下文（完全隔离）
    async selectConversation(conversationId) {
      if (!conversationId) return;
      // 停止任何进行中的流式轮询
      this.stopStreaming();

      state.activeConversationId = conversationId;
      state.messages = [];
      state.knownMessageIds = new Set();

      // 更新标签高亮
      document.querySelectorAll('[data-conversation-id]').forEach((el) => {
        el.classList.toggle('session-tab--active', el.dataset.conversationId === conversationId);
      });

      // 同步活跃对话到后端
      if (state.activeSessionId) {
        try { await API.setActiveConversation(state.activeSessionId, conversationId); } catch (_) {}
      }

      await this.loadMessages(conversationId);
    },

    // 新建对话抽屉（选择 Agent 类型）
    openNewConversationDrawer() {
      if (!state.activeSessionId) {
        showToast('请先选择一个会话', 'warning');
        return;
      }
      const agentOptions = Object.keys(AGENT_LABELS)
        .map((k) => '<option value="' + k + '">' + escapeHtml(AGENT_LABELS[k]) + '</option>')
        .join('');

      showDrawer({
        title: '新建对话',
        bodyHtml: '' +
          '<div class="form-group">' +
            '<label class="form-label" for="new-conv-title">对话标题</label>' +
            '<input type="text" class="form-control" id="new-conv-title" placeholder="新对话" value="新对话" />' +
          '</div>' +
          '<div class="form-group" style="margin-bottom:0;">' +
            '<label class="form-label" for="new-conv-agent">初始 Agent</label>' +
            '<select class="form-control" id="new-conv-agent">' + agentOptions + '</select>' +
            '<div class="form-hint">选择首个响应的 Agent 类型，决定对话初始路由。</div>' +
          '</div>',
        footerHtml: '' +
          '<button class="btn btn-ghost" id="new-conv-cancel">取消</button>' +
          '<button class="btn btn-primary" id="new-conv-create"><i data-lucide="plus"></i><span>创建</span></button>',
        onMount: (drawer) => {
          drawer.querySelector('#new-conv-cancel')?.addEventListener('click', () => closeDrawer());
          drawer.querySelector('#new-conv-create')?.addEventListener('click', () => this.handleCreateConversation());
        },
      });
    },

    // 处理新建对话
    async handleCreateConversation() {
      const titleEl = document.getElementById('new-conv-title');
      const agentEl = document.getElementById('new-conv-agent');
      const title = (titleEl && titleEl.value.trim()) || '新对话';
      const agentId = (agentEl && agentEl.value) || 'orchestrator';
      const btn = document.getElementById('new-conv-create');
      if (btn) btn.disabled = true;

      try {
        await API.createConversation(state.activeSessionId, title, agentId);
        closeDrawer();
        showToast('对话已创建', 'success');
        await this.loadConversations(state.activeSessionId);
      } catch (err) {
        showToast(err.message || '创建对话失败', 'error');
      } finally {
        if (btn) btn.disabled = false;
      }
    },

    // 关闭/删除对话确认
    confirmCloseConversation(conversationId) {
      showDrawer({
        title: '关闭对话',
        bodyHtml: '' +
          '<div class="flex items-start gap-md">' +
            '<div class="text-danger" data-lucide="alert-triangle" style="width:24px;height:24px;flex-shrink:0;"></div>' +
            '<div>' +
              '<p class="font-medium" style="color:var(--text-primary);margin-bottom:var(--space-sm);">确定要关闭并删除该对话吗？</p>' +
              '<p class="text-sm text-secondary">对话内所有消息将一并删除，且无法恢复。</p>' +
            '</div>' +
          '</div>',
        footerHtml: '' +
          '<button class="btn btn-secondary" data-action="cancel">取消</button>' +
          '<button class="btn btn-danger" data-action="confirm"><i data-lucide="trash-2"></i><span>确认删除</span></button>',
        onMount: (drawer) => {
          drawer.querySelector('[data-action="cancel"]')?.addEventListener('click', () => closeDrawer());
          drawer.querySelector('[data-action="confirm"]')?.addEventListener('click', async () => {
            try {
              await API.deleteConversation(conversationId);
              closeDrawer();
              showToast('对话已删除', 'success');
              if (state.activeConversationId === conversationId) {
                state.activeConversationId = null;
                state.messages = [];
              }
              await this.loadConversations(state.activeSessionId);
            } catch (err) {
              showToast(err.message || '删除失败', 'error');
            }
          });
        },
      });
    },

    // 重命名对话
    renameConversation(conversationId) {
      const conv = state.conversations.find((c) => c.id === conversationId);
      const currentTitle = (conv && conv.title) || '新对话';
      showDrawer({
        title: '重命名对话',
        bodyHtml: '' +
          '<div class="form-group" style="margin-bottom:0;">' +
            '<label class="form-label" for="rename-conv-title">对话标题</label>' +
            '<input type="text" class="form-control" id="rename-conv-title" value="' + escapeHtml(currentTitle) + '" />' +
          '</div>',
        footerHtml: '' +
          '<button class="btn btn-secondary" id="rename-cancel">取消</button>' +
          '<button class="btn btn-primary" id="rename-confirm"><i data-lucide="check"></i><span>保存</span></button>',
        onMount: (drawer) => {
          drawer.querySelector('#rename-cancel')?.addEventListener('click', () => closeDrawer());
          drawer.querySelector('#rename-confirm')?.addEventListener('click', async () => {
            const input = document.getElementById('rename-conv-title');
            const newTitle = (input && input.value.trim()) || currentTitle;
            try {
              await API.renameConversation(conversationId, newTitle);
              closeDrawer();
              showToast('对话已重命名', 'success');
              await this.loadConversations(state.activeSessionId);
            } catch (err) {
              showToast(err.message || '重命名失败', 'error');
            }
          });
        },
      });
    },

    /* ----------------------------------------------------------------------
       消息列表
       ---------------------------------------------------------------------- */

    // 加载对话消息
    async loadMessages(conversationId) {
      const msgEl = document.getElementById('session-messages');
      if (!msgEl) return;
      msgEl.innerHTML = '' +
        '<div class="session-empty">' +
          '<div class="spinner spinner--lg"></div>' +
          '<div class="session-empty__title">加载消息中…</div>' +
        '</div>';

      try {
        const data = await API.getConversationMessages(conversationId, 100);
        state.messages = (data && data.messages) || [];
        state.knownMessageIds = new Set(state.messages.map((m) => m.id));
        this.renderMessages();
      } catch (err) {
        msgEl.innerHTML = '' +
          '<div class="session-empty">' +
            '<div class="session-empty__icon text-danger" data-lucide="alert-triangle"></div>' +
            '<div class="session-empty__title">消息加载失败</div>' +
            '<p class="session-empty__desc">' + escapeHtml(err.message || '未知错误') + '</p>' +
          '</div>';
        refreshIcons(msgEl);
      }
    },

    // 渲染消息列表
    renderMessages() {
      const msgEl = document.getElementById('session-messages');
      if (!msgEl) return;

      if (state.messages.length === 0) {
        this.renderMessagesEmpty();
        return;
      }

      msgEl.innerHTML = state.messages.map((m) => this.messageHtml(m)).join('');
      refreshIcons(msgEl);
      this.scrollToBottom();

      // 绑定推理折叠
      msgEl.querySelectorAll('[data-reasoning-toggle]').forEach((el) => {
        el.addEventListener('click', () => {
          const wrapper = el.closest('.session-reasoning');
          if (wrapper) wrapper.classList.toggle('session-reasoning--open');
        });
      });
    },

    // 消息为空时的引导
    renderMessagesEmpty() {
      const msgEl = document.getElementById('session-messages');
      if (!msgEl) return;
      msgEl.innerHTML = '' +
        '<div class="session-empty">' +
          '<div class="session-empty__icon" data-lucide="message-circle"></div>' +
          '<div class="session-empty__title">开始对话</div>' +
          '<p class="session-empty__desc">在下方输入消息，选择 Agent 类型后发送。</p>' +
        '</div>';
      refreshIcons(msgEl);
    },

    // 单条消息 HTML
    messageHtml(m) {
      const role = m.role || 'assistant';
      const isUser = role === 'user';
      const agentId = m.agent_id || '';
      const color = agentColor(agentId);
      const label = agentLabel(agentId);
      const content = escapeHtml(m.content || '');
      const reasoning = m.reasoning || '';
      const isStreaming = !!m._streaming;

      // 推理面板：流式过程中即使推理为空也预留面板（便于实时填充）
      let reasoningHtml = '';
      if (reasoning || isStreaming) {
        const toggleLabel = isStreaming ? '思考中…' : '查看思考过程';
        reasoningHtml = '' +
          '<div class="session-reasoning' + (isStreaming ? ' session-reasoning--open' : '') + '">' +
            '<button class="session-reasoning__toggle" data-reasoning-toggle>' +
              '<i data-lucide="chevron-right"></i>' +
              (isStreaming ? '<span class="session-typing-dots"><span></span><span></span><span></span></span>' : '') +
              '<span>' + toggleLabel + '</span>' +
            '</button>' +
            '<div class="session-reasoning__body' + (isStreaming ? ' session-reasoning__body--streaming' : '') + '">' +
              escapeHtml(reasoning) +
            '</div>' +
          '</div>';
      }

      // 引用卡片
      let citationsHtml = '';
      const citations = m.citations || [];
      if (citations.length > 0) {
        citationsHtml = '' +
          '<div class="session-citations">' +
            '<div class="session-citations__title">' +
              '<i data-lucide="quote" style="width:12px;height:12px;"></i>' +
              '<span>引用 ' + citations.length + ' 条</span>' +
            '</div>' +
            '<div class="session-citations__grid">' +
              citations.map((c) => this.citationHtml(c)).join('') +
            '</div>' +
          '</div>';
      }

      // 流式光标：内容为空时显示打字指示器，有内容时显示闪烁光标
      let contentCursor = '';
      if (isStreaming) {
        contentCursor = content
          ? '<span class="session-streaming-cursor"></span>'
          : '<span class="session-typing-dots"><span></span><span></span><span></span></span>';
      }

      return '' +
        '<div class="session-message session-message--' + (isUser ? 'user' : 'assistant') + '" data-msg-id="' + escapeHtml(m.id || '') + '">' +
          '<div class="session-message__header">' +
            (isUser
              ? '<span class="session-message__role">你</span>'
              : '<span class="session-message__agent" style="background:' + hexToRgba(color, 0.15) + ';color:' + color + ';border:1px solid ' + hexToRgba(color, 0.3) + ';">' +
                  '<span style="width:6px;height:6px;border-radius:50%;background:' + color + ';"></span>' +
                  escapeHtml(label) +
                '</span>'
            ) +
            '<span class="session-message__role">' + escapeHtml(role) + '</span>' +
          '</div>' +
          '<div class="session-message__bubble">' + content + contentCursor + '</div>' +
          reasoningHtml +
          citationsHtml +
        '</div>';
    },

    // 引用卡片 HTML
    citationHtml(c) {
      const title = escapeHtml(c.title || '未命名文献');
      const snippet = escapeHtml(c.snippet || c.abstract || '');
      const url = c.url || c.link || '#';
      const domain = extractDomain(url);
      const favicon = 'https://www.google.com/s2/favicons?domain=' + encodeURIComponent(domain) + '&sz=32';
      return '' +
        '<a class="session-citation" href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">' +
          '<div class="session-citation__header">' +
            '<img class="session-citation__favicon" src="' + escapeHtml(favicon) + '" alt="" onerror="this.style.visibility=\'hidden\'" />' +
            '<span class="session-citation__domain">' + escapeHtml(domain) + '</span>' +
          '</div>' +
          '<div class="session-citation__title">' + title + '</div>' +
          (snippet ? '<div class="session-citation__snippet">' + snippet + '</div>' : '') +
        '</a>';
    },

    /* ----------------------------------------------------------------------
       输入区与发送
       ---------------------------------------------------------------------- */

    // 输入区 HTML
    inputAreaHtml() {
      const agentOptions = Object.keys(AGENT_LABELS)
        .map((k) => '<option value="' + k + '"' + (k === state.selectedAgent ? ' selected' : '') + '>' + escapeHtml(AGENT_LABELS[k]) + '</option>')
        .join('');
      return '' +
        '<div class="session-input">' +
          '<div class="session-input__toggles">' +
            '<button type="button" class="session-toggle' + (state.deepThinking ? ' session-toggle--active' : '') + '" id="toggle-deep-thinking" title="深度思考（思维链推理）" aria-pressed="' + (state.deepThinking ? 'true' : 'false') + '">' +
              '<i data-lucide="brain" style="width:13px;height:13px;"></i>' +
              '<span>深度思考</span>' +
            '</button>' +
            '<button type="button" class="session-toggle' + (state.webSearching ? ' session-toggle--active' : '') + '" id="toggle-web-search" title="联网搜索" aria-pressed="' + (state.webSearching ? 'true' : 'false') + '">' +
              '<i data-lucide="globe" style="width:13px;height:13px;"></i>' +
              '<span>联网搜索</span>' +
            '</button>' +
          '</div>' +
          '<div class="session-input__row">' +
            '<select class="session-agent-select" id="session-agent-select" title="选择 Agent">' + agentOptions + '</select>' +
            '<textarea class="session-input__textarea" id="session-input-text" placeholder="输入消息…（Ctrl/Cmd + Enter 发送）" rows="1"></textarea>' +
            '<button class="session-input__send" id="session-send-btn" type="button">' +
              '<i data-lucide="send"></i><span>发送</span>' +
            '</button>' +
          '</div>' +
          '<div class="session-input__hint">' +
            '<i data-lucide="info" style="width:12px;height:12px;"></i>' +
            '<span>切换标签完全隔离上下文 · 双击标签可重命名 · 流式输出实时展示推理过程</span>' +
          '</div>' +
        '</div>';
    },

    // 绑定输入区事件
    bindInputArea() {
      const ws = document.getElementById('session-workspace');
      if (!ws) return;
      const agentSelect = ws.querySelector('#session-agent-select');
      const textArea = ws.querySelector('#session-input-text');
      const sendBtn = ws.querySelector('#session-send-btn');
      const deepThinkingBtn = ws.querySelector('#toggle-deep-thinking');
      const webSearchBtn = ws.querySelector('#toggle-web-search');

      if (agentSelect) {
        agentSelect.addEventListener('change', () => {
          state.selectedAgent = agentSelect.value;
        });
      }
      if (textArea) {
        // 自适应高度
        textArea.addEventListener('input', () => {
          textArea.style.height = 'auto';
          textArea.style.height = Math.min(textArea.scrollHeight, 160) + 'px';
        });
        // 快捷键发送
        textArea.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            this.handleSend();
          }
        });
      }
      if (sendBtn) {
        sendBtn.addEventListener('click', () => this.handleSend());
      }
      // v9.0 Task 7：深度思考开关
      if (deepThinkingBtn) {
        deepThinkingBtn.addEventListener('click', () => {
          state.deepThinking = !state.deepThinking;
          deepThinkingBtn.classList.toggle('session-toggle--active', state.deepThinking);
          deepThinkingBtn.setAttribute('aria-pressed', state.deepThinking ? 'true' : 'false');
        });
      }
      // v9.0 Task 7：联网搜索开关
      if (webSearchBtn) {
        webSearchBtn.addEventListener('click', () => {
          state.webSearching = !state.webSearching;
          webSearchBtn.classList.toggle('session-toggle--active', state.webSearching);
          webSearchBtn.setAttribute('aria-pressed', state.webSearching ? 'true' : 'false');
        });
      }
    },

    // 处理发送消息
    async handleSend() {
      if (state.sending || state.streaming) return;
      if (!state.activeSessionId || !state.activeConversationId) {
        showToast('请先选择会话与对话', 'warning');
        return;
      }
      const textArea = document.getElementById('session-input-text');
      const sendBtn = document.getElementById('session-send-btn');
      const content = (textArea && textArea.value.trim()) || '';
      if (!content) {
        showToast('请输入消息内容', 'warning');
        if (textArea) textArea.focus();
        return;
      }

      const agentId = state.selectedAgent;
      state.sending = true;
      if (sendBtn) sendBtn.disabled = true;
      if (textArea) {
        textArea.value = '';
        textArea.style.height = 'auto';
      }

      // 立即在界面追加用户消息
      const userMsg = {
        id: 'temp-' + Date.now(),
        role: 'user',
        content: content,
        agent_id: '',
        reasoning: '',
        citations: [],
      };
      state.messages.push(userMsg);
      this.renderMessages();

      try {
        // v9.0 Task 7：通过 SSE 流式端点发送，后端负责持久化用户消息与助手回复
        await this.startSseStreaming(agentId, content);
      } catch (err) {
        showToast(err.message || '发送失败', 'error');
        this.finalizeStreaming();
      } finally {
        state.sending = false;
        if (sendBtn) sendBtn.disabled = false;
      }
    },

    /* ----------------------------------------------------------------------
       流式输出（v9.0 Task 7：SSE 实时流式渲染）
       ---------------------------------------------------------------------- */

    // 启动 SSE 流式接收：通过 fetch + ReadableStream 实时解析 SSE 事件
    async startSseStreaming(agentId, message) {
      this.stopStreaming();
      state.streaming = true;
      state.streamStart = Date.now();

      // 插入助手占位消息（带流式标记）
      const placeholder = {
        id: 'stream-' + Date.now(),
        role: 'assistant',
        content: '',
        agent_id: agentId,
        reasoning: '',
        citations: [],
        _streaming: true,
      };
      state.messages.push(placeholder);
      this.renderMessages();

      // 创建中断控制器
      state.streamAbortController = new AbortController();

      const cid = state.activeConversationId;
      const url = '/api/conversations/' + encodeURIComponent(cid) + '/stream';
      const payload = {
        message: message,
        agent_id: agentId,
        deep_thinking: state.deepThinking,
        web_search: state.webSearching,
      };

      let response;
      try {
        response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          },
          body: JSON.stringify(payload),
          signal: state.streamAbortController.signal,
        });
      } catch (err) {
        if (err.name === 'AbortError') {
          this.finalizeStreaming();
          return;
        }
        throw new Error('流式请求失败：' + (err.message || err));
      }

      if (!response.ok) {
        let msg = '请求失败（HTTP ' + response.status + '）';
        try {
          const errData = await response.json();
          msg = errData.detail || errData.error || errData.message || msg;
        } catch (_) {}
        throw new Error(msg);
      }

      // 获取流式读取器
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      const placeholderIdx = state.messages.length - 1;

      // 缓存 DOM 引用，避免每个 chunk 都重新查询
      state.streamDomRefs = this.cacheStreamDomRefs(placeholder.id);

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // SSE 事件以双换行分隔
          const lines = buffer.split('\n\n');
          buffer = lines.pop(); // 保留最后不完整的片段

          for (const line of lines) {
            await this.handleSseEvent(line, placeholderIdx);
          }
        }
        // 处理缓冲区剩余内容
        if (buffer.trim()) {
          await this.handleSseEvent(buffer, placeholderIdx);
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          showToast('流式接收异常：' + (err.message || err), 'error');
        }
      } finally {
        this.finalizeStreaming();
      }
    },

    // 处理单个 SSE 事件文本
    async handleSseEvent(eventText, placeholderIdx) {
      // 一个事件可能包含多行 data:，合并为完整 JSON
      const dataLines = eventText
        .split('\n')
        .filter((l) => l.startsWith('data: '))
        .map((l) => l.slice(6));
      if (dataLines.length === 0) return;

      const dataStr = dataLines.join('\n');
      let payload;
      try {
        payload = JSON.parse(dataStr);
      } catch (_) {
        return;
      }

      const eventType = payload.type || '';
      const msg = state.messages[placeholderIdx];
      if (!msg) return;

      if (eventType === 'reasoning') {
        msg.reasoning = (msg.reasoning || '') + (payload.content || '');
        this.updateStreamReasoningDom(msg.reasoning);
        this.scrollToBottom();
      } else if (eventType === 'content') {
        msg.content = (msg.content || '') + (payload.content || '');
        this.updateStreamContentDom(msg.content);
        this.scrollToBottom();
      } else if (eventType === 'done') {
        // 完成事件：用聚合结果覆盖
        msg.content = payload.content || msg.content || '';
        msg.reasoning = payload.reasoning || msg.reasoning || '';
        msg.citations = payload.citations || [];
        msg._streaming = false;
        // 若后端返回了真实消息 ID（通过后续刷新获取），此处保留临时 ID
        this.updateStreamContentDom(msg.content);
        this.updateStreamReasoningDom(msg.reasoning);
        // 若有引用，尝试单独拉取以获取完整字段
        if (msg.citations.length === 0) {
          // done 事件未带引用，保持空，后续可由用户刷新
        }
      } else if (eventType === 'error') {
        msg.content = (msg.content ? msg.content + '\n' : '') + '⚠️ ' + (payload.content || '未知错误');
        msg._streaming = false;
        this.updateStreamContentDom(msg.content);
        showToast(payload.content || '流式响应错误', 'error');
      }
    },

    // 缓存流式消息的 DOM 引用（避免每次 chunk 都查询 DOM）
    cacheStreamDomRefs(msgId) {
      const msgEl = document.querySelector('[data-msg-id="' + msgId + '"]');
      if (!msgEl) return null;
      return {
        root: msgEl,
        bubble: msgEl.querySelector('.session-message__bubble'),
        reasoningBody: msgEl.querySelector('.session-reasoning__body'),
        reasoningWrap: msgEl.querySelector('.session-reasoning'),
      };
    },

    // 实时更新内容气泡（避免全量重渲染）
    updateStreamContentDom(content) {
      const refs = state.streamDomRefs;
      if (!refs || !refs.bubble) {
        // DOM 引用丢失，回退到全量渲染
        this.renderMessages();
        return;
      }
      refs.bubble.innerHTML = escapeHtml(content) + '<span class="session-streaming-cursor"></span>';
    },

    // 实时更新推理面板（避免全量重渲染）
    updateStreamReasoningDom(reasoning) {
      const refs = state.streamDomRefs;
      if (!reasoning) return;
      if (!refs || !refs.reasoningBody) {
        // 推理面板尚未渲染，需要全量渲染以创建面板
        this.renderMessages();
        state.streamDomRefs = this.cacheStreamDomRefs(state.messages[state.messages.length - 1].id);
        return;
      }
      refs.reasoningBody.innerHTML = escapeHtml(reasoning);
      // 流式过程中自动展开推理面板
      if (refs.reasoningWrap) {
        refs.reasoningWrap.classList.add('session-reasoning--open');
      }
    },

    // 流式结束：清理占位标记与 DOM 引用
    finalizeStreaming() {
      state.messages.forEach((m) => { delete m._streaming; });
      state.streamDomRefs = null;
      state.streamAbortController = null;
      state.streaming = false;
      this.renderMessages();
    },

    // 停止流式（中断 fetch 与清理）
    stopStreaming() {
      if (state.streamAbortController) {
        try { state.streamAbortController.abort(); } catch (_) {}
        state.streamAbortController = null;
      }
      if (state.streamTimer) {
        clearInterval(state.streamTimer);
        state.streamTimer = null;
      }
      state.streaming = false;
    },

    // 滚动到底部
    scrollToBottom() {
      const msgEl = document.getElementById('session-messages');
      if (msgEl) msgEl.scrollTop = msgEl.scrollHeight;
    },

    /* ----------------------------------------------------------------------
       Agent 列表
       ---------------------------------------------------------------------- */

    async loadAgents() {
      try {
        const data = await API.getAgents();
        state.agents = (data && data.agents) || [];
      } catch (_) {
        // 静默失败，使用内置 Agent 配置
      }
    },

    /* ----------------------------------------------------------------------
       会话详情与删除（保留原有功能）
       ---------------------------------------------------------------------- */

    // 会话详情抽屉
    async showSessionDetail(sessionId) {
      const { drawer } = showDrawer({
        title: '会话详情',
        bodyHtml: '<div class="loading-overlay"><div class="spinner spinner--lg"></div><div>正在加载会话详情…</div></div>',
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
          body.innerHTML = this.sessionListErrorHtml(err);
          refreshIcons(drawer);
        }
        showToast(err.message || '加载详情失败', 'error');
      }
    },

    // 详情抽屉主体
    detailBodyHtml(session, proposals) {
      return '' +
        '<div class="flex flex-col gap-md">' +
          '<div>' +
            '<div class="text-xs text-muted mb-sm" style="letter-spacing:0.08em;text-transform:uppercase;">论题标题</div>' +
            '<div class="text-display" style="font-size:1.15rem;color:var(--text-primary);line-height:1.4;">' + escapeHtml(session.title || '未命名会话') + '</div>' +
          '</div>' +
          '<div class="flex items-center gap-sm flex-wrap">' + statusBadge(session.status) + '</div>' +
          '<div class="grid grid--2" style="gap:var(--space-md);">' +
            '<div><div class="text-xs text-muted mb-xs">会话 ID</div><div class="text-mono text-sm" style="color:var(--text-primary);">' + escapeHtml(session.id || '—') + '</div></div>' +
            '<div><div class="text-xs text-muted mb-xs">创建时间</div><div class="text-sm">' + formatDate(session.created_at) + '</div></div>' +
            '<div><div class="text-xs text-muted mb-xs">更新时间</div><div class="text-sm">' + formatDate(session.updated_at) + '</div></div>' +
            '<div><div class="text-xs text-muted mb-xs">导师信息</div><div class="text-sm">' + escapeHtml(session.mentor_info || '—') + '</div></div>' +
          '</div>' +
          '<hr class="divider" />' +
          '<div>' +
            '<div class="flex items-center justify-between mb-md">' +
              '<h4 class="text-display" style="font-size:1rem;">关联论题</h4>' +
              '<span class="badge badge--accent">' + proposals.length + ' 条</span>' +
            '</div>' +
            (proposals.length === 0
              ? '<div class="empty-state" style="padding:var(--space-lg);"><div class="empty-state__icon" data-lucide="file-text"></div><div class="empty-state__title">暂无论题</div><p class="empty-state__desc">该会话尚未生成论题。</p></div>'
              : '<div class="list">' + proposals.map((p) => this.proposalItemHtml(p)).join('') + '</div>'
            ) +
          '</div>' +
        '</div>';
    },

    proposalItemHtml(p) {
      const score = typeof p.confidence_score === 'number' ? Math.round(p.confidence_score * 100) : null;
      return '' +
        '<div class="list-item flex-col" style="align-items:stretch;">' +
          '<div class="text-display font-semibold" style="color:var(--text-primary);font-size:0.9rem;line-height:1.4;">' + escapeHtml(p.title || '未命名论题') + '</div>' +
          '<div class="flex items-center gap-sm flex-wrap mt-sm">' +
            (score !== null ? '<span class="badge badge--default">置信度 ' + score + '%</span>' : '') +
            (p.auto_rewritten ? '<span class="badge badge--accent">已改写</span>' : '') +
            '<span class="text-xs text-muted">' + formatDate(p.created_at, false) + '</span>' +
          '</div>' +
        '</div>';
    },

    // 删除会话确认
    confirmDeleteSession(sessionId) {
      showDrawer({
        title: '删除会话',
        bodyHtml: '' +
          '<div class="flex items-start gap-md">' +
            '<div class="text-danger" data-lucide="alert-triangle" style="width:24px;height:24px;flex-shrink:0;"></div>' +
            '<div>' +
              '<p class="font-medium" style="color:var(--text-primary);margin-bottom:var(--space-sm);">确定要删除该会话吗？</p>' +
              '<p class="text-sm text-secondary">删除后无法恢复，关联的对话与论题记录可能仍保留。</p>' +
            '</div>' +
          '</div>',
        footerHtml: '' +
          '<button class="btn btn-secondary" data-action="cancel">取消</button>' +
          '<button class="btn btn-danger" data-action="confirm"><i data-lucide="trash-2"></i><span>确认删除</span></button>',
        onMount: (drawer) => {
          drawer.querySelector('[data-action="cancel"]')?.addEventListener('click', () => closeDrawer());
          drawer.querySelector('[data-action="confirm"]')?.addEventListener('click', async () => {
            const btn = drawer.querySelector('[data-action="confirm"]');
            if (btn) btn.disabled = true;
            try {
              await API.deleteSession(sessionId);
              try { sessionStorage.removeItem(SESSIONS_CACHE_KEY); } catch (_) {}
              closeDrawer();
              showToast('会话已删除', 'success');
              if (state.activeSessionId === sessionId) {
                state.activeSessionId = null;
                state.activeConversationId = null;
                const ws = document.getElementById('session-workspace');
                if (ws) ws.innerHTML = this.workspaceEmptyHtml();
                refreshIcons(ws);
              }
              this.loadSessions();
            } catch (err) {
              if (btn) btn.disabled = false;
              showToast(err.message || '删除失败', 'error');
            }
          });
        },
      });
    },
  };

  /* ----------------------------------------------------------------------
     工具函数
     ---------------------------------------------------------------------- */

  // hex 转 rgba
  function hexToRgba(hex, alpha) {
    const h = (hex || '#4F46E5').replace('#', '');
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + (alpha || 0.15) + ')';
  }

  // 从 URL 提取域名
  function extractDomain(url) {
    if (!url) return 'unknown';
    try {
      const u = new URL(url);
      return u.hostname || 'unknown';
    } catch (_) {
      return String(url).split('/')[0] || 'unknown';
    }
  }

  // sleep
  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
})();
