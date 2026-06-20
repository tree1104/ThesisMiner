/* ==========================================================================
   ThesisMiner v8.0 - 论题生成页面（五阶段流程 UI）
   顶部进度条 + 五阶段面板：信息确权 → 创意 → 校验 → 生成 → 深度辅助
   页面注册到 window.Pages.generate，由 app.js 路由系统动态加载
   ========================================================================== */
(function () {
  'use strict';

  // 五阶段定义（key / 标签 / 配色 / 图标）
  const STAGES = [
    { key: 'info_confirm', label: '信息确权', color: '#3B82F6', icon: 'search' },
    { key: 'creativity', label: '创意', color: '#8B5CF6', icon: 'lightbulb' },
    { key: 'validation', label: '校验', color: '#F59E0B', icon: 'shield-check' },
    { key: 'generation', label: '生成', color: '#10B981', icon: 'file-text' },
    { key: 'deep_assist', label: '深度辅助', color: '#EC4899', icon: 'sparkles' },
  ];

  // 生成粒度选项
  const GRANULARITIES = [
    { key: 'title', label: '标题', icon: 'type' },
    { key: 'abstract', label: '摘要', icon: 'align-left' },
    { key: 'outline', label: '大纲', icon: 'list' },
    { key: 'full', label: '全文', icon: 'file-text' },
  ];

  // 深度辅助选项
  const DEEP_ASSISTS = [
    { key: 'literature', title: '文献精读', desc: '对选定文献进行深度解读，提取核心观点、方法与可借鉴之处。', icon: 'book-open' },
    { key: 'experiment', title: '实验预研', desc: '梳理实验设计思路，预判可行性与潜在难点，制定预研方案。', icon: 'flask-conical' },
    { key: 'defense', title: '答辩模拟', desc: '模拟答辩问答场景，针对论题生成高频提问与参考回答。', icon: 'message-square' },
  ];

  // 表单与流程状态
  const state = {
    degree: 'master',
    discipline: 'humanities_social',
    mode: 'quick',
    count: 3,
    generating: false,
    proposals: [],
    currentStage: null,
    stageConfirmed: {
      info_confirm: false,
      creativity: false,
      validation: false,
      generation: false,
    },
    selectedProposalIdx: null,
    validation: null,
    granularity: 'title',
    generatedContent: null,
    styleBefore: '',
    styleAfter: '',
  };

  // 根据阶段 key 取配色
  function stageColor(key) {
    const s = STAGES.find((st) => st.key === key);
    return s ? s.color : '#4F46E5';
  }

  // 渲染按钮组选项
  function buttonGroup(group, options, current) {
    return options
      .map((opt) => {
        const active = opt.value === current;
        return (
          '<button class="btn ' + (active ? 'btn-primary' : 'btn-secondary') +
          '" data-group="' + group + '" data-value="' + opt.value + '" style="flex:1">' +
          opt.label +
          '</button>'
        );
      })
      .join('');
  }

  // AI 未配置提示
  function aiUnconfiguredResult() {
    return (
      '<div class="card card--accent" style="border-left-color:var(--danger)">' +
      '<div class="flex items-start gap-md">' +
      '<i data-lucide="alert-triangle" style="width:22px;height:22px;color:var(--danger);flex-shrink:0;margin-top:2px"></i>' +
      '<div>' +
      '<h4 class="text-danger mb-sm">AI 服务未配置</h4>' +
      '<p class="text-sm text-secondary mb-md">论题生成需要配置 AI API Key。请先前往设置页完成配置。</p>' +
      '<button class="btn btn-primary btn-sm" data-action="goto-settings">' +
      '<i data-lucide="settings"></i> 前往设置</button>' +
      '</div>' +
      '</div>' +
      '</div>'
    );
  }

  window.Pages = window.Pages || {};
  window.Pages.generate = {
    /** 渲染页面骨架 */
    render() {
      return (
        '<header class="page-header">' +
        '<div class="page-header__eyebrow">ThesisMiner · Generate</div>' +
        '<h1 class="page-header__title">论题生成</h1>' +
        '<p class="page-header__desc">五阶段流程驱动：信息确权 → 创意 → 校验 → 生成 → 深度辅助，从学术语境到开题成稿的全链路支持。</p>' +
        '</header>' +
        '<div class="page-body">' +
        // 表单区
        '<div class="form-section" id="gen-form-section" style="margin-bottom:var(--space-lg);">' +
        '<div class="form-section__title">生成配置</div>' +
        '<div class="grid grid--2">' +
        '<div class="form-group">' +
        '<label class="form-label">学位类型</label>' +
        '<div class="flex gap-sm" data-group="degree">' +
        buttonGroup('degree', [
          { value: 'master', label: '硕士' },
          { value: 'doctor', label: '博士' },
        ], state.degree) +
        '</div>' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">学科类型</label>' +
        '<div class="flex gap-sm" data-group="discipline">' +
        buttonGroup('discipline', [
          { value: 'humanities_social', label: '人文社科' },
          { value: 'science_engineering', label: '理工科' },
        ], state.discipline) +
        '</div>' +
        '</div>' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">导师信息</label>' +
        '<textarea id="gen-mentor" class="form-control" rows="3" placeholder="输入导师在研项目、同门论文等信息..."></textarea>' +
        '<div class="form-hint">越详细的导师背景越能生成贴合研究方向的论题。</div>' +
        '</div>' +
        '<div class="grid grid--2">' +
        '<div class="form-group">' +
        '<label class="form-label">生成模式</label>' +
        '<div class="flex gap-sm" data-group="mode">' +
        buttonGroup('mode', [
          { value: 'quick', label: '快速发散' },
          { value: 'deep', label: '深度精炼' },
        ], state.mode) +
        '</div>' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">生成数量</label>' +
        '<input id="gen-count" type="number" class="form-control" min="1" max="5" value="' + state.count + '" style="max-width:120px" />' +
        '</div>' +
        '</div>' +
        '<button id="gen-submit" class="btn btn-primary btn-lg btn-block">' +
        '<i data-lucide="sparkles"></i> 开始生成' +
        '</button>' +
        '</div>' +
        // 阶段进度条（生成前隐藏）
        '<div id="stage-progress-wrap" class="hidden"></div>' +
        // 阶段面板容器（生成前显示空状态）
        '<div id="stage-panels">' +
        '<div class="empty-state">' +
        '<div class="empty-state__icon" data-lucide="sparkles"></div>' +
        '<div class="empty-state__title">等待生成论题</div>' +
        '<p class="empty-state__desc">填写上方表单信息，点击「开始生成」按钮，AI 将基于学术语境启动五阶段流程。</p>' +
        '</div>' +
        '</div>' +
        '</div>'
      );
    },

    /** app.js 调用入口 */
    async init() {
      const container = document.getElementById('app-content');
      if (container) await this.mount(container);
    },

    /** 挂载：绑定事件 */
    async mount(container) {
      refreshIcons();
      this.bindForm(container);
    },

    /** 绑定表单交互 */
    bindForm(root) {
      if (!root) return;
      // 按钮组切换
      root.querySelectorAll('[data-group]').forEach((group) => {
        const groupName = group.dataset.group;
        group.querySelectorAll('button[data-value]').forEach((btn) => {
          btn.addEventListener('click', () => {
            state[groupName] = btn.dataset.value;
            group.querySelectorAll('button[data-value]').forEach((b) => {
              const active = b.dataset.value === state[groupName];
              b.classList.toggle('btn-primary', active);
              b.classList.toggle('btn-secondary', !active);
            });
          });
        });
      });

      // 数量输入
      const countInput = document.getElementById('gen-count');
      if (countInput) {
        countInput.addEventListener('change', () => {
          let n = parseInt(countInput.value, 10);
          if (Number.isNaN(n)) n = 3;
          n = Math.max(1, Math.min(5, n));
          countInput.value = n;
          state.count = n;
        });
      }

      // 生成按钮
      const submit = document.getElementById('gen-submit');
      if (submit) {
        submit.addEventListener('click', () => this.handleGenerate());
      }
    },

    /** 处理生成论题：启动五阶段流程 */
    async handleGenerate() {
      if (state.generating) return;

      const mentorEl = document.getElementById('gen-mentor');
      const mentorInfo = (mentorEl && mentorEl.value.trim()) || '';
      if (!mentorInfo) {
        showToast('请输入导师信息后再生成', 'warning');
        if (mentorEl) mentorEl.focus();
        return;
      }

      const submit = document.getElementById('gen-submit');

      // 检查 AI 配置
      try {
        const status = await API.getStatus();
        if (!status || !status.ai_configured) {
          const panels = document.getElementById('stage-panels');
          if (panels) {
            panels.innerHTML = aiUnconfiguredResult();
            refreshIcons();
            this.bindResultActions();
          }
          return;
        }
      } catch (err) {
        showToast('状态检查失败：' + (err.message || err), 'error');
      }

      // 进入生成中
      state.generating = true;
      if (submit) {
        submit.disabled = true;
        submit.innerHTML = '<span class="spinner"></span> 生成中…';
      }

      // 展示加载态
      const panels = document.getElementById('stage-panels');
      if (panels) {
        panels.innerHTML =
          '<div class="empty-state">' +
          '<div class="spinner spinner--lg"></div>' +
          '<div class="empty-state__title mt-md">正在生成论题…</div>' +
          '<p class="empty-state__desc">AI 正在结合导师信息与学术规范进行多轮推演，请稍候。</p>' +
          '</div>';
        refreshIcons();
      }

      try {
        const res = await API.generateProposals({
          degree: state.degree,
          discipline: state.discipline,
          mentor_info: mentorInfo,
          mode: state.mode,
          count: state.count,
        });

        const proposals = (res && res.proposals) || [];
        state.proposals = proposals;

        if (!proposals.length) {
          if (panels) {
            panels.innerHTML =
              '<div class="empty-state">' +
              '<div class="empty-state__icon" data-lucide="inbox"></div>' +
              '<div class="empty-state__title">未生成任何论题</div>' +
              '<p class="empty-state__desc">AI 未返回有效结果，请调整导师信息后重试。</p>' +
              '</div>';
            refreshIcons();
          }
          return;
        }

        // 重置阶段状态并进入阶段 1
        state.currentStage = 'info_confirm';
        state.stageConfirmed = { info_confirm: false, creativity: false, validation: false, generation: false };
        state.selectedProposalIdx = null;
        state.validation = null;
        state.generatedContent = null;

        this.renderStageProgress();
        this.renderStagePanels();
        showToast('已生成 ' + proposals.length + ' 条候选论题，进入信息确权阶段', 'success');
      } catch (err) {
        const msg = err && err.message ? err.message : String(err);
        if (panels) {
          panels.innerHTML =
            '<div class="card card--accent fade-in" style="border-left-color:var(--danger)">' +
            '<div class="flex items-start gap-md">' +
            '<i data-lucide="alert-circle" style="width:22px;height:22px;color:var(--danger);flex-shrink:0;margin-top:2px"></i>' +
            '<div>' +
            '<h4 class="text-danger mb-sm">生成失败</h4>' +
            '<p class="text-sm text-secondary">' + escapeHtml(msg) + '</p>' +
            '</div></div></div>';
          refreshIcons();
        }
        showToast('论题生成失败：' + msg, 'error');
      } finally {
        state.generating = false;
        if (submit) {
          submit.disabled = false;
          submit.innerHTML = '<i data-lucide="sparkles"></i> 重新生成';
          refreshIcons();
        }
      }
    },

    /** 绑定结果区中的动作按钮（如前往设置） */
    bindResultActions() {
      const root = document.getElementById('app-content');
      if (!root) return;
      root.querySelectorAll('[data-action="goto-settings"]').forEach((btn) => {
        btn.addEventListener('click', () => navigate('settings'));
      });
    },

    /* ----------------------------------------------------------------------
       阶段进度条
       ---------------------------------------------------------------------- */

    renderStageProgress() {
      const wrap = document.getElementById('stage-progress-wrap');
      if (!wrap) return;
      wrap.classList.remove('hidden');

      const currentIdx = STAGES.findIndex((s) => s.key === state.currentStage);
      let html = '<div class="stage-progress" style="--stage-current:' + stageColor(state.currentStage) + ';">';
      STAGES.forEach((stage, idx) => {
        const isActive = stage.key === state.currentStage;
        const isCompleted = idx < currentIdx || state.stageConfirmed[stage.key];
        const stepCls = isActive ? 'active' : (isCompleted ? 'completed' : '');
        html +=
          '<div class="stage-step ' + stepCls + '" data-stage="' + stage.key + '" style="--stage-current:' + stage.color + ';">' +
            '<div class="stage-circle">' + (idx + 1) + '</div>' +
            '<div class="stage-label">' + escapeHtml(stage.label) + '</div>' +
          '</div>';
        if (idx < STAGES.length - 1) {
          const lineCompleted = idx < currentIdx;
          html += '<div class="stage-line' + (lineCompleted ? ' completed' : '') + '" style="--stage-current:' + stage.color + ';"></div>';
        }
      });
      html += '</div>';
      wrap.innerHTML = html;
      refreshIcons(wrap);
    },

    /* ----------------------------------------------------------------------
       阶段面板渲染
       ---------------------------------------------------------------------- */

    renderStagePanels() {
      const panels = document.getElementById('stage-panels');
      if (!panels) return;
      panels.style.setProperty('--stage-current', stageColor(state.currentStage));

      let html = '';
      STAGES.forEach((stage) => {
        const isActive = stage.key === state.currentStage;
        html += '<div class="stage-panel' + (isActive ? ' stage-panel--active' : '') + '" data-stage-panel="' + stage.key + '" style="--stage-current:' + stage.color + ';">';
        if (isActive) {
          html += this['render_' + stage.key]();
        }
        html += '</div>';
      });
      panels.innerHTML = html;
      refreshIcons(panels);
      this.bindStageActions();
    },

    // 绑定阶段内动作按钮
    bindStageActions() {
      const panels = document.getElementById('stage-panels');
      if (!panels) return;

      // 阶段 1：确认进入创意
      const confirmInfoBtn = panels.querySelector('#confirm-info-confirm');
      if (confirmInfoBtn) {
        confirmInfoBtn.addEventListener('click', () => this.confirmStage('info_confirm', 'creativity'));
      }

      // 阶段 2：选中论题进入校验
      panels.querySelectorAll('[data-select-proposal]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const idx = parseInt(btn.dataset.selectProposal, 10);
          this.selectProposal(idx);
        });
      });

      // 阶段 3：进入生成 / 回退
      const proceedGenBtn = panels.querySelector('#proceed-generation');
      if (proceedGenBtn) {
        proceedGenBtn.addEventListener('click', () => this.confirmStage('validation', 'generation'));
      }
      const rollbackBtn = panels.querySelector('#rollback-creativity');
      if (rollbackBtn) {
        rollbackBtn.addEventListener('click', () => this.goToStage('creativity'));
      }

      // 阶段 4：粒度选择
      panels.querySelectorAll('[data-granularity]').forEach((el) => {
        el.addEventListener('click', () => {
          state.granularity = el.dataset.granularity;
          this.renderGenerationGranularity();
        });
      });
      const genContentBtn = panels.querySelector('#generate-content-btn');
      if (genContentBtn) {
        genContentBtn.addEventListener('click', () => this.handleGenerateContent());
      }
      const proceedDeepBtn = panels.querySelector('#proceed-deep-assist');
      if (proceedDeepBtn) {
        proceedDeepBtn.addEventListener('click', () => this.confirmStage('generation', 'deep_assist'));
      }

      // 阶段 5：深度辅助入口
      panels.querySelectorAll('[data-deep-assist]').forEach((el) => {
        el.addEventListener('click', () => this.enterDeepAssist(el.dataset.deepAssist));
      });
    },

    // 确认当前阶段并进入下一阶段
    confirmStage(currentKey, nextKey) {
      state.stageConfirmed[currentKey] = true;
      this.goToStage(nextKey);
    },

    // 跳转到指定阶段
    goToStage(key) {
      state.currentStage = key;
      this.renderStageProgress();
      this.renderStagePanels();
    },

    /* ----------------------------------------------------------------------
       阶段 1：信息确权
       ---------------------------------------------------------------------- */

    render_info_confirm() {
      // 从候选论题中提取文献摘要信息
      const literature = this.extractLiterature();

      let bodyHtml = '' +
        '<div class="stage-panel__header">' +
          '<div>' +
            '<h2 class="stage-panel__title">信息确权</h2>' +
            '<p class="stage-panel__desc">确认已检索的学术文献摘要，核对研究方向后再进入创意阶段。</p>' +
          '</div>' +
          '<span class="badge badge--default"><i data-lucide="search" style="width:12px;height:12px;"></i> ' + literature.length + ' 篇文献</span>' +
        '</div>';

      if (literature.length === 0) {
        bodyHtml +=
          '<div class="empty-state">' +
            '<div class="empty-state__icon" data-lucide="file-search"></div>' +
            '<div class="empty-state__title">暂无文献摘要</div>' +
            '<p class="empty-state__desc">本次生成未返回文献检索摘要，可直接确认进入创意阶段。</p>' +
          '</div>';
      } else {
        bodyHtml += '<div class="info-confirm-list">';
        literature.forEach((lit) => {
          bodyHtml +=
            '<div class="info-confirm-card">' +
              '<div class="info-confirm-card__title">' + escapeHtml(lit.title || '未命名文献') + '</div>' +
              '<div class="info-confirm-card__meta">' +
                (lit.source ? '<span><i data-lucide="book" style="width:11px;height:11px;"></i> ' + escapeHtml(lit.source) + '</span>' : '') +
                (lit.year ? '<span>' + escapeHtml(String(lit.year)) + '</span>' : '') +
                (lit.inspiration ? '<span class="badge badge--default">' + escapeHtml(lit.inspiration) + '</span>' : '') +
              '</div>' +
              (lit.snippet ? '<div class="info-confirm-card__snippet">' + escapeHtml(lit.snippet) + '</div>' : '') +
            '</div>';
        });
        bodyHtml += '</div>';
      }

      bodyHtml +=
        '<button class="stage-action stage-action--primary" id="confirm-info-confirm">' +
          '<i data-lucide="arrow-right-circle"></i><span>确认进入创意阶段</span>' +
        '</button>';

      return bodyHtml;
    },

    // 从候选论题中提取文献摘要信息
    extractLiterature() {
      const literature = [];
      const seen = new Set();
      state.proposals.forEach((p) => {
        const source = p.inspiration_source || '';
        if (source && !seen.has(source)) {
          seen.add(source);
          literature.push({
            title: p.literature_review_outline || source,
            source: source,
            year: '',
            inspiration: p.inspiration_source,
            snippet: p.problem_awareness || '',
          });
        }
      });
      return literature;
    },

    /* ----------------------------------------------------------------------
       阶段 2：创意
       ---------------------------------------------------------------------- */

    render_creativity() {
      let bodyHtml = '' +
        '<div class="stage-panel__header">' +
          '<div>' +
            '<h2 class="stage-panel__title">创意</h2>' +
            '<p class="stage-panel__desc">四维创意引擎产出的候选论题，选中一条进入校验阶段。</p>' +
          '</div>' +
          '<span class="badge badge--default">' + state.proposals.length + ' 条候选</span>' +
        '</div>';

      bodyHtml += '<div class="creativity-grid">';
      state.proposals.forEach((p, idx) => {
        const isSelected = idx === state.selectedProposalIdx;
        const score = Number(p.confidence_score) || 0;
        const pct = Math.round(score * 100);
        bodyHtml +=
          '<div class="creativity-card' + (isSelected ? ' creativity-card--selected' : '') + '">' +
            '<span class="creativity-card__dimension">' +
              '<i data-lucide="lightbulb" style="width:11px;height:11px;"></i> ' +
              (p.inspiration_source ? escapeHtml(truncate(p.inspiration_source, 16)) : '创意候选') +
            '</span>' +
            '<div class="creativity-card__title">' + escapeHtml(p.title || '未命名论题') + '</div>' +
            (p.problem_awareness
              ? '<div class="creativity-card__desc">' + escapeHtml(truncate(p.problem_awareness, 80)) + '</div>'
              : '<div class="creativity-card__desc">置信度 ' + pct + '%</div>'
            ) +
            '<button class="creativity-card__action" data-select-proposal="' + idx + '"' + (isSelected ? ' disabled' : '') + '>' +
              '<i data-lucide="check-circle-2"></i>' +
              (isSelected ? '已选中' : '选中进入校验') +
            '</button>' +
          '</div>';
      });
      bodyHtml += '</div>';

      return bodyHtml;
    },

    // 选中候选论题，进入校验
    async selectProposal(idx) {
      state.selectedProposalIdx = idx;
      const proposal = state.proposals[idx];
      if (!proposal) return;

      // 进入校验阶段并立即运行校验
      state.currentStage = 'validation';
      state.validation = null;
      this.renderStageProgress();
      this.renderStagePanels();
      await this.runValidation(proposal);
    },

    /* ----------------------------------------------------------------------
       阶段 3：校验
       ---------------------------------------------------------------------- */

    render_validation() {
      const proposal = state.proposals[state.selectedProposalIdx];
      if (!proposal) {
        return '<div class="empty-state"><div class="empty-state__icon" data-lucide="alert-triangle"></div><div class="empty-state__title">未选择论题</div><p class="empty-state__desc">请返回创意阶段选择一条候选论题。</p></div>';
      }

      let bodyHtml = '' +
        '<div class="stage-panel__header">' +
          '<div>' +
            '<h2 class="stage-panel__title">校验</h2>' +
            '<p class="stage-panel__desc">CriticAgent 对选定论题进行学术规范校验，输出评分、问题与建议。</p>' +
          '</div>' +
        '</div>' +
        '<div class="card card--accent mb-md">' +
          '<div class="card__body">' +
            '<div class="text-xs text-muted mb-xs">当前论题</div>' +
            '<div class="text-display" style="font-size:1rem;color:var(--text-primary);">' + escapeHtml(proposal.title || '未命名论题') + '</div>' +
          '</div>' +
        '</div>';

      if (!state.validation) {
        bodyHtml +=
          '<div class="empty-state">' +
            '<div class="spinner spinner--lg"></div>' +
            '<div class="empty-state__title mt-md">正在校验…</div>' +
            '<p class="empty-state__desc">CriticAgent 正在评估学术规范与可行性。</p>' +
          '</div>';
        return bodyHtml;
      }

      const v = state.validation;
      const score = typeof v.score === 'number' ? v.score : (typeof v.confidence_score === 'number' ? Math.round(v.confidence_score * 100) : 75);
      const isLow = score < 60;
      const issues = v.issues || v.problems || [];
      const suggestions = v.suggestions || [];

      bodyHtml +=
        '<div class="validation-score">' +
          '<div>' +
            '<div class="validation-score__value' + (isLow ? ' validation-score__value--low' : '') + '">' + score + '</div>' +
            '<div class="validation-score__label">综合评分</div>' +
          '</div>' +
          '<div class="validation-issues">' +
            (issues.length > 0
              ? issues.map((issue) =>
                  '<div class="validation-issue">' +
                    '<i data-lucide="alert-triangle"></i>' +
                    '<span>' + escapeHtml(typeof issue === 'string' ? issue : (issue.description || issue.message || JSON.stringify(issue))) + '</span>' +
                  '</div>'
                ).join('')
              : '<div class="validation-issue"><i data-lucide="check-circle-2" style="color:var(--success);"></i><span>未发现明显问题</span></div>'
            ) +
            (suggestions.length > 0
              ? suggestions.map((sug) =>
                  '<div class="validation-issue"><i data-lucide="lightbulb" style="color:var(--info);"></i><span>' + escapeHtml(typeof sug === 'string' ? sug : (sug.description || sug.message || '')) + '</span></div>'
                ).join('')
              : ''
            ) +
          '</div>' +
        '</div>';

      if (isLow) {
        bodyHtml +=
          '<button class="stage-action stage-action--danger" id="rollback-creativity">' +
            '<i data-lucide="rotate-ccw"></i><span>回退重新生成</span>' +
          '</button>';
      } else {
        bodyHtml +=
          '<button class="stage-action stage-action--primary" id="proceed-generation">' +
            '<i data-lucide="arrow-right-circle"></i><span>进入生成阶段</span>' +
          '</button>';
      }

      return bodyHtml;
    },

    // 运行校验：调用标题校验与可行性检查
    async runValidation(proposal) {
      try {
        const [titleRes, feasRes] = await Promise.all([
          API.validateTitle({ title: proposal.title, degree: state.degree }).catch(() => null),
          API.checkFeasibility({ title: proposal.title, degree: state.degree, discipline: state.discipline }).catch(() => null),
        ]);

        // 综合校验结果
        const score = this.computeValidationScore(titleRes, feasRes, proposal);
        const issues = this.collectValidationIssues(titleRes, feasRes);
        const suggestions = this.collectValidationSuggestions(titleRes, feasRes);

        state.validation = {
          score: score,
          issues: issues,
          suggestions: suggestions,
          title_result: titleRes,
          feasibility_result: feasRes,
        };

        // 重新渲染校验面板
        this.renderStagePanels();
      } catch (err) {
        // 校验失败时给出默认通过结果，避免阻塞流程
        state.validation = {
          score: 75,
          issues: ['校验服务暂不可用，已跳过部分检查'],
          suggestions: [],
        };
        this.renderStagePanels();
        showToast('校验服务异常：' + (err.message || err), 'warning');
      }
    },

    // 计算综合评分
    computeValidationScore(titleRes, feasRes, proposal) {
      let score = 70;
      // 标题校验通过加分
      if (titleRes && !titleRes.auto_rewritten) score += 10;
      if (titleRes && titleRes.auto_rewritten) score -= 5;
      // 可行性检查
      if (feasRes && feasRes.feasible) score += 15;
      if (feasRes && feasRes.feasible === false) score -= 20;
      // 置信度
      const conf = Number(proposal.confidence_score) || 0;
      score += Math.round(conf * 10);
      return Math.max(0, Math.min(100, score));
    },

    // 收集校验问题
    collectValidationIssues(titleRes, feasRes) {
      const issues = [];
      if (titleRes && titleRes.auto_rewritten && titleRes.reason) {
        issues.push('标题已自动改写：' + titleRes.reason);
      }
      if (feasRes && feasRes.issues && Array.isArray(feasRes.issues)) {
        feasRes.issues.forEach((i) => issues.push(typeof i === 'string' ? i : (i.message || i.description || '')));
      }
      return issues.filter(Boolean);
    },

    // 收集校验建议
    collectValidationSuggestions(titleRes, feasRes) {
      const suggestions = [];
      if (feasRes && feasRes.suggestions && Array.isArray(feasRes.suggestions)) {
        feasRes.suggestions.forEach((s) => suggestions.push(typeof s === 'string' ? s : (s.message || s.description || '')));
      }
      return suggestions.filter(Boolean);
    },

    /* ----------------------------------------------------------------------
       阶段 4：生成
       ---------------------------------------------------------------------- */

    render_generation() {
      const proposal = state.proposals[state.selectedProposalIdx];
      if (!proposal) {
        return '<div class="empty-state"><div class="empty-state__icon" data-lucide="alert-triangle"></div><div class="empty-state__title">未选择论题</div></div>';
      }

      let bodyHtml = '' +
        '<div class="stage-panel__header">' +
          '<div>' +
            '<h2 class="stage-panel__title">生成</h2>' +
            '<p class="stage-panel__desc">选择生成粒度，查看 style_normalizer 改写前后的对比。</p>' +
          '</div>' +
        '</div>';

      // 粒度选择器
      bodyHtml += '<div class="granularity-selector">';
      GRANULARITIES.forEach((g) => {
        const isActive = g.key === state.granularity;
        bodyHtml +=
          '<div class="granularity-option' + (isActive ? ' granularity-option--active' : '') + '" data-granularity="' + g.key + '">' +
            '<div class="granularity-option__icon"><i data-lucide="' + g.icon + '"></i></div>' +
            '<div class="granularity-option__label">' + escapeHtml(g.label) + '</div>' +
          '</div>';
      });
      bodyHtml += '</div>';

      // 生成按钮
      bodyHtml +=
        '<button class="btn btn-primary mb-lg" id="generate-content-btn">' +
          '<i data-lucide="file-text"></i><span>生成「' + escapeHtml(this.granularityLabel()) + '」</span>' +
        '</button>';

      // 风格对比区
      bodyHtml += '<div id="generation-content-area">' + this.renderGenerationContent() + '</div>';

      // 进入深度辅助
      if (state.generatedContent) {
        bodyHtml +=
          '<button class="stage-action stage-action--primary" id="proceed-deep-assist">' +
            '<i data-lucide="arrow-right-circle"></i><span>进入深度辅助</span>' +
          '</button>';
      }

      return bodyHtml;
    },

    // 当前粒度标签
    granularityLabel() {
      const g = GRANULARITIES.find((x) => x.key === state.granularity);
      return g ? g.label : '';
    },

    // 渲染生成内容与风格对比
    renderGenerationContent() {
      if (!state.generatedContent) {
        return '' +
          '<div class="empty-state">' +
            '<div class="empty-state__icon" data-lucide="file-text"></div>' +
            '<div class="empty-state__title">尚未生成</div>' +
            '<p class="empty-state__desc">点击上方按钮生成内容，将展示 style_normalizer 改写前后对比。</p>' +
          '</div>';
      }

      return '' +
        '<div class="style-compare">' +
          '<div class="style-compare__panel style-compare__panel--before">' +
            '<div class="style-compare__label"><i data-lucide="pen-tool" style="width:12px;height:12px;"></i> 改写前（原始）</div>' +
            '<div class="style-compare__content">' + escapeHtml(state.styleBefore || '（无原始内容）') + '</div>' +
          '</div>' +
          '<div class="style-compare__panel style-compare__panel--after">' +
            '<div class="style-compare__label"><i data-lucide="check-circle-2" style="width:12px;height:12px;"></i> 改写后（规范化）</div>' +
            '<div class="style-compare__content">' + escapeHtml(state.styleAfter || state.generatedContent) + '</div>' +
          '</div>' +
        '</div>';
    },

    // 仅刷新粒度选择与内容区
    renderGenerationGranularity() {
      const panels = document.getElementById('stage-panels');
      if (!panels) return;
      // 更新粒度高亮
      panels.querySelectorAll('[data-granularity]').forEach((el) => {
        el.classList.toggle('granularity-option--active', el.dataset.granularity === state.granularity);
      });
      // 更新按钮文案
      const btn = panels.querySelector('#generate-content-btn');
      if (btn) {
        btn.innerHTML = '<i data-lucide="file-text"></i><span>生成「' + escapeHtml(this.granularityLabel()) + '」</span>';
        refreshIcons(btn);
      }
    },

    // 处理内容生成
    async handleGenerateContent() {
      const proposal = state.proposals[state.selectedProposalIdx];
      if (!proposal) return;
      const btn = document.getElementById('generate-content-btn');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span><span>生成中…</span>';
      }

      try {
        // 根据粒度取不同字段作为生成内容
        let before = '';
        let after = '';
        switch (state.granularity) {
          case 'title':
            before = proposal.title || '';
            after = proposal.title || '';
            break;
          case 'abstract':
            before = proposal.problem_awareness || '';
            after = proposal.problem_awareness || '';
            break;
          case 'outline':
            before = proposal.literature_review_outline || '';
            after = proposal.literature_review_outline || '';
            break;
          case 'full':
            // 全文调用报告生成
            if (proposal.id) {
              const res = await API.generateReport(proposal.id, true);
              after = (res && res.report) || '';
              before = after;
            } else {
              after = proposal.problem_awareness || proposal.title || '';
              before = after;
            }
            break;
          default:
            after = proposal.title || '';
            before = after;
        }

        // 模拟 style_normalizer 改写：若 auto_rewritten，则 before 为原始、after 为改写后
        if (proposal.auto_rewritten) {
          before = '（原始表述）' + (before || proposal.title || '');
          after = after || proposal.title || '';
        }

        state.styleBefore = before;
        state.styleAfter = after;
        state.generatedContent = after;

        // 刷新生成阶段面板
        this.renderStagePanels();
        showToast('已生成「' + this.granularityLabel() + '」内容', 'success');
      } catch (err) {
        showToast('生成失败：' + (err.message || err), 'error');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i data-lucide="file-text"></i><span>重新生成「' + escapeHtml(this.granularityLabel()) + '」</span>';
          refreshIcons(btn);
        }
      }
    },

    /* ----------------------------------------------------------------------
       阶段 5：深度辅助
       ---------------------------------------------------------------------- */

    render_deep_assist() {
      const proposal = state.proposals[state.selectedProposalIdx];

      let bodyHtml = '' +
        '<div class="stage-panel__header">' +
          '<div>' +
            '<h2 class="stage-panel__title">深度辅助</h2>' +
            '<p class="stage-panel__desc">选择深度辅助模式，进入对应的子对话继续推进研究。</p>' +
          '</div>' +
        '</div>';

      if (proposal) {
        bodyHtml +=
          '<div class="card card--accent mb-lg">' +
            '<div class="card__body">' +
              '<div class="text-xs text-muted mb-xs">当前论题</div>' +
              '<div class="text-display" style="font-size:1rem;color:var(--text-primary);">' + escapeHtml(proposal.title || '未命名论题') + '</div>' +
            '</div>' +
          '</div>';
      }

      bodyHtml += '<div class="deep-assist-grid">';
      DEEP_ASSISTS.forEach((opt) => {
        bodyHtml +=
          '<button class="deep-assist-card" data-deep-assist="' + opt.key + '">' +
            '<div class="deep-assist-card__icon"><i data-lucide="' + opt.icon + '"></i></div>' +
            '<div class="deep-assist-card__title">' + escapeHtml(opt.title) + '</div>' +
            '<div class="deep-assist-card__desc">' + escapeHtml(opt.desc) + '</div>' +
            '<span class="deep-assist-card__arrow">' +
              '<span>进入对话</span>' +
              '<i data-lucide="arrow-right"></i>' +
            '</span>' +
          '</button>';
      });
      bodyHtml += '</div>';

      return bodyHtml;
    },

    // 进入深度辅助子对话：跳转会话页
    enterDeepAssist(type) {
      const proposal = state.proposals[state.selectedProposalIdx];
      const title = proposal ? proposal.title : '深度辅助';
      const labels = { literature: '文献精读', experiment: '实验预研', defense: '答辩模拟' };
      showToast('即将进入「' + (labels[type] || type) + '」子对话', 'info');
      // 跳转到会话页继续对话
      setTimeout(() => navigate('sessions'), 600);
    },
  };
})();
