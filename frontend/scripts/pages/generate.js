/* ==========================================================================
   ThesisMiner v6.0 - 论题生成页面
   左侧表单配置 + 右侧候选论题展示，含标题校验工具
   ========================================================================== */
(function () {
  'use strict';

  // 学位/学科标签映射
  const DEGREE_LABELS = { master: '硕士', doctor: '博士' };
  const DISCIPLINE_LABELS = {
    humanities_social: '人文社科',
    science_engineering: '理工科',
  };

  // 表单状态
  const state = {
    degree: 'master',
    discipline: 'humanities_social',
    mode: 'quick',
    count: 3,
    generating: false,
    proposals: [],
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

  /**
   * 渲染按钮组选项
   * @param {string} group 分组名
   * @param {Array<{value:string,label:string}>} options 选项
   * @param {string} current 当前选中值
   */
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

  /** 候选论题卡片 */
  function proposalCard(p, idx) {
    const score = Number(p.confidence_score) || 0;
    const pct = Math.round(score * 100);
    const level = confidenceLevel(score);
    return (
      '<div class="card card--interactive card--accent slide-in" data-proposal-idx="' + idx + '">' +
      '<div class="flex items-start justify-between gap-md mb-sm">' +
      '<h3 class="text-display" style="font-size:1.15rem;line-height:1.35;flex:1">' +
      escapeHtml(p.title || '未命名论题') + '</h3>' +
      '<span class="badge badge--accent">' + pct + '%</span>' +
      '</div>' +
      '<div class="flex flex-wrap gap-xs mb-md">' +
      (p.inspiration_source
        ? '<span class="badge badge--default"><i data-lucide="lightbulb" style="width:12px;height:12px"></i> ' +
          escapeHtml(truncate(p.inspiration_source, 28)) + '</span>'
        : '') +
      (p.auto_rewritten ? '<span class="badge badge--warning">已改写</span>' : '') +
      '</div>' +
      (p.problem_awareness
        ? '<p class="text-sm text-secondary line-clamp-2 mb-md">' +
          escapeHtml(p.problem_awareness) + '</p>'
        : '') +
      '<div class="confidence-bar">' +
      '<div class="confidence-bar__track">' +
      '<div class="confidence-bar__fill confidence-bar__fill--' + level +
      '" style="width:' + pct + '%"></div>' +
      '</div>' +
      '<span class="confidence-bar__value">' + pct + '%</span>' +
      '</div>' +
      '<div class="flex items-center justify-between mt-md">' +
      '<span class="text-xs text-muted">点击查看完整详情</span>' +
      '<i data-lucide="chevron-right" style="width:16px;height:16px;color:var(--accent-primary)"></i>' +
      '</div>' +
      '</div>'
    );
  }

  /** 空状态 */
  function emptyResult() {
    return (
      '<div class="empty-state">' +
      '<div class="empty-state__icon" data-lucide="sparkles"></div>' +
      '<div class="empty-state__title">等待生成论题</div>' +
      '<p class="empty-state__desc">填写左侧表单信息，点击「生成论题」按钮，AI 将基于学术语境为你产出候选论题。</p>' +
      '</div>'
    );
  }

  /** 生成中状态 */
  function loadingResult() {
    return (
      '<div class="empty-state">' +
      '<div class="spinner spinner--lg"></div>' +
      '<div class="empty-state__title mt-md">正在生成论题…</div>' +
      '<p class="empty-state__desc">AI 正在结合导师信息与学术规范进行多轮推演，请稍候。</p>' +
      '</div>'
    );
  }

  /**
   * 生成中状态（带打字机/进度动画）
   * 返回 HTML 字符串与启动/清理函数；后端 /generate 仍返回 JSON，
   * 此处通过循环切换文案模拟流式进度，提升等待体验。
   */
  function loadingResultAnimated() {
    const messages = [
      '正在分析学术语境...',
      '检索相关文献...',
      '生成候选论题...',
      '校验学术规范...',
      '优化论题表述...',
    ];
    const steps = ['分析', '检索', '生成', '校验'];
    const html =
      '<div class="empty-state" id="loading-state">' +
      '<div class="spinner spinner--lg"></div>' +
      '<div class="empty-state__title mt-md" id="loading-message">' + messages[0] + '</div>' +
      '<p class="empty-state__desc">AI 正在结合导师信息与学术规范进行多轮推演，请稍候。</p>' +
      '<div class="flex gap-xs mt-md" id="loading-dots">' +
      steps
        .map(
          (s, i) =>
            '<span class="badge badge--default" data-step="' +
            i +
            '" style="opacity:0.3;transition:all 0.3s ease;">' +
            s +
            '</span>',
        )
        .join('') +
      '</div>' +
      '</div>';
    return {
      html: html,
      start: function () {
        let msgIdx = 0;
        const interval = setInterval(() => {
          msgIdx = (msgIdx + 1) % messages.length;
          const msgEl = document.getElementById('loading-message');
          const dots = document.querySelectorAll('#loading-dots .badge');
          if (msgEl) msgEl.textContent = messages[msgIdx];
          if (dots) {
            dots.forEach((dot, i) => {
              const active = i <= msgIdx;
              dot.style.opacity = active ? '1' : '0.3';
              dot.style.background = active ? 'var(--accent-primary)' : '';
              dot.style.color = active ? 'var(--bg-base)' : '';
              dot.style.borderColor = active ? 'var(--accent-primary)' : '';
            });
          }
        }, 1500);
        return () => clearInterval(interval);
      },
    };
  }

  /** AI 未配置提示 */
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
      '<span class="badge badge--accent">置信度 ' + pct + '%</span>' +
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
          content.map((c) => '<li class="text-sm text-secondary">' + escapeHtml(c) + '</li>').join('') +
          '</ol></div>'
        : '') +
      (p.feasibility_analysis
        ? '<div><h6>可行性分析</h6><p class="text-sm text-secondary">' +
          escapeHtml(p.feasibility_analysis) + '</p></div>'
        : '') +
      '<div class="flex gap-sm pt-md" style="border-top:1px solid var(--border-subtle)">' +
      '<button id="gen-report-btn" class="btn btn-primary" style="flex:1"' +
      (p.id ? '' : ' disabled') + '>' +
      '<i data-lucide="file-text"></i> 生成开题报告' +
      '</button>' +
      '</div>' +
      '</div>';

    showDrawer({
      title: '论题详情',
      bodyHtml: bodyHtml,
      onMount: (drawer) => {
        const btn = drawer.querySelector('#gen-report-btn');
        if (btn && p.id) {
          btn.addEventListener('click', () => handleGenerateReport(p));
        }
      },
    });
  }

  /**
   * 处理生成开题报告
   * @param {object} proposal 论题对象
   */
  async function handleGenerateReport(proposal) {
    const proposalId = proposal && proposal.id;
    if (!proposalId) {
      showToast('论题 ID 缺失，无法生成报告', 'warning');
      return;
    }

    // 关闭论题详情抽屉，打开报告抽屉并展示加载态
    closeDrawer();
    showReportDrawer({ loading: true, proposal: proposal });

    try {
      const res = await API.generateReport(proposalId, true);
      showReportDrawer({
        loading: false,
        proposal: proposal,
        report: (res && res.report) || '',
        aiEnhanced: !!(res && res.ai_enhanced),
        generatedAt: (res && res.generated_at) || '',
      });
    } catch (err) {
      const msg = err && err.message ? err.message : String(err);
      showReportDrawer({ loading: false, proposal: proposal, error: msg });
      showToast('开题报告生成失败：' + msg, 'error');
    }
  }

  /**
   * 在抽屉中展示开题报告 Markdown
   * @param {object} opts - { loading, proposal, report, aiEnhanced, generatedAt, error }
   */
  function showReportDrawer(opts) {
    const proposal = opts.proposal || {};
    let bodyHtml;

    if (opts.loading) {
      bodyHtml =
        '<div class="empty-state">' +
        '<div class="spinner spinner--lg"></div>' +
        '<div class="empty-state__title mt-md">正在生成开题报告…</div>' +
        '<p class="empty-state__desc">AI 正在基于论题数据扩展为完整报告，请稍候。</p>' +
        '</div>';
    } else if (opts.error) {
      bodyHtml =
        '<div class="card card--accent" style="border-left-color:var(--danger)">' +
        '<div class="flex items-start gap-md">' +
        '<i data-lucide="alert-circle" style="width:22px;height:22px;color:var(--danger);flex-shrink:0;margin-top:2px"></i>' +
        '<div>' +
        '<h4 class="text-danger mb-sm">生成失败</h4>' +
        '<p class="text-sm text-secondary">' + escapeHtml(opts.error) + '</p>' +
        '</div></div></div>';
    } else {
      const report = opts.report || '';
      const aiBadge = opts.aiEnhanced
        ? '<span class="badge badge--accent ml-sm">AI 增强</span>'
        : '<span class="badge badge--default ml-sm">模板生成</span>';
      const time = opts.generatedAt ? formatDate(opts.generatedAt) : '';

      bodyHtml =
        '<div class="flex flex-col gap-md">' +
        '<div>' +
        '<h3 class="text-display" style="font-size:1.15rem;line-height:1.4">' +
        escapeHtml(proposal.title || '开题报告') + '</h3>' +
        '<div class="mt-sm">' +
        '<span class="badge badge--default">开题报告</span>' + aiBadge +
        (time ? '<span class="text-xs text-muted ml-sm">' + escapeHtml(time) + '</span>' : '') +
        '</div>' +
        '</div>' +
        '<div class="flex gap-sm">' +
        '<button id="report-copy-btn" class="btn btn-secondary btn-sm" style="flex:1">' +
        '<i data-lucide="copy"></i> 复制' +
        '</button>' +
        '<button id="report-download-btn" class="btn btn-primary btn-sm" style="flex:1">' +
        '<i data-lucide="download"></i> 下载' +
        '</button>' +
        '</div>' +
        '<pre class="code-block" id="report-md" style="white-space:pre-wrap;word-break:break-word;max-height:60vh;overflow:auto;font-size:0.85rem;line-height:1.6">' +
        escapeHtml(report) + '</pre>' +
        '</div>';
    }

    showDrawer({
      title: '开题报告',
      bodyHtml: bodyHtml,
      onMount: (drawer) => {
        const copyBtn = drawer.querySelector('#report-copy-btn');
        const downloadBtn = drawer.querySelector('#report-download-btn');
        const mdEl = drawer.querySelector('#report-md');

        if (copyBtn && mdEl) {
          copyBtn.addEventListener('click', async () => {
            const text = mdEl.textContent || '';
            const ok = await copyToClipboard(text);
            showToast(ok ? '已复制到剪贴板' : '复制失败，请手动选择文本', ok ? 'success' : 'error');
          });
        }

        if (downloadBtn && mdEl) {
          downloadBtn.addEventListener('click', () => {
            const text = mdEl.textContent || '';
            const safeName = (proposal.title || '开题报告').replace(/[\\/:*?"<>|]/g, '_');
            const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = safeName + '.md';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('已开始下载', 'success');
          });
        }
      },
    });
  }

  window.Pages = window.Pages || {};
  window.Pages.generate = {
    /** 渲染页面骨架 */
    render() {
      return (
        '<header class="page-header">' +
        '<div class="page-header__eyebrow">ThesisMiner · Generate</div>' +
        '<h1 class="page-header__title">论题生成</h1>' +
        '<p class="page-header__desc">基于学术语境驱动，生成直通开题报告的高质量论题提案，每一条都附带完整的研究架构。</p>' +
        '</header>' +
        '<div class="page-body">' +
        '<div class="grid" style="grid-template-columns:400px 1fr;gap:var(--space-lg);align-items:start" id="gen-layout">' +
        '<!-- 左侧表单 -->' +
        '<section class="flex flex-col gap-lg">' +
        '<div class="form-section" style="margin-bottom:0">' +
        '<div class="form-group">' +
        '<label class="form-label">学位类型</label>' +
        '<div class="flex gap-sm" data-group="degree">' +
        buttonGroup(
          'degree',
          [
            { value: 'master', label: '硕士' },
            { value: 'doctor', label: '博士' },
          ],
          state.degree,
        ) +
        '</div>' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">学科类型</label>' +
        '<div class="flex gap-sm" data-group="discipline">' +
        buttonGroup(
          'discipline',
          [
            { value: 'humanities_social', label: '人文社科' },
            { value: 'science_engineering', label: '理工科' },
          ],
          state.discipline,
        ) +
        '</div>' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">导师信息</label>' +
        '<textarea id="gen-mentor" class="form-control" rows="4" ' +
        'placeholder="输入导师在研项目、同门论文等信息..."></textarea>' +
        '<div class="form-hint">越详细的导师背景越能生成贴合研究方向的论题。</div>' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">生成模式</label>' +
        '<div class="flex gap-sm" data-group="mode">' +
        buttonGroup(
          'mode',
          [
            { value: 'quick', label: '快速发散' },
            { value: 'deep', label: '深度精炼' },
          ],
          state.mode,
        ) +
        '</div>' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">生成数量</label>' +
        '<input id="gen-count" type="number" class="form-control" min="1" max="5" value="' + state.count + '" style="max-width:120px" />' +
        '<div class="form-hint">单次生成 1-5 个候选论题。</div>' +
        '</div>' +
        '<button id="gen-submit" class="btn btn-primary btn-lg btn-block">' +
        '<i data-lucide="sparkles"></i> 生成论题' +
        '</button>' +
        '</div>' +
        '<!-- 标题校验工具（折叠） -->' +
        '<div class="form-section" style="margin-bottom:0">' +
        '<div class="flex items-center justify-between cursor-pointer" id="validator-toggle">' +
        '<span class="form-section__title" style="margin:0">标题校验工具</span>' +
        '<i data-lucide="chevron-down" id="validator-chevron" style="width:18px;height:18px;color:var(--text-muted);transition:transform 0.2s"></i>' +
        '</div>' +
        '<div id="validator-panel" class="hidden mt-md">' +
        '<div class="form-group" style="margin-bottom:var(--space-sm)">' +
        '<input id="validator-input" type="text" class="form-control" placeholder="输入待校验的论题标题..." />' +
        '</div>' +
        '<button id="validator-btn" class="btn btn-secondary btn-sm btn-block">' +
        '<i data-lucide="check-check"></i> 校验标题' +
        '</button>' +
        '<div id="validator-result" class="mt-md"></div>' +
        '</div>' +
        '</div>' +
        '</section>' +
        '<!-- 右侧结果区 -->' +
        '<section>' +
        '<div class="flex items-center justify-between mb-md">' +
        '<h2 class="heading-accent" style="font-size:1.1rem">候选论题</h2>' +
        '<span id="gen-count-badge" class="badge badge--default"></span>' +
        '</div>' +
        '<div id="gen-result">' + emptyResult() + '</div>' +
        '</section>' +
        '</div>' +
        '</div>'
      );
    },

    /** app.js 调用入口：委托给 mount(container) */
    async init() {
      const container = document.getElementById('app-content');
      if (container) await this.mount(container);
    },

    /** 挂载到主内容区：绑定事件 */
    async mount(container) {
      refreshIcons();
      this.bindForm(container);
      this.bindValidator();
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
            // 更新视觉状态
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

    /** 绑定标题校验工具 */
    bindValidator() {
      const toggle = document.getElementById('validator-toggle');
      const panel = document.getElementById('validator-panel');
      const chevron = document.getElementById('validator-chevron');
      if (toggle && panel) {
        toggle.addEventListener('click', () => {
          const isOpen = !panel.classList.contains('hidden');
          panel.classList.toggle('hidden', isOpen);
          if (chevron) chevron.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
        });
      }

      const btn = document.getElementById('validator-btn');
      const input = document.getElementById('validator-input');
      if (btn && input) {
        const run = () => this.handleValidate();
        btn.addEventListener('click', run);
        input.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') run();
        });
      }
    },

    /** 处理生成论题 */
    async handleGenerate() {
      if (state.generating) return;

      const mentorEl = document.getElementById('gen-mentor');
      const mentorInfo = (mentorEl && mentorEl.value.trim()) || '';
      if (!mentorInfo) {
        showToast('请输入导师信息后再生成', 'warning');
        if (mentorEl) mentorEl.focus();
        return;
      }

      const resultEl = document.getElementById('gen-result');
      const submit = document.getElementById('gen-submit');
      const countBadge = document.getElementById('gen-count-badge');

      // 检查 AI 配置
      try {
        const status = await API.getStatus();
        if (!status || !status.ai_configured) {
          if (resultEl) {
            resultEl.innerHTML = aiUnconfiguredResult();
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
      // 使用带打字机/进度动画的加载态
      let stopLoadingAnim = null;
      if (resultEl) {
        const loading = loadingResultAnimated();
        resultEl.innerHTML = loading.html;
        refreshIcons();
        stopLoadingAnim = loading.start();
      }
      if (countBadge) countBadge.textContent = '';

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
          if (resultEl) {
            resultEl.innerHTML =
              '<div class="empty-state">' +
              '<div class="empty-state__icon" data-lucide="inbox"></div>' +
              '<div class="empty-state__title">未生成任何论题</div>' +
              '<p class="empty-state__desc">AI 未返回有效结果，请调整导师信息后重试。</p>' +
              '</div>';
            refreshIcons();
          }
          return;
        }

        if (resultEl) {
          // 结果到达，先停止加载动画
          if (stopLoadingAnim) stopLoadingAnim();
          // 渐显动画：包裹一层 fade-in 容器
          resultEl.innerHTML =
            '<div class="list stagger fade-in" id="gen-result-list">' +
            proposals.map((p, i) => proposalCard(p, i)).join('') +
            '</div>';
          refreshIcons();
          // 绑定卡片点击
          resultEl.querySelectorAll('[data-proposal-idx]').forEach((el) => {
            el.addEventListener('click', () => {
              const idx = parseInt(el.dataset.proposalIdx, 10);
              const target = state.proposals[idx];
              if (target) showProposalDrawer(target);
            });
          });
        }
        if (countBadge) {
          countBadge.textContent = '共 ' + proposals.length + ' 条';
        }
        showToast('已生成 ' + proposals.length + ' 条候选论题', 'success');
      } catch (err) {
        const msg = err && err.message ? err.message : String(err);
        if (resultEl) {
          resultEl.innerHTML =
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
        // 兜底清理加载动画
        if (stopLoadingAnim) stopLoadingAnim();
        state.generating = false;
        if (submit) {
          submit.disabled = false;
          submit.innerHTML = '<i data-lucide="sparkles"></i> 生成论题';
          refreshIcons();
        }
      }
    },

    /** 处理标题校验 */
    async handleValidate() {
      const input = document.getElementById('validator-input');
      const resultEl = document.getElementById('validator-result');
      const btn = document.getElementById('validator-btn');
      if (!input || !resultEl) return;

      const title = input.value.trim();
      if (!title) {
        showToast('请输入待校验的标题', 'warning');
        input.focus();
        return;
      }

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> 校验中…';
      }
      resultEl.innerHTML = '<div class="skeleton skeleton--text"></div>';

      try {
        const res = await API.validateTitle({ title: title, degree: state.degree });
        const rewritten = !!(res && res.auto_rewritten);
        const reason = res && res.reason ? res.reason : '';
        const finalTitle = (res && res.title) || title;

        if (rewritten) {
          resultEl.innerHTML =
            '<div class="card" style="padding:var(--space-md);border-left:3px solid var(--warning)">' +
            '<div class="flex items-center gap-sm mb-sm">' +
            '<i data-lucide="alert-triangle" style="width:16px;height:16px;color:var(--warning)"></i>' +
            '<span class="badge badge--warning">已自动改写</span>' +
            '</div>' +
            (reason ? '<p class="text-sm text-secondary mb-sm">原因：' + escapeHtml(reason) + '</p>' : '') +
            '<div class="mb-sm"><h6 class="text-muted">原标题</h6>' +
            '<p class="text-sm text-muted" style="text-decoration:line-through">' + escapeHtml(title) + '</p></div>' +
            '<div><h6 class="text-success">改写后</h6>' +
            '<p class="text-sm text-display" style="font-size:1rem">' + escapeHtml(finalTitle) + '</p></div>' +
            '</div>';
        } else {
          resultEl.innerHTML =
            '<div class="card" style="padding:var(--space-md);border-left:3px solid var(--success)">' +
            '<div class="flex items-center gap-sm mb-sm">' +
            '<i data-lucide="check-circle-2" style="width:16px;height:16px;color:var(--success)"></i>' +
            '<span class="badge badge--success">校验通过</span>' +
            '</div>' +
            '<p class="text-sm text-secondary">标题符合学术规范，可正常使用。</p>' +
            '<p class="text-sm text-display mt-sm" style="font-size:1rem">' + escapeHtml(finalTitle) + '</p>' +
            '</div>';
        }
        refreshIcons();
      } catch (err) {
        const msg = err && err.message ? err.message : String(err);
        resultEl.innerHTML =
          '<div class="card" style="padding:var(--space-md);border-left:3px solid var(--danger)">' +
          '<div class="flex items-center gap-sm mb-sm">' +
          '<i data-lucide="alert-circle" style="width:16px;height:16px;color:var(--danger)"></i>' +
          '<span class="badge badge--danger">校验失败</span>' +
          '</div>' +
          '<p class="text-sm text-secondary">' + escapeHtml(msg) + '</p>' +
          '</div>';
        refreshIcons();
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i data-lucide="check-check"></i> 校验标题';
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
  };
})();
