/* ==========================================================================
   ThesisMiner v6.0 - 谱系管理页面
   节点列表 + SVG 关系图可视化 + 导入抽屉与知识卡片
   ========================================================================== */
(function () {
  'use strict';

  // 节点类型 -> 颜色 / 图标映射
  const TYPE_META = {
    paper: { color: '#6a9fb5', icon: 'file-text', label: '论文' },
    topic: { color: '#d4a574', icon: 'lightbulb', label: '论题' },
    method: { color: '#7fb069', icon: 'wrench', label: '方法' },
    author: { color: '#e8b04e', icon: 'user', label: '作者' },
    concept: { color: '#c75450', icon: 'bookmark', label: '概念' },
    dataset: { color: '#a8a39a', icon: 'database', label: '数据' },
  };

  // 默认节点类型选项
  const NODE_TYPES = ['paper', 'topic', 'method', 'author', 'concept', 'dataset'];

  // 分页状态
  let currentPage = 1;
  const PAGE_SIZE = 20;
  let totalNodes = 0;
  let selectedNodeIds = new Set();
  // 当前页节点数据缓存（用于复选框切换时局部刷新工具栏）
  let currentPageNodes = [];

  /** 取节点类型元信息，未知类型回退到默认 */
  function typeMeta(type) {
    return TYPE_META[type] || { color: '#a8a39a', icon: 'circle', label: type || '节点' };
  }

  /** 节点列表条目 */
  function nodeItem(node) {
    const meta = typeMeta(node.node_type);
    const isChecked = selectedNodeIds.has(node.id);
    return (
      '<div class="list-item list-item--clickable" data-node-id="' + escapeHtml(node.id) + '">' +
      '<input type="checkbox" class="node-checkbox" data-node-id="' + escapeHtml(node.id) + '" ' +
      (isChecked ? 'checked' : '') + ' style="margin-right:8px;flex-shrink:0" />' +
      '<span class="nav-item__icon" style="color:' + meta.color + ';flex-shrink:0">' +
      '<i data-lucide="' + meta.icon + '"></i></span>' +
      '<div class="flex-1" style="min-width:0">' +
      '<div class="flex items-center gap-sm mb-xs">' +
      '<span class="badge badge--default" style="font-size:0.65rem">' + escapeHtml(meta.label) + '</span>' +
      '<span class="text-xs text-muted text-mono">' + formatDate(node.created_at, false) + '</span>' +
      '</div>' +
      '<div class="text-sm font-medium truncate">' + escapeHtml(node.title || '未命名节点') + '</div>' +
      (node.abstract
        ? '<div class="text-xs text-muted line-clamp-2 mt-xs">' + escapeHtml(node.abstract) + '</div>'
        : '') +
      '</div>' +
      '<button class="btn btn-ghost btn-icon" data-delete-node="' + escapeHtml(node.id) + '" ' +
      'title="删除节点" aria-label="删除节点">' +
      '<i data-lucide="trash-2" style="width:15px;height:15px;color:var(--danger)"></i>' +
      '</button>' +
      '</div>'
    );
  }

  /** 图谱空状态 */
  function graphEmpty() {
    return (
      '<div class="empty-state" style="height:100%">' +
      '<div class="empty-state__icon" data-lucide="git-fork"></div>' +
      '<div class="empty-state__title">暂无图谱数据</div>' +
      '<p class="empty-state__desc">导入谱系节点与关系后，将在此处以图形方式展示学术脉络。</p>' +
      '<button class="btn btn-primary btn-sm mt-md" data-action="open-import">' +
      '<i data-lucide="upload"></i> 导入谱系</button>' +
      '</div>'
    );
  }

  /** 列表空状态 */
  function listEmpty() {
    return (
      '<div class="empty-state">' +
      '<div class="empty-state__icon" data-lucide="git-fork"></div>' +
      '<div class="empty-state__title">尚未建立谱系</div>' +
      '<p class="empty-state__desc">点击「导入」按钮，添加论文、论题、方法等节点，构建你的学术脉络。</p>' +
      '</div>'
    );
  }

  /** 分页工具栏：全选 / 批量删除 / 页码导航 */
  function paginationToolbar() {
    const totalPages = Math.max(1, Math.ceil(totalNodes / PAGE_SIZE));
    const hasPrev = currentPage > 1;
    const hasNext = currentPage < totalPages;
    const selectedCount = selectedNodeIds.size;
    // 当前页是否全部选中
    const pageIds = currentPageNodes.map((n) => n.id);
    const allSelected = pageIds.length > 0 && pageIds.every((id) => selectedNodeIds.has(id));
    return (
      '<div class="flex items-center justify-between mb-md" style="gap:12px;flex-wrap:wrap" id="lineage-pagination-toolbar">' +
      '<div class="flex items-center gap-sm">' +
      '<label class="flex items-center gap-xs" style="cursor:pointer;font-size:0.8rem">' +
      '<input type="checkbox" id="select-all-checkbox" ' + (allSelected ? 'checked' : '') + ' />' +
      '<span>全选</span>' +
      '</label>' +
      (selectedCount > 0
        ? '<button class="btn btn-secondary btn-sm" id="batch-delete-btn">' +
          '<i data-lucide="trash-2"></i><span>批量删除 (' + selectedCount + ')</span>' +
          '</button>'
        : '') +
      '</div>' +
      '<div class="flex items-center gap-sm">' +
      '<button class="btn btn-ghost btn-sm" id="prev-page-btn" ' + (!hasPrev ? 'disabled' : '') + '>' +
      '<i data-lucide="chevron-left"></i>' +
      '</button>' +
      '<span class="text-xs text-muted">第 ' + currentPage + ' 页 / 共 ' + totalPages +
      ' 页 (' + totalNodes + ' 条)</span>' +
      '<button class="btn btn-ghost btn-sm" id="next-page-btn" ' + (!hasNext ? 'disabled' : '') + '>' +
      '<i data-lucide="chevron-right"></i>' +
      '</button>' +
      '</div>' +
      '</div>'
    );
  }

  window.Pages = window.Pages || {};
  window.Pages.lineage = {
    // 图谱节点位置缓存（用于拖拽持久化）
    positions: {},
    // 当前图谱数据缓存
    graphData: { nodes: [], edges: [] },

    /** 渲染页面骨架 */
    render() {
      return (
        '<header class="page-header">' +
        '<div class="page-header__eyebrow">ThesisMiner · Lineage</div>' +
        '<h1 class="page-header__title">学术谱系</h1>' +
        '<p class="page-header__desc">管理论文、论题、方法等知识节点及其关系，以图谱形式可视化你的学术脉络传承。</p>' +
        '</header>' +
        '<div class="page-body">' +
        '<!-- 顶部工具栏 -->' +
        '<div class="flex items-center gap-md mb-lg flex-wrap" id="lineage-toolbar">' +
        '<div class="relative" style="flex:1;min-width:220px;max-width:420px">' +
        '<i data-lucide="search" style="position:absolute;left:12px;top:50%;transform:translateY(-50%);width:16px;height:16px;color:var(--text-muted)"></i>' +
        '<input id="lineage-search" type="text" class="form-control" placeholder="搜索节点标题..." style="padding-left:38px" />' +
        '</div>' +
        '<div class="flex gap-sm">' +
        '<button class="btn btn-secondary" data-action="open-import">' +
        '<i data-lucide="upload"></i> 导入</button>' +
        '<button class="btn btn-secondary" data-action="open-card">' +
        '<i data-lucide="plus"></i> 添加卡片</button>' +
        '</div>' +
        '</div>' +
        '<!-- 主体两列 -->' +
        '<div class="grid" style="grid-template-columns:1fr 1fr;gap:var(--space-lg);align-items:start">' +
        '<!-- 左列：节点列表 -->' +
        '<section>' +
        '<div class="flex items-center justify-between mb-md">' +
        '<h2 class="heading-accent" style="font-size:1.1rem">节点列表</h2>' +
        '<span id="node-count" class="badge badge--default"></span>' +
        '</div>' +
        '<div id="lineage-list" class="list stagger">' +
        '<div class="skeleton skeleton--block"></div>' +
        '<div class="skeleton skeleton--block"></div>' +
        '</div>' +
        '</section>' +
        '<!-- 右列：图谱可视化 -->' +
        '<section>' +
        '<div class="flex items-center justify-between mb-md">' +
        '<h2 class="heading-accent" style="font-size:1.1rem">关系图谱</h2>' +
        '<span class="text-xs text-muted">可拖拽节点</span>' +
        '</div>' +
        '<div class="card" style="padding:0;overflow:hidden">' +
        '<div id="lineage-graph" style="height:520px;position:relative">' +
        '<div class="loading-overlay" style="height:100%">' +
        '<div class="spinner spinner--lg"></div>' +
        '</div>' +
        '</div>' +
        '</div>' +
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

    /** 挂载到主内容区：绑定事件并加载数据 */
    async mount(container) {
      // 重置分页与选中状态
      currentPage = 1;
      selectedNodeIds.clear();
      refreshIcons();
      this.bindToolbar(container);
      this.loadNodes();
      this.loadGraph();
    },

    /** 绑定工具栏与全局动作 */
    bindToolbar(root) {
      if (!root) return;
      // 搜索（防抖实时搜索）
      const search = root.querySelector('#lineage-search');
      if (search) {
        const handler = debounce((val) => this.handleSearch(val), 300);
        search.addEventListener('input', () => handler(search.value.trim()));
      }

      // 工具栏按钮
      root.querySelectorAll('[data-action]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const action = btn.dataset.action;
          if (action === 'open-import') this.openImportDrawer();
          else if (action === 'open-card') this.openCardDrawer();
        });
      });
    },

    /** 加载节点列表 */
    async loadNodes(keyword) {
      const wrap = document.getElementById('lineage-list');
      const countEl = document.getElementById('node-count');
      if (!wrap) return;
      try {
        let nodes = [];
        let isSearch = false;
        if (keyword) {
          // 搜索模式：不使用分页，展示全部匹配结果
          isSearch = true;
          const res = await API.searchLineage(keyword);
          nodes = (res && res.results) || [];
          totalNodes = nodes.length;
        } else {
          // 列表模式：按页大小分页
          const offset = (currentPage - 1) * PAGE_SIZE;
          const res = await API.getLineage(PAGE_SIZE, offset);
          nodes = (res && res.nodes) || [];
          totalNodes = (res && res.total) || 0;
        }

        currentPageNodes = nodes;

        if (countEl) countEl.textContent = '共 ' + totalNodes + ' 个';

        if (!nodes.length) {
          wrap.innerHTML = listEmpty();
          refreshIcons();
          return;
        }

        // 渲染分页工具栏（搜索模式下隐藏）+ 节点列表
        const toolbarHtml = isSearch ? '' : paginationToolbar();
        wrap.innerHTML = toolbarHtml + nodes.map((n) => nodeItem(n)).join('');
        refreshIcons();

        // 绑定分页工具栏事件
        if (!isSearch) {
          this.bindPaginationEvents(wrap);
        }

        // 复选框：阻止冒泡并切换选中状态
        wrap.querySelectorAll('.node-checkbox').forEach((cb) => {
          cb.addEventListener('click', (e) => e.stopPropagation());
          cb.addEventListener('change', () => {
            const id = cb.dataset.nodeId;
            if (cb.checked) {
              selectedNodeIds.add(id);
            } else {
              selectedNodeIds.delete(id);
            }
            this.refreshToolbar();
          });
        });

        // 点击节点 -> 弹出详情抽屉
        wrap.querySelectorAll('[data-node-id]').forEach((el) => {
          el.addEventListener('click', (e) => {
            if (e.target.closest('[data-delete-node]')) return;
            if (e.target.closest('.node-checkbox')) return;
            const id = el.dataset.nodeId;
            const target = nodes.find((x) => x.id === id);
            if (target) this.showNodeDrawer(target);
          });
        });

        // 单个删除节点
        wrap.querySelectorAll('[data-delete-node]').forEach((btn) => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const id = btn.dataset.deleteNode;
            this.confirmDelete(id);
          });
        });
      } catch (err) {
        wrap.innerHTML =
          '<div class="empty-state">' +
          '<div class="empty-state__icon" data-lucide="alert-circle"></div>' +
          '<div class="empty-state__title">节点加载失败</div>' +
          '<p class="empty-state__desc">' + escapeHtml(err.message || String(err)) + '</p>' +
          '</div>';
        refreshIcons();
      }
    },

    /** 加载图谱数据并渲染 */
    async loadGraph() {
      const wrap = document.getElementById('lineage-graph');
      if (!wrap) return;
      try {
        const res = await API.getLineageGraph();
        const nodes = (res && res.nodes) || [];
        const edges = (res && res.edges) || [];
        this.graphData = { nodes, edges };
        this.renderGraph(wrap, nodes, edges);
      } catch (err) {
        wrap.innerHTML =
          '<div class="empty-state" style="height:100%">' +
          '<div class="empty-state__icon" data-lucide="alert-circle"></div>' +
          '<div class="empty-state__title">图谱加载失败</div>' +
          '<p class="empty-state__desc">' + escapeHtml(err.message || String(err)) + '</p>' +
          '</div>';
        refreshIcons();
      }
    },

    /**
     * 渲染 SVG 关系图
     * @param {HTMLElement} container 容器
     * @param {Array} nodes 节点列表
     * @param {Array} edges 边列表
     */
    renderGraph(container, nodes, edges) {
      if (!nodes.length) {
        container.innerHTML = graphEmpty();
        refreshIcons();
        // 绑定空状态导入按钮
        container.querySelectorAll('[data-action="open-import"]').forEach((btn) => {
          btn.addEventListener('click', () => this.openImportDrawer());
        });
        return;
      }

      const W = Math.max(container.clientWidth || 600, 400);
      const H = 520;
      const cx = W / 2;
      const cy = H / 2;
      const radius = Math.min(W, H) / 2 - 70;

      // 计算节点初始位置（环形布局，保留已有拖拽位置）
      const positions = {};
      nodes.forEach((n, i) => {
        if (this.positions[n.id]) {
          positions[n.id] = { ...this.positions[n.id] };
        } else {
          const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
          positions[n.id] = {
            x: cx + radius * Math.cos(angle),
            y: cy + radius * Math.sin(angle),
          };
        }
      });
      this.positions = positions;

      // 构建 SVG
      const parts = [];
      parts.push(
        '<svg width="100%" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" ' +
        'style="display:block;background:radial-gradient(ellipse at center, rgba(212,165,116,0.04), transparent 70%)" ' +
        'id="lineage-svg">',
      );
      // 箭头定义
      parts.push(
        '<defs><marker id="graph-arrow" viewBox="0 0 10 10" refX="10" refY="5" ' +
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">' +
        '<path d="M0,0 L10,5 L0,10 z" fill="#6b6862"/></marker></defs>',
      );

      // 边
      edges.forEach((e) => {
        const s = positions[e.source_id];
        const t = positions[e.target_id];
        if (!s || !t) return;
        // 缩短线条，避免插入节点圆内
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const ux = dx / dist;
        const uy = dy / dist;
        const r = 26;
        const x1 = s.x + ux * r;
        const y1 = s.y + uy * r;
        const x2 = t.x - ux * r;
        const y2 = t.y - uy * r;
        parts.push(
          '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" ' +
          'stroke="rgba(245,241,232,0.18)" stroke-width="1.5" marker-end="url(#graph-arrow)" ' +
          'data-edge="' + escapeHtml(e.source_id) + '|' + escapeHtml(e.target_id) + '"/>',
        );
      });

      // 节点
      nodes.forEach((n) => {
        const p = positions[n.id];
        const meta = typeMeta(n.node_type);
        const label = (n.title || '').slice(0, 5);
        parts.push(
          '<g class="graph-node" data-node-id="' + escapeHtml(n.id) + '" ' +
          'transform="translate(' + p.x + ',' + p.y + ')" style="cursor:grab">' +
          '<circle r="24" fill="' + meta.color + '" fill-opacity="0.18" ' +
          'stroke="' + meta.color + '" stroke-width="2"/>' +
          '<text text-anchor="middle" y="4" font-size="11" font-weight="600" fill="#f5f1e8" ' +
          'style="pointer-events:none;user-select:none">' + escapeHtml(label) + '</text>' +
          '<text text-anchor="middle" y="44" font-size="10" fill="#a8a39a" ' +
          'style="pointer-events:none;user-select:none">' + escapeHtml(truncate(n.title || '', 14)) + '</text>' +
          '</g>',
        );
      });

      parts.push('</svg>');
      container.innerHTML = parts.join('');

      // 绑定拖拽与点击
      this.bindGraphInteraction(container, nodes);
      refreshIcons();
    },

    /** 绑定图谱节点拖拽与点击 */
    bindGraphInteraction(container, nodes) {
      const svg = container.querySelector('#lineage-svg');
      if (!svg) return;

      const nodeEls = svg.querySelectorAll('.graph-node');
      nodeEls.forEach((g) => {
        let dragging = false;
        let moved = false;
        let startX = 0;
        let startY = 0;
        let origX = 0;
        let origY = 0;

        const onMove = (e) => {
          if (!dragging) return;
          const pt = clientToSvg(svg, e);
          const dx = pt.x - startX;
          const dy = pt.y - startY;
          if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
          const nx = origX + dx;
          const ny = origY + dy;
          g.setAttribute('transform', 'translate(' + nx + ',' + ny + ')');
          const id = g.dataset.nodeId;
          if (this.positions[id]) {
            this.positions[id].x = nx;
            this.positions[id].y = ny;
          }
          // 同步更新关联边
          this.updateEdges(svg);
        };

        const onUp = () => {
          dragging = false;
          g.style.cursor = 'grab';
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          // 未拖动则视为点击 -> 打开详情
          if (!moved) {
            const id = g.dataset.nodeId;
            const target = nodes.find((x) => x.id === id);
            if (target) this.showNodeDrawer(target);
          }
        };

        g.addEventListener('mousedown', (e) => {
          dragging = true;
          moved = false;
          g.style.cursor = 'grabbing';
          const pt = clientToSvg(svg, e);
          startX = pt.x;
          startY = pt.y;
          const tf = g.getAttribute('transform') || '';
          const m = tf.match(/translate\(([-\d.]+),([-\d.]+)\)/);
          origX = m ? parseFloat(m[1]) : 0;
          origY = m ? parseFloat(m[2]) : 0;
          document.addEventListener('mousemove', onMove);
          document.addEventListener('mouseup', onUp);
          e.preventDefault();
        });
      });
    },

    /** 拖拽后更新边位置 */
    updateEdges(svg) {
      const edges = svg.querySelectorAll('line[data-edge]');
      edges.forEach((line) => {
        const [sid, tid] = line.dataset.edge.split('|');
        const s = this.positions[sid];
        const t = this.positions[tid];
        if (!s || !t) return;
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const ux = dx / dist;
        const uy = dy / dist;
        const r = 26;
        line.setAttribute('x1', s.x + ux * r);
        line.setAttribute('y1', s.y + uy * r);
        line.setAttribute('x2', t.x - ux * r);
        line.setAttribute('y2', t.y - uy * r);
      });
    },

    /** 处理搜索 */
    async handleSearch(keyword) {
      // 清除搜索时回到第一页
      if (!keyword) {
        currentPage = 1;
      }
      // 搜索时清空选中状态
      selectedNodeIds.clear();
      await this.loadNodes(keyword);
    },

    /** 节点详情抽屉 */
    showNodeDrawer(node) {
      const meta = typeMeta(node.node_type);
      const metadata = node.metadata || {};
      const metaKeys = Object.keys(metadata);
      const bodyHtml =
        '<div class="flex flex-col gap-md">' +
        '<div class="flex items-center gap-sm">' +
        '<span class="badge badge--accent">' + escapeHtml(meta.label) + '</span>' +
        '<span class="text-xs text-muted text-mono">' + formatDate(node.created_at) + '</span>' +
        '</div>' +
        '<h3 class="text-display" style="font-size:1.25rem;line-height:1.4">' +
        escapeHtml(node.title || '未命名节点') + '</h3>' +
        (node.abstract
          ? '<div><h6>摘要</h6><p class="text-sm text-secondary">' + escapeHtml(node.abstract) + '</p></div>'
          : '') +
        (metaKeys.length
          ? '<div><h6 class="mb-sm">元数据</h6><div class="code-block">' +
            escapeHtml(JSON.stringify(metadata, null, 2)) + '</div></div>'
          : '') +
        '</div>';
      showDrawer({ title: '节点详情', bodyHtml: bodyHtml });
    },

    /** 删除确认 */
    confirmDelete(id) {
      const overlay = document.createElement('div');
      overlay.className = 'drawer-overlay';
      const dialog = document.createElement('div');
      dialog.className = 'drawer';
      dialog.style.width = 'min(420px, 90vw)';
      dialog.innerHTML =
        '<div class="drawer__header"><h3 class="drawer__title">确认删除</h3>' +
        '<button class="drawer__close" data-cancel><i data-lucide="x"></i></button></div>' +
        '<div class="drawer__body">' +
        '<div class="flex items-start gap-md">' +
        '<i data-lucide="alert-triangle" style="width:22px;height:22px;color:var(--warning);flex-shrink:0;margin-top:2px"></i>' +
        '<p class="text-sm text-secondary">删除该节点将同时移除与其关联的所有关系边，此操作不可撤销。是否继续？</p>' +
        '</div></div>' +
        '<div class="drawer__footer">' +
        '<button class="btn btn-secondary" data-cancel>取消</button>' +
        '<button class="btn btn-danger" data-confirm><i data-lucide="trash-2"></i> 删除</button>' +
        '</div>';
      overlay.appendChild(dialog);
      const container = document.getElementById('drawer-container');
      if (!container) return;
      container.appendChild(overlay);
      refreshIcons(dialog);

      const close = () => {
        overlay.style.animation = 'fadeIn 200ms reverse forwards';
        setTimeout(() => overlay.remove(), 200);
      };
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) close();
      });
      dialog.querySelectorAll('[data-cancel]').forEach((b) => b.addEventListener('click', close));
      dialog.querySelector('[data-confirm]').addEventListener('click', async () => {
        const btn = dialog.querySelector('[data-confirm]');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> 删除中…';
        try {
          await API.deleteLineageNode(id);
          showToast('节点已删除', 'success');
          // 从选中集合中移除已删除节点
          selectedNodeIds.delete(id);
          close();
          // 刷新列表与图谱
          this.positions = {};
          this.loadNodes();
          this.loadGraph();
        } catch (err) {
          showToast('删除失败：' + (err.message || err), 'error');
          btn.disabled = false;
          btn.innerHTML = '<i data-lucide="trash-2"></i> 删除';
          refreshIcons();
        }
      });
    },

    /** 绑定分页工具栏事件（全选 / 批量删除 / 翻页） */
    bindPaginationEvents(wrap) {
      if (!wrap) return;

      // 全选复选框：仅选中/取消当前页节点
      const selectAll = wrap.querySelector('#select-all-checkbox');
      if (selectAll) {
        selectAll.addEventListener('click', (e) => e.stopPropagation());
        selectAll.addEventListener('change', () => {
          const pageIds = currentPageNodes.map((n) => n.id);
          if (selectAll.checked) {
            pageIds.forEach((nid) => selectedNodeIds.add(nid));
          } else {
            pageIds.forEach((nid) => selectedNodeIds.delete(nid));
          }
          // 同步更新当前页所有节点复选框
          wrap.querySelectorAll('.node-checkbox').forEach((cb) => {
            cb.checked = selectedNodeIds.has(cb.dataset.nodeId);
          });
          this.refreshToolbar();
        });
      }

      // 批量删除按钮
      const batchBtn = wrap.querySelector('#batch-delete-btn');
      if (batchBtn) {
        batchBtn.addEventListener('click', () => {
          this.confirmBatchDelete();
        });
      }

      // 上一页
      const prevBtn = wrap.querySelector('#prev-page-btn');
      if (prevBtn) {
        prevBtn.addEventListener('click', () => {
          if (currentPage > 1) {
            currentPage--;
            selectedNodeIds.clear();
            this.loadNodes();
          }
        });
      }

      // 下一页
      const nextBtn = wrap.querySelector('#next-page-btn');
      if (nextBtn) {
        nextBtn.addEventListener('click', () => {
          const totalPages = Math.max(1, Math.ceil(totalNodes / PAGE_SIZE));
          if (currentPage < totalPages) {
            currentPage++;
            selectedNodeIds.clear();
            this.loadNodes();
          }
        });
      }
    },

    /** 局部刷新分页工具栏（复选框切换时调用，避免重渲染整个列表） */
    refreshToolbar() {
      const toolbar = document.getElementById('lineage-pagination-toolbar');
      if (!toolbar) return;
      toolbar.outerHTML = paginationToolbar();
      refreshIcons();
      const wrap = document.getElementById('lineage-list');
      if (wrap) this.bindPaginationEvents(wrap);
    },

    /** 批量删除确认 */
    confirmBatchDelete() {
      const ids = Array.from(selectedNodeIds);
      if (!ids.length) return;

      const overlay = document.createElement('div');
      overlay.className = 'drawer-overlay';
      const dialog = document.createElement('div');
      dialog.className = 'drawer';
      dialog.style.width = 'min(420px, 90vw)';
      dialog.innerHTML =
        '<div class="drawer__header"><h3 class="drawer__title">确认批量删除</h3>' +
        '<button class="drawer__close" data-cancel><i data-lucide="x"></i></button></div>' +
        '<div class="drawer__body">' +
        '<div class="flex items-start gap-md">' +
        '<i data-lucide="alert-triangle" style="width:22px;height:22px;color:var(--warning);flex-shrink:0;margin-top:2px"></i>' +
        '<p class="text-sm text-secondary">即将删除选中的 ' + ids.length + ' 个节点及其关联的所有关系边，此操作不可撤销。是否继续？</p>' +
        '</div></div>' +
        '<div class="drawer__footer">' +
        '<button class="btn btn-secondary" data-cancel>取消</button>' +
        '<button class="btn btn-danger" data-confirm><i data-lucide="trash-2"></i> 批量删除</button>' +
        '</div>';
      overlay.appendChild(dialog);
      const container = document.getElementById('drawer-container');
      if (!container) return;
      container.appendChild(overlay);
      refreshIcons(dialog);

      const close = () => {
        overlay.style.animation = 'fadeIn 200ms reverse forwards';
        setTimeout(() => overlay.remove(), 200);
      };
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) close();
      });
      dialog.querySelectorAll('[data-cancel]').forEach((b) => b.addEventListener('click', close));
      dialog.querySelector('[data-confirm]').addEventListener('click', async () => {
        const btn = dialog.querySelector('[data-confirm]');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> 删除中…';
        try {
          const res = await API.batchDeleteLineage(ids);
          const deleted = (res && res.deleted) || 0;
          const failed = (res && res.failed) || [];
          if (failed.length) {
            showToast('已删除 ' + deleted + ' 个，' + failed.length + ' 个失败', 'warning');
          } else {
            showToast('已删除 ' + deleted + ' 个节点', 'success');
          }
          selectedNodeIds.clear();
          close();
          // 刷新列表与图谱
          this.positions = {};
          this.loadNodes();
          this.loadGraph();
        } catch (err) {
          showToast('批量删除失败：' + (err.message || err), 'error');
          btn.disabled = false;
          btn.innerHTML = '<i data-lucide="trash-2"></i> 批量删除';
          refreshIcons();
        }
      });
    },

    /** 打开导入抽屉 */
    openImportDrawer() {
      const typeOptions = NODE_TYPES
        .map(
          (t) =>
            '<option value="' + t + '">' + escapeHtml(typeMeta(t).label) + ' (' + t + ')</option>',
        )
        .join('');

      const bodyHtml =
        '<div class="flex flex-col gap-md">' +
        '<div class="form-section" style="margin-bottom:0">' +
        '<div class="form-section__title" style="margin-bottom:var(--space-sm)">单个节点</div>' +
        '<div class="form-group">' +
        '<label class="form-label">节点类型</label>' +
        '<select id="imp-type" class="form-control">' + typeOptions + '</select>' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">标题</label>' +
        '<input id="imp-title" type="text" class="form-control" placeholder="节点标题" />' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">摘要</label>' +
        '<textarea id="imp-abstract" class="form-control" rows="3" placeholder="节点摘要（可选）"></textarea>' +
        '</div>' +
        '<button id="imp-add-node" class="btn btn-secondary btn-block btn-sm">' +
        '<i data-lucide="plus"></i> 添加到批量列表</button>' +
        '</div>' +
        '<div class="form-section" style="margin-bottom:0">' +
        '<div class="form-section__title" style="margin-bottom:var(--space-sm)">批量导入（JSON）</div>' +
        '<p class="text-xs text-muted mb-sm">粘贴包含 <code class="text-mono text-accent">nodes</code> 与 <code class="text-mono text-accent">edges</code> 数组的 JSON：</p>' +
        '<textarea id="imp-json" class="form-control code-block" rows="8" ' +
        'placeholder="{\n  &quot;nodes&quot;: [{&quot;node_type&quot;:&quot;paper&quot;,&quot;title&quot;:&quot;...&quot;,&quot;abstract&quot;:&quot;...&quot;}],\n  &quot;edges&quot;: [{&quot;source_id&quot;:&quot;...&quot;,&quot;target_id&quot;:&quot;...&quot;,&quot;relation_type&quot;:&quot;cites&quot;}]\n}"></textarea>' +
        '<div id="imp-pending" class="mt-sm"></div>' +
        '</div>' +
        '</div>';

      const footerHtml =
        '<button class="btn btn-secondary" data-drawer-close>取消</button>' +
        '<button id="imp-submit" class="btn btn-primary"><i data-lucide="upload"></i> 提交导入</button>';

      let pendingNodes = [];
      let pendingEdges = [];

      const drawer = showDrawer({
        title: '导入谱系',
        bodyHtml: bodyHtml,
        footerHtml: footerHtml,
        onMount: (el) => {
          refreshIcons(el);

          const pendingWrap = el.querySelector('#imp-pending');

          const renderPending = () => {
            if (!pendingNodes.length && !pendingEdges.length) {
              pendingWrap.innerHTML = '';
              return;
            }
            pendingWrap.innerHTML =
              '<div class="badge badge--success mb-sm">待导入：' + pendingNodes.length +
              ' 节点 / ' + pendingEdges.length + ' 边</div>';
          };

          // 添加单个节点到待导入列表
          const addBtn = el.querySelector('#imp-add-node');
          if (addBtn) {
            addBtn.addEventListener('click', () => {
              const typeEl = el.querySelector('#imp-type');
              const titleEl = el.querySelector('#imp-title');
              const absEl = el.querySelector('#imp-abstract');
              const title = titleEl.value.trim();
              if (!title) {
                showToast('请输入节点标题', 'warning');
                titleEl.focus();
                return;
              }
              pendingNodes.push({
                node_type: typeEl.value,
                title: title,
                abstract: absEl.value.trim(),
                metadata: {},
              });
              titleEl.value = '';
              absEl.value = '';
              renderPending();
              showToast('已加入待导入列表', 'info', { duration: 1500 });
            });
          }

          // 提交导入
          const submitBtn = el.querySelector('#imp-submit');
          if (submitBtn) {
            submitBtn.addEventListener('click', async () => {
              const jsonEl = el.querySelector('#imp-json');
              const jsonText = jsonEl.value.trim();
              let nodes = pendingNodes.slice();
              let edges = pendingEdges.slice();

              // 解析 JSON 批量数据
              if (jsonText) {
                try {
                  const parsed = JSON.parse(jsonText);
                  if (parsed && Array.isArray(parsed.nodes)) {
                    nodes = nodes.concat(parsed.nodes);
                  }
                  if (parsed && Array.isArray(parsed.edges)) {
                    edges = edges.concat(parsed.edges);
                  }
                } catch (e) {
                  showToast('JSON 格式错误：' + e.message, 'error');
                  return;
                }
              }

              if (!nodes.length && !edges.length) {
                showToast('请添加节点或粘贴批量 JSON', 'warning');
                return;
              }

              submitBtn.disabled = true;
              submitBtn.innerHTML = '<span class="spinner"></span> 导入中…';
              try {
                const res = await API.importLineage({ nodes: nodes, edges: edges });
                const nn = (res && res.imported_nodes) || 0;
                const ne = (res && res.imported_edges) || 0;
                showToast('导入成功：' + nn + ' 节点 / ' + ne + ' 边', 'success');
                closeDrawer();
                this.positions = {};
                this.loadNodes();
                this.loadGraph();
              } catch (err) {
                showToast('导入失败：' + (err.message || err), 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i data-lucide="upload"></i> 提交导入';
                refreshIcons();
              }
            });
          }
        },
      });

      // 关闭按钮（footer 中的取消）
      if (drawer) {
        const cancelBtn = drawer.drawer.querySelector('.drawer__footer [data-drawer-close]');
        if (cancelBtn) cancelBtn.addEventListener('click', () => closeDrawer());
      }
    },

    /** 打开知识卡片创建抽屉 */
    openCardDrawer() {
      const bodyHtml =
        '<div class="flex flex-col gap-md">' +
        '<div class="form-group">' +
        '<label class="form-label">标题<span class="required">*</span></label>' +
        '<input id="card-title" type="text" class="form-control" placeholder="卡片标题" />' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">内容<span class="required">*</span></label>' +
        '<textarea id="card-content" class="form-control" rows="5" placeholder="卡片正文内容"></textarea>' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">标签</label>' +
        '<input id="card-tags" type="text" class="form-control" placeholder="多个标签用逗号分隔" />' +
        '</div>' +
        '<div class="form-group">' +
        '<label class="form-label">来源</label>' +
        '<input id="card-source" type="text" class="form-control" placeholder="来源链接或说明（可选）" />' +
        '</div>' +
        '</div>';

      const footerHtml =
        '<button class="btn btn-secondary" data-drawer-close>取消</button>' +
        '<button id="card-submit" class="btn btn-primary"><i data-lucide="plus"></i> 创建卡片</button>';

      const drawer = showDrawer({
        title: '添加知识卡片',
        bodyHtml: bodyHtml,
        footerHtml: footerHtml,
        onMount: (el) => {
          refreshIcons(el);
          const submitBtn = el.querySelector('#card-submit');
          if (submitBtn) {
            submitBtn.addEventListener('click', async () => {
              const title = el.querySelector('#card-title').value.trim();
              const content = el.querySelector('#card-content').value.trim();
              if (!title || !content) {
                showToast('标题与内容不能为空', 'warning');
                return;
              }
              const tagsRaw = el.querySelector('#card-tags').value.trim();
              const tags = tagsRaw
                ? tagsRaw.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
                : [];
              const source = el.querySelector('#card-source').value.trim();

              submitBtn.disabled = true;
              submitBtn.innerHTML = '<span class="spinner"></span> 创建中…';
              try {
                await API.addCard({ title, content, tags, source });
                showToast('知识卡片已创建', 'success');
                closeDrawer();
              } catch (err) {
                showToast('创建失败：' + (err.message || err), 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i data-lucide="plus"></i> 创建卡片';
                refreshIcons();
              }
            });
          }
        },
      });

      if (drawer) {
        const cancelBtn = drawer.drawer.querySelector('.drawer__footer [data-drawer-close]');
        if (cancelBtn) cancelBtn.addEventListener('click', () => closeDrawer());
      }
    },
  };

  /**
   * 将鼠标客户端坐标转换为 SVG 内部坐标
   * @param {SVGSVGElement} svg
   * @param {MouseEvent} e
   * @returns {{x:number,y:number}}
   */
  function clientToSvg(svg, e) {
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const ctm = svg.getScreenCTM();
    if (ctm) {
      const inv = ctm.inverse();
      const r = pt.matrixTransform(inv);
      return { x: r.x, y: r.y };
    }
    return { x: e.clientX, y: e.clientY };
  }
})();
