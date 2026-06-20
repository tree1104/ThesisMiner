/* ==========================================================================
   ThesisMiner v8.0 - 谱系管理页面 (D3.js 力导向图谱重构)
   节点列表 + D3 力导向关系图 + 类型过滤 + 节点详情侧栏
   ========================================================================== */
(function () {
  'use strict';

  /* ------------------------------------------------------------------------
     常量与类型映射
     ------------------------------------------------------------------------ */

  // 节点类型 -> 颜色 / 图标 / 标签映射（v8.0 新配色方案）
  var TYPE_META = {
    paper: { color: '#F59E0B', icon: 'file-text', label: '文献' },
    topic: { color: '#3B82F6', icon: 'lightbulb', label: '论题' },
    method: { color: '#10B981', icon: 'wrench', label: '方法' },
    author: { color: '#8B5CF6', icon: 'user', label: '导师' },
    concept: { color: '#EC4899', icon: 'bookmark', label: '概念' },
    dataset: { color: '#6B7280', icon: 'database', label: '数据' },
  };

  var NODE_TYPES = ['paper', 'topic', 'method', 'author', 'concept', 'dataset'];

  // 节点类型 -> 内联 SVG 路径（24x24 viewBox，用于 D3 节点中心图标）
  var TYPE_ICON_PATHS = {
    paper: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8',
    topic: 'M9 18h6 M10 22h4 M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14',
    method: 'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z',
    author: 'M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2 M12 7a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
    concept: 'M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z',
    dataset: 'M12 2C6.5 2 2 3.5 2 5v14c0 1.5 4.5 3 10 3s10-1.5 10-3V5c0-1.5-4.5-3-10-3z M2 5c0 1.5 4.5 3 10 3s10-1.5 10-3 M2 12c0 1.5 4.5 3 10 3s10-1.5 10-3',
  };

  // 设计令牌
  var PRIMARY_COLOR = '#4F46E5';
  var GRAPH_BG = '#F9FAFB';
  var EDGE_COLOR = '#9CA3AF';
  var EDGE_HIGHLIGHT = '#4F46E5';
  var LABEL_COLOR = '#374151';
  var EDGE_LABEL_COLOR = '#6B7280';
  var SELECTED_RING = '#FCD34D';

  /* ------------------------------------------------------------------------
     状态
     ------------------------------------------------------------------------ */

  // 分页状态
  var currentPage = 1;
  var PAGE_SIZE = 20;
  var totalNodes = 0;
  var selectedNodeIds = new Set();
  var currentPageNodes = [];

  // 图谱状态
  var activeFilters = new Set(NODE_TYPES); // 默认全部显示
  var selectedGraphNodeId = null;
  var hoveredNodeId = null;
  var searchKeyword = ''; // 当前搜索关键词（用于图谱高亮）

  // D3 力导向图谱状态
  var simulation = null;
  var svgSel = null;
  var gRoot = null;
  var zoomBehavior = null;
  var linkSel = null;
  var nodeSel = null;
  var edgeLabelSel = null;
  var allGraphNodes = [];
  var allGraphEdges = [];
  var graphWidth = 0;
  var graphHeight = 560;

  /* ------------------------------------------------------------------------
     辅助函数
     ------------------------------------------------------------------------ */

  /** 取节点类型元信息，未知类型回退到默认 */
  function typeMeta(type) {
    return TYPE_META[type] || { color: '#6B7280', icon: 'circle', label: type || '节点' };
  }

  /** 关系类型 -> 中文标签 */
  function relationLabel(rel) {
    var map = {
      derives: '衍生',
      cites: '引用',
      advises: '指导',
      related: '关联',
      derived_from: '衍生',
      cited_by: '引用',
      advised_by: '指导',
    };
    return map[rel] || rel || '关联';
  }

  /** 检查 D3 是否已加载 */
  function d3Available() {
    return typeof window.d3 !== 'undefined' && window.d3.forceSimulation;
  }

  /* ------------------------------------------------------------------------
     页面结构渲染
     ------------------------------------------------------------------------ */

  /**
   * 主入口：渲染谱系页面骨架
   * @returns {string} HTML 字符串
   */
  function renderLineagePage() {
    return (
      '<header class="page-header">' +
      '<div class="page-header__eyebrow">ThesisMiner · Lineage</div>' +
      '<h1 class="page-header__title">学术谱系</h1>' +
      '<p class="page-header__desc">管理论文、论题、方法等知识节点及其关系，以力导向图谱可视化你的学术脉络传承。</p>' +
      '</header>' +
      '<div class="page-body">' +
      '<!-- 顶部工具栏 -->' +
      renderToolbar() +
      '<!-- 主体两列布局 -->' +
      '<div class="lineage-layout">' +
      '<!-- 左列：节点列表 -->' +
      '<section class="lineage-list-section">' +
      '<div class="lineage-section-header">' +
      '<h2 class="heading-accent lineage-section-title">节点列表</h2>' +
      '<span id="node-count" class="badge badge--default"></span>' +
      '</div>' +
      '<div id="lineage-list" class="list stagger">' +
      '<div class="skeleton skeleton--block"></div>' +
      '<div class="skeleton skeleton--block"></div>' +
      '</div>' +
      '</section>' +
      '<!-- 右列：图谱可视化 -->' +
      '<section class="lineage-graph-section">' +
      '<div class="lineage-section-header">' +
      '<h2 class="heading-accent lineage-section-title">关系图谱</h2>' +
      '<div class="lineage-graph-controls">' +
      '<button class="btn btn-ghost btn-sm" id="lineage-zoom-in" title="放大">' +
      '<i data-lucide="zoom-in"></i></button>' +
      '<button class="btn btn-ghost btn-sm" id="lineage-zoom-out" title="缩小">' +
      '<i data-lucide="zoom-out"></i></button>' +
      '<button class="btn btn-ghost btn-sm" id="lineage-reset-view" title="重置视图（居中并自适应）">' +
      '<i data-lucide="locate"></i><span>重置视图</span></button>' +
      '<button class="btn btn-ghost btn-sm" id="lineage-reset-layout" title="重置布局">' +
      '<i data-lucide="refresh-cw"></i><span>重置布局</span></button>' +
      '<button class="btn btn-ghost btn-sm" id="lineage-fullscreen" title="全屏">' +
      '<i data-lucide="maximize-2"></i><span>全屏</span></button>' +
      '</div>' +
      '</div>' +
      '<div class="lineage-graph-wrap" id="lineage-graph-wrap">' +
      '<div id="lineage-graph" style="height:' + graphHeight + 'px;position:relative">' +
      '<div class="loading-overlay" style="height:100%">' +
      '<div class="spinner spinner--lg"></div>' +
      '</div>' +
      '</div>' +
      '<!-- 图例 -->' +
      '<div class="lineage-legend" id="lineage-legend"></div>' +
      '<!-- 节点详情侧栏 -->' +
      '<div class="lineage-detail" id="lineage-detail"></div>' +
      '</div>' +
      '</section>' +
      '</div>' +
      '</div>'
    );
  }

  /**
   * 渲染顶部工具栏（搜索 + 类型过滤 + 操作按钮）
   * @returns {string}
   */
  function renderToolbar() {
    // 类型过滤复选框
    var filterItems = NODE_TYPES
      .map(function (t) {
        var meta = typeMeta(t);
        var checked = activeFilters.has(t) ? 'checked' : '';
        return (
          '<label class="lineage-filter__item" data-filter-type="' + t + '">' +
          '<input type="checkbox" class="lineage-filter__checkbox" data-filter-type="' + t + '" ' + checked + ' />' +
          '<span class="lineage-type-dot" style="background:' + meta.color + '"></span>' +
          '<span>' + escapeHtml(meta.label) + '</span>' +
          '</label>'
        );
      })
      .join('');

    return (
      '<div class="lineage-toolbar" id="lineage-toolbar">' +
      '<div class="lineage-toolbar__left">' +
      '<div class="relative lineage-search-wrap">' +
      '<i data-lucide="search" style="position:absolute;left:12px;top:50%;transform:translateY(-50%);width:16px;height:16px;color:var(--text-muted)"></i>' +
      '<input id="lineage-search" type="text" class="form-control" placeholder="搜索节点标题..." style="padding-left:38px" />' +
      '</div>' +
      '<div class="lineage-filter">' +
      '<span class="lineage-filter__label">类型筛选:</span>' +
      filterItems +
      '</div>' +
      '</div>' +
      '<div class="lineage-toolbar__right">' +
      '<button class="btn btn-secondary" data-action="open-import">' +
      '<i data-lucide="upload"></i> 导入</button>' +
      '<button class="btn btn-secondary" data-action="open-card">' +
      '<i data-lucide="plus"></i> 添加卡片</button>' +
      '</div>' +
      '</div>'
    );
  }

  /**
   * 渲染图例
   * @returns {string}
   */
  function renderLegend() {
    var items = NODE_TYPES
      .map(function (t) {
        var meta = typeMeta(t);
        return (
          '<div class="lineage-legend__item">' +
          '<span class="lineage-type-dot" style="background:' + meta.color + '"></span>' +
          '<span>' + escapeHtml(meta.label) + '</span>' +
          '</div>'
        );
      })
      .join('');
    return items;
  }

  /* ------------------------------------------------------------------------
     节点列表渲染
     ------------------------------------------------------------------------ */

  /**
   * 渲染节点列表条目
   * @param {object} node
   * @returns {string}
   */
  function nodeItem(node) {
    var meta = typeMeta(node.node_type);
    var isChecked = selectedNodeIds.has(node.id);
    return (
      '<div class="list-item list-item--clickable lineage-list-item" data-node-id="' + escapeHtml(node.id) + '">' +
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
      '<div class="empty-state__icon"><i data-lucide="git-fork"></i></div>' +
      '<div class="empty-state__title">暂无图谱数据</div>' +
      '<p class="empty-state__desc">导入谱系节点与关系后，将在此处以力导向图谱展示学术脉络。</p>' +
      '<button class="btn btn-primary btn-sm mt-md" data-action="open-import">' +
      '<i data-lucide="upload"></i> 导入谱系</button>' +
      '</div>'
    );
  }

  /** 列表空状态 */
  function listEmpty() {
    return (
      '<div class="empty-state">' +
      '<div class="empty-state__icon"><i data-lucide="git-fork"></i></div>' +
      '<div class="empty-state__title">尚未建立谱系</div>' +
      '<p class="empty-state__desc">点击「导入」按钮，添加论文、论题、方法等节点，构建你的学术脉络。</p>' +
      '</div>'
    );
  }

  /**
   * 渲染分页工具栏：全选 / 批量删除 / 页码导航
   * @returns {string}
   */
  function paginationToolbar() {
    var totalPages = Math.max(1, Math.ceil(totalNodes / PAGE_SIZE));
    var hasPrev = currentPage > 1;
    var hasNext = currentPage < totalPages;
    var selectedCount = selectedNodeIds.size;
    var pageIds = currentPageNodes.map(function (n) { return n.id; });
    var allSelected = pageIds.length > 0 && pageIds.every(function (id) { return selectedNodeIds.has(id); });
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

  /**
   * 渲染节点列表（含分页工具栏）
   * @param {Array} nodes 当前页节点
   * @param {boolean} isSearch 是否搜索模式
   */
  function renderNodeList(nodes, isSearch) {
    var wrap = document.getElementById('lineage-list');
    if (!wrap) return;

    if (!nodes.length) {
      wrap.innerHTML = listEmpty();
      refreshIcons();
      return;
    }

    var toolbarHtml = isSearch ? '' : paginationToolbar();
    wrap.innerHTML = toolbarHtml + nodes.map(nodeItem).join('');
    refreshIcons();

    // 绑定分页工具栏事件
    if (!isSearch) {
      bindPaginationEvents(wrap);
    }

    // 复选框：阻止冒泡并切换选中状态
    wrap.querySelectorAll('.node-checkbox').forEach(function (cb) {
      cb.addEventListener('click', function (e) { e.stopPropagation(); });
      cb.addEventListener('change', function () {
        var id = cb.dataset.nodeId;
        if (cb.checked) {
          selectedNodeIds.add(id);
        } else {
          selectedNodeIds.delete(id);
        }
        // 同步图谱高亮：选中节点在图中高亮
        highlightSelectedInGraph();
        refreshToolbar();
      });
    });

    // 点击节点 -> 弹出详情抽屉 + 图谱高亮
    wrap.querySelectorAll('[data-node-id]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        if (e.target.closest('[data-delete-node]')) return;
        if (e.target.closest('.node-checkbox')) return;
        var id = el.dataset.nodeId;
        var target = nodes.find(function (x) { return x.id === id; });
        if (target) {
          // 在图谱中选中并显示侧栏详情
          selectGraphNode(id);
          showNodeDrawer(target);
        }
      });
    });

    // 单个删除节点
    wrap.querySelectorAll('[data-delete-node]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var id = btn.dataset.deleteNode;
        confirmDelete(id);
      });
    });
  }

  /* ------------------------------------------------------------------------
     D3 力导向图谱渲染
     ------------------------------------------------------------------------ */

  /**
   * 使用 D3.js v7 渲染力导向交互图谱
   * @param {HTMLElement} container 图谱容器
   * @param {Array} nodes 节点列表
   * @param {Array} edges 边列表（含 source_id / target_id / relation_type）
   */
  function renderForceGraph(container, nodes, edges) {
    if (!nodes.length) {
      container.innerHTML = graphEmpty();
      refreshIcons();
      container.querySelectorAll('[data-action="open-import"]').forEach(function (btn) {
        btn.addEventListener('click', function () { openImportDrawer(); });
      });
      return;
    }

    // D3 未加载时回退到提示
    if (!d3Available()) {
      container.innerHTML =
        '<div class="empty-state" style="height:100%">' +
        '<div class="empty-state__icon"><i data-lucide="alert-circle"></i></div>' +
        '<div class="empty-state__title">D3.js 未加载</div>' +
        '<p class="empty-state__desc">力导向图谱依赖 D3.js v7，请检查网络连接。</p>' +
        '</div>';
      refreshIcons();
      return;
    }

    // 清空容器
    container.innerHTML = '';
    graphWidth = Math.max(container.clientWidth || 600, 400);

    // 计算节点度数（连接数），用于决定半径大小
    var degreeMap = {};
    edges.forEach(function (e) {
      var s = e.source_id || e.source;
      var t = e.target_id || e.target;
      if (s) degreeMap[s] = (degreeMap[s] || 0) + 1;
      if (t) degreeMap[t] = (degreeMap[t] || 0) + 1;
    });

    // 准备 D3 数据（深拷贝避免污染原始数据）
    var simNodes = nodes.map(function (n) {
      return Object.assign({}, n, {
        degree: degreeMap[n.id] || 0,
      });
    });

    var simLinks = edges
      .map(function (e) {
        var sId = e.source_id || (typeof e.source === 'object' ? e.source.id : e.source);
        var tId = e.target_id || (typeof e.target === 'object' ? e.target.id : e.target);
        if (!sId || !tId) return null;
        return {
          source: sId,
          target: tId,
          relation: e.relation_type || e.relation || 'related',
          weight: e.weight || 1,
          raw: e,
        };
      })
      .filter(Boolean);

    allGraphNodes = simNodes;
    allGraphEdges = simLinks;

    // 创建 SVG
    svgSel = d3
      .select(container)
      .append('svg')
      .attr('width', '100%')
      .attr('height', graphHeight)
      .attr('viewBox', '0 0 ' + graphWidth + ' ' + graphHeight)
      .attr('id', 'lineage-svg')
      .style('background', GRAPH_BG)
      .style('display', 'block')
      .style('border-radius', '8px')
      .style('cursor', 'grab');

    // 缩放行为
    zoomBehavior = d3
      .zoom()
      .scaleExtent([0.2, 4])
      .on('zoom', function (event) {
        if (gRoot) gRoot.attr('transform', event.transform);
      });

    svgSel.call(zoomBehavior);

    // 根分组（所有图谱元素挂在此处，受 zoom 控制）
    gRoot = svgSel.append('g').attr('class', 'lineage-g-root');

    // 箭头定义
    var defs = svgSel.append('defs');

    defs
      .append('marker')
      .attr('id', 'graph-arrow')
      .attr('viewBox', '0 0 10 10')
      .attr('refX', 10)
      .attr('refY', 5)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto-start-reverse')
      .append('path')
      .attr('d', 'M0,0 L10,5 L0,10 z')
      .attr('fill', EDGE_COLOR);

    defs
      .append('marker')
      .attr('id', 'graph-arrow-hl')
      .attr('viewBox', '0 0 10 10')
      .attr('refX', 10)
      .attr('refY', 5)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto-start-reverse')
      .append('path')
      .attr('d', 'M0,0 L10,5 L0,10 z')
      .attr('fill', EDGE_HIGHLIGHT);

    // 边图层
    var linkG = gRoot.append('g').attr('class', 'lineage-links');
    linkSel = linkG
      .selectAll('line')
      .data(simLinks)
      .enter()
      .append('line')
      .attr('stroke', EDGE_COLOR)
      .attr('stroke-width', function (d) { return 1 + (d.weight || 1) * 0.5; })
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', 'url(#graph-arrow)')
      .style('cursor', 'pointer')
      .style('pointer-events', 'all');

    // 边交互：悬停高亮 + 点击展示关系详情
    linkSel
      .on('mouseover', function (event, d) {
        d3.select(this)
          .attr('stroke', EDGE_HIGHLIGHT)
          .attr('stroke-opacity', 1)
          .attr('stroke-width', 2 + (d.weight || 1) * 0.5)
          .attr('marker-end', 'url(#graph-arrow-hl)');
      })
      .on('mouseout', function () {
        if (selectedGraphNodeId) {
          var sn = allGraphNodes.find(function (n) { return n.id === selectedGraphNodeId; });
          if (sn) highlightConnections(sn);
          else resetHighlight();
        } else {
          resetHighlight();
        }
      })
      .on('click', function (event, d) {
        event.stopPropagation();
        showEdgeDetail(d);
      });

    // 边标签图层
    var edgeLabelG = gRoot.append('g').attr('class', 'lineage-edge-labels');
    edgeLabelSel = edgeLabelG
      .selectAll('text')
      .data(simLinks)
      .enter()
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('font-size', '9px')
      .attr('fill', EDGE_LABEL_COLOR)
      .attr('pointer-events', 'none')
      .style('user-select', 'none')
      .style('font-family', 'DM Sans, Noto Sans SC, sans-serif')
      .text(function (d) { return relationLabel(d.relation); });

    // 节点图层
    var nodeG = gRoot.append('g').attr('class', 'lineage-nodes');
    nodeSel = nodeG
      .selectAll('g.lineage-node')
      .data(simNodes, function (d) { return d.id; })
      .enter()
      .append('g')
      .attr('class', 'lineage-node')
      .style('cursor', 'grab')
      .call(
        d3
          .drag()
          .on('start', dragstarted)
          .on('drag', dragged)
          .on('end', dragended)
      );

    // 节点圆形
    nodeSel
      .append('circle')
      .attr('r', function (d) { return nodeRadius(d); })
      .attr('fill', function (d) { return typeMeta(d.node_type).color; })
      .attr('fill-opacity', 0.85)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2);

    // 节点中心图标（内联 SVG 路径，白色描边，区分节点类型）
    nodeSel
      .append('path')
      .attr('class', 'lineage-node-icon')
      .attr('d', function (d) { return TYPE_ICON_PATHS[d.node_type] || TYPE_ICON_PATHS.concept; })
      .attr('fill', 'none')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 1.5)
      .attr('stroke-linecap', 'round')
      .attr('stroke-linejoin', 'round')
      .attr('vector-effect', 'non-scaling-stroke')
      .attr('pointer-events', 'none')
      .attr('transform', function (d) {
        var r = nodeRadius(d);
        var scale = (r * 1.1) / 24;
        return 'translate(' + -12 * scale + ',' + -12 * scale + ') scale(' + scale + ')';
      });

    // 节点标签
    nodeSel
      .append('text')
      .attr('class', 'lineage-node-label')
      .attr('text-anchor', 'middle')
      .attr('y', function (d) { return nodeRadius(d) + 14; })
      .attr('font-size', '11px')
      .attr('fill', LABEL_COLOR)
      .attr('pointer-events', 'none')
      .style('user-select', 'none')
      .style('font-family', 'DM Sans, Noto Sans SC, sans-serif')
      .text(function (d) { return truncate(d.title || '', 10); });

    // 节点交互：悬停高亮 + 点击选中
    nodeSel
      .on('mouseover', function (event, d) {
        hoveredNodeId = d.id;
        highlightConnections(d);
      })
      .on('mouseout', function () {
        hoveredNodeId = null;
        if (selectedGraphNodeId) {
          var sn = allGraphNodes.find(function (n) { return n.id === selectedGraphNodeId; });
          if (sn) highlightConnections(sn);
          else resetHighlight();
        } else {
          resetHighlight();
        }
      })
      .on('click', function (event, d) {
        event.stopPropagation();
        selectGraphNode(d.id);
      });

    // 点击背景取消选中
    svgSel.on('click', function () {
      selectedGraphNodeId = null;
      resetHighlight();
      hideNodeDetail();
    });

    // 力导向仿真
    simulation = d3
      .forceSimulation(simNodes)
      .force(
        'link',
        d3
          .forceLink(simLinks)
          .id(function (d) { return d.id; })
          .distance(90)
          .strength(0.4)
      )
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(graphWidth / 2, graphHeight / 2))
      .force(
        'collision',
        d3.forceCollide().radius(function (d) { return nodeRadius(d) + 8; })
      )
      .on('tick', ticked);

    // 仿真稳定后自动居中并自适应缩放
    simulation.on('end', function () {
      autoFitGraph();
    });
    // 兜底：若仿真长时间未结束，2.5 秒后也执行一次自适应
    setTimeout(autoFitGraph, 2500);

    function ticked() {
      linkSel
        .attr('x1', function (d) { return d.source.x; })
        .attr('y1', function (d) { return d.source.y; })
        .attr('x2', function (d) { return d.target.x; })
        .attr('y2', function (d) { return d.target.y; });

      edgeLabelSel
        .attr('x', function (d) { return (d.source.x + d.target.x) / 2; })
        .attr('y', function (d) { return (d.source.y + d.target.y) / 2; });

      nodeSel.attr('transform', function (d) {
        return 'translate(' + d.x + ',' + d.y + ')';
      });
    }

    // 应用初始过滤
    applyFilters();
    // 同步列表选中状态到图谱
    highlightSelectedInGraph();
  }

  /** 计算节点半径（基于度数，8-12 之间） */
  function nodeRadius(d) {
    return 8 + Math.min(d.degree || 0, 4);
  }

  /* ------------------------------------------------------------------------
     D3 拖拽回调
     ------------------------------------------------------------------------ */

  function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
    d3.select(this).style('cursor', 'grabbing');
  }

  function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
  }

  function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
    d3.select(this).style('cursor', 'grab');
  }

  /* ------------------------------------------------------------------------
     图谱高亮与过滤
     ------------------------------------------------------------------------ */

  /** 高亮与指定节点相连的节点和边 */
  function highlightConnections(node) {
    if (!nodeSel || !node) return;

    var connectedIds = new Set([node.id]);
    var connectedEdgeIndices = new Set();

    allGraphEdges.forEach(function (e, i) {
      var s = typeof e.source === 'object' ? e.source.id : e.source;
      var t = typeof e.target === 'object' ? e.target.id : e.target;
      if (s === node.id || t === node.id) {
        connectedIds.add(s);
        connectedIds.add(t);
        connectedEdgeIndices.add(i);
      }
    });

    // 节点透明度
    nodeSel.style('opacity', function (d) {
      return connectedIds.has(d.id) ? 1 : 0.2;
    });

    // 悬停节点放大
    nodeSel.select('circle').attr('r', function (d) {
      var base = nodeRadius(d);
      if (d.id === node.id) return base + 4;
      return base;
    });

    // 边高亮
    linkSel
      .attr('stroke', function (d, i) {
        return connectedEdgeIndices.has(i) ? EDGE_HIGHLIGHT : EDGE_COLOR;
      })
      .attr('stroke-opacity', function (d, i) {
        return connectedEdgeIndices.has(i) ? 1 : 0.12;
      })
      .attr('stroke-width', function (d, i) {
        return connectedEdgeIndices.has(i) ? 2 + (d.weight || 1) * 0.5 : 1;
      })
      .attr('marker-end', function (d, i) {
        return connectedEdgeIndices.has(i) ? 'url(#graph-arrow-hl)' : 'url(#graph-arrow)';
      });

    // 边标签透明度
    edgeLabelSel.style('opacity', function (d, i) {
      return connectedEdgeIndices.has(i) ? 1 : 0.1;
    });

    // 选中节点的金色环
    nodeSel.select('circle').attr('stroke', function (d) {
      if (d.id === selectedGraphNodeId) return SELECTED_RING;
      return '#fff';
    });
    nodeSel.select('circle').attr('stroke-width', function (d) {
      if (d.id === selectedGraphNodeId) return 3;
      return 2;
    });
  }

  /** 重置所有高亮 */
  function resetHighlight() {
    if (!nodeSel) return;

    nodeSel.style('opacity', 1);
    nodeSel.select('circle').attr('r', function (d) { return nodeRadius(d); });

    linkSel
      .attr('stroke', EDGE_COLOR)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', function (d) { return 1 + (d.weight || 1) * 0.5; })
      .attr('marker-end', 'url(#graph-arrow)');

    edgeLabelSel.style('opacity', 1);

    // 保持选中节点的金色环
    nodeSel.select('circle').attr('stroke', function (d) {
      return d.id === selectedGraphNodeId ? SELECTED_RING : '#fff';
    });
    nodeSel.select('circle').attr('stroke-width', function (d) {
      return d.id === selectedGraphNodeId ? 3 : 2;
    });

    // 同步列表选中高亮
    highlightSelectedInGraph();

    // 若有搜索关键词，恢复搜索高亮
    if (searchKeyword) {
      highlightSearchInGraph();
    }
  }

  /** 应用类型过滤：隐藏被过滤掉的节点和边 */
  function applyFilters() {
    if (!nodeSel || !linkSel) return;

    nodeSel.style('display', function (d) {
      return activeFilters.has(d.node_type) ? null : 'none';
    });

    linkSel.style('display', function (d) {
      var s = typeof d.source === 'object' ? d.source : null;
      var t = typeof d.target === 'object' ? d.target : null;
      if (!s) s = allGraphNodes.find(function (n) { return n.id === d.source; });
      if (!t) t = allGraphNodes.find(function (n) { return n.id === d.target; });
      var sType = s ? s.node_type : null;
      var tType = t ? t.node_type : null;
      return activeFilters.has(sType) && activeFilters.has(tType) ? null : 'none';
    });

    edgeLabelSel.style('display', function (d) {
      var s = typeof d.source === 'object' ? d.source : null;
      var t = typeof d.target === 'object' ? d.target : null;
      if (!s) s = allGraphNodes.find(function (n) { return n.id === d.source; });
      if (!t) t = allGraphNodes.find(function (n) { return n.id === d.target; });
      var sType = s ? s.node_type : null;
      var tType = t ? t.node_type : null;
      return activeFilters.has(sType) && activeFilters.has(tType) ? null : 'none';
    });
  }

  /** 在图谱中高亮列表选中的节点（添加金色环） */
  function highlightSelectedInGraph() {
    if (!nodeSel) return;
    nodeSel.select('circle').attr('stroke', function (d) {
      if (d.id === selectedGraphNodeId) return SELECTED_RING;
      if (selectedNodeIds.has(d.id)) return PRIMARY_COLOR;
      return '#fff';
    });
    nodeSel.select('circle').attr('stroke-width', function (d) {
      if (d.id === selectedGraphNodeId) return 3;
      if (selectedNodeIds.has(d.id)) return 2.5;
      return 2;
    });
  }

  /** 选中图谱节点：高亮 + 显示侧栏详情 */
  function selectGraphNode(id) {
    selectedGraphNodeId = id;
    var node = allGraphNodes.find(function (n) { return n.id === id; });
    if (node) {
      highlightConnections(node);
      renderNodeDetail(node);
    }
  }

  /* ------------------------------------------------------------------------
     节点详情侧栏
     ------------------------------------------------------------------------ */

  /**
   * 渲染节点详情侧栏
   * @param {object} node 节点数据
   */
  function renderNodeDetail(node) {
    var panel = document.getElementById('lineage-detail');
    if (!panel || !node) {
      hideNodeDetail();
      return;
    }

    var meta = typeMeta(node.node_type);
    var metadata = node.metadata || {};
    var metaKeys = Object.keys(metadata);

    // 查找关联节点
    var connected = [];
    allGraphEdges.forEach(function (e) {
      var s = typeof e.source === 'object' ? e.source.id : e.source;
      var t = typeof e.target === 'object' ? e.target.id : e.target;
      if (s === node.id) {
        var target = allGraphNodes.find(function (n) { return n.id === t; });
        if (target) connected.push({ node: target, relation: e.relation, direction: 'out' });
      } else if (t === node.id) {
        var source = allGraphNodes.find(function (n) { return n.id === s; });
        if (source) connected.push({ node: source, relation: e.relation, direction: 'in' });
      }
    });

    // 关联论题摘要（如果节点是论文/论题类型，显示其摘要作为相关论题摘要）
    var relatedSummary = '';
    if (node.abstract) {
      relatedSummary =
        '<div class="lineage-detail__section">' +
        '<h6>相关论题摘要</h6>' +
        '<p class="text-sm text-secondary lineage-detail__abstract">' + escapeHtml(node.abstract) + '</p>' +
        '</div>';
    }

    panel.innerHTML =
      '<div class="lineage-detail__header">' +
      '<div class="flex items-center gap-sm">' +
      '<span class="lineage-type-dot" style="background:' + meta.color + '"></span>' +
      '<span class="badge badge--default">' + escapeHtml(meta.label) + '</span>' +
      '</div>' +
      '<button class="lineage-detail__close" id="lineage-detail-close" aria-label="关闭">' +
      '<i data-lucide="x"></i></button>' +
      '</div>' +
      '<h3 class="lineage-detail__title">' + escapeHtml(node.title || '未命名节点') + '</h3>' +
      '<div class="text-xs text-muted text-mono mb-md">' + formatDate(node.created_at) + '</div>' +
      (metaKeys.length
        ? '<div class="lineage-detail__section"><h6>元数据</h6><div class="code-block lineage-detail__meta">' +
          escapeHtml(JSON.stringify(metadata, null, 2)) + '</div></div>'
        : '') +
      relatedSummary +
      '<div class="lineage-detail__section"><h6>关联节点 (' + connected.length + ')</h6>' +
      (connected.length
        ? '<div class="lineage-detail__connections">' +
          connected
            .map(function (c) {
              var cMeta = typeMeta(c.node.node_type);
              return (
                '<div class="lineage-detail__conn" data-node-id="' + escapeHtml(c.node.id) + '">' +
                '<span class="lineage-type-dot" style="background:' + cMeta.color + '"></span>' +
                '<span class="lineage-detail__conn-label">' + escapeHtml(c.node.title || '未命名') + '</span>' +
                '<span class="badge badge--default lineage-detail__conn-rel">' + escapeHtml(relationLabel(c.relation)) + '</span>' +
                '</div>'
              );
            })
            .join('') +
          '</div>'
        : '<p class="text-xs text-muted">暂无关联节点</p>') +
      '</div>';

    panel.classList.add('lineage-detail--open');
    refreshIcons(panel);

    // 绑定关闭按钮
    var closeBtn = panel.querySelector('#lineage-detail-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        selectedGraphNodeId = null;
        resetHighlight();
        hideNodeDetail();
      });
    }

    // 绑定关联节点点击 -> 跳转选中
    panel.querySelectorAll('[data-node-id]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        var id = el.dataset.nodeId;
        selectGraphNode(id);
      });
    });
  }

  /** 隐藏节点详情侧栏 */
  function hideNodeDetail() {
    var panel = document.getElementById('lineage-detail');
    if (panel) panel.classList.remove('lineage-detail--open');
  }

  /** 在侧栏展示边（关系）详情 */
  function showEdgeDetail(edge) {
    var panel = document.getElementById('lineage-detail');
    if (!panel) return;

    var sNode = allGraphNodes.find(function (n) {
      return n.id === (typeof edge.source === 'object' ? edge.source.id : edge.source);
    });
    var tNode = allGraphNodes.find(function (n) {
      return n.id === (typeof edge.target === 'object' ? edge.target.id : edge.target);
    });
    if (!sNode || !tNode) return;

    var sMeta = typeMeta(sNode.node_type);
    var tMeta = typeMeta(tNode.node_type);
    var rel = relationLabel(edge.relation);
    var weight = edge.weight || 1;

    panel.innerHTML =
      '<div class="lineage-detail__header">' +
      '<div class="flex items-center gap-sm">' +
      '<span class="badge badge--accent">' + escapeHtml(rel) + '</span>' +
      '</div>' +
      '<button class="lineage-detail__close" id="lineage-detail-close" aria-label="关闭">' +
      '<i data-lucide="x"></i></button>' +
      '</div>' +
      '<h3 class="lineage-detail__title">关系详情</h3>' +
      '<div class="lineage-detail__section">' +
      '<h6>起点节点</h6>' +
      '<div class="flex items-center gap-sm">' +
      '<span class="lineage-type-dot" style="background:' + sMeta.color + '"></span>' +
      '<span class="text-sm font-medium">' + escapeHtml(sNode.title || '未命名') + '</span>' +
      '<span class="badge badge--default">' + escapeHtml(sMeta.label) + '</span>' +
      '</div>' +
      '</div>' +
      '<div class="lineage-detail__section">' +
      '<h6>终点节点</h6>' +
      '<div class="flex items-center gap-sm">' +
      '<span class="lineage-type-dot" style="background:' + tMeta.color + '"></span>' +
      '<span class="text-sm font-medium">' + escapeHtml(tNode.title || '未命名') + '</span>' +
      '<span class="badge badge--default">' + escapeHtml(tMeta.label) + '</span>' +
      '</div>' +
      '</div>' +
      '<div class="lineage-detail__section">' +
      '<h6>关系属性</h6>' +
      '<div class="text-sm text-secondary">' +
      '<div class="mb-xs"><strong>关系类型：</strong>' + escapeHtml(rel) + ' (' + escapeHtml(edge.relation || 'related') + ')</div>' +
      '<div><strong>权重：</strong>' + weight + '</div>' +
      '</div>' +
      '</div>';

    panel.classList.add('lineage-detail--open');
    refreshIcons(panel);

    var closeBtn = panel.querySelector('#lineage-detail-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        resetHighlight();
        hideNodeDetail();
      });
    }
  }

  /** 自动居中并缩放图谱以适应所有节点 */
  function autoFitGraph() {
    if (!svgSel || !allGraphNodes.length || !zoomBehavior) return;
    var padding = 60;
    var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    allGraphNodes.forEach(function (n) {
      if (n.x == null || n.y == null) return;
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    });
    if (!isFinite(minX) || !isFinite(maxX)) return;
    var bw = Math.max(maxX - minX, 1);
    var bh = Math.max(maxY - minY, 1);
    var scale = Math.min(
      (graphWidth - padding * 2) / bw,
      (graphHeight - padding * 2) / bh,
      2
    );
    scale = Math.max(scale, 0.2);
    var cx = (minX + maxX) / 2;
    var cy = (minY + maxY) / 2;
    var tx = graphWidth / 2 - scale * cx;
    var ty = graphHeight / 2 - scale * cy;
    svgSel
      .transition()
      .duration(500)
      .call(
        zoomBehavior.transform,
        d3.zoomIdentity.translate(tx, ty).scale(scale)
      );
  }

  /* ------------------------------------------------------------------------
     图谱控制：重置布局 / 全屏
     ------------------------------------------------------------------------ */

  /** 重置力导向布局（重新启动仿真并居中） */
  function resetLayout() {
    if (!simulation || !svgSel) return;
    // 释放所有固定位置
    allGraphNodes.forEach(function (n) {
      n.fx = null;
      n.fy = null;
    });
    // 重置缩放
    svgSel.transition().duration(400).call(zoomBehavior.transform, d3.zoomIdentity);
    // 重启仿真
    simulation.alpha(1).restart();
    // 仿真稳定后自动适配视图
    setTimeout(autoFitGraph, 1200);
  }

  /** 重置视图：仅居中并自适应缩放，不重启仿真 */
  function resetView() {
    autoFitGraph();
  }

  /** 放大 */
  function zoomIn() {
    if (!svgSel || !zoomBehavior) return;
    svgSel.transition().duration(200).call(zoomBehavior.scaleBy, 1.3);
  }

  /** 缩小 */
  function zoomOut() {
    if (!svgSel || !zoomBehavior) return;
    svgSel.transition().duration(200).call(zoomBehavior.scaleBy, 1 / 1.3);
  }

  /** 切换全屏模式 */
  function toggleFullscreen() {
    var wrap = document.getElementById('lineage-graph-wrap');
    if (!wrap) return;
    if (!document.fullscreenElement) {
      var req = wrap.requestFullscreen || wrap.webkitRequestFullscreen || wrap.mozRequestFullScreen;
      if (req) {
        req.call(wrap).catch(function (err) {
          showToast('全屏失败：' + (err.message || err), 'error');
        });
      }
    } else {
      var exit = document.exitFullscreen || document.webkitExitFullscreen || document.mozCancelFullScreen;
      if (exit) exit.call(document);
    }
  }

  /** 全屏状态变化时调整图谱尺寸 */
  function handleFullscreenChange() {
    var wrap = document.getElementById('lineage-graph-wrap');
    var graphEl = document.getElementById('lineage-graph');
    if (!wrap || !graphEl) return;
    if (document.fullscreenElement === wrap) {
      graphEl.style.height = '100vh';
      graphWidth = Math.max(window.innerWidth, 400);
      graphHeight = window.innerHeight;
      if (svgSel) {
        svgSel.attr('height', graphHeight);
        svgSel.attr('viewBox', '0 0 ' + graphWidth + ' ' + graphHeight);
      }
      if (simulation) {
        simulation.force('center', d3.forceCenter(graphWidth / 2, graphHeight / 2));
        simulation.alpha(0.3).restart();
      }
      setTimeout(autoFitGraph, 1000);
    } else {
      graphHeight = 560;
      graphEl.style.height = graphHeight + 'px';
      if (svgSel) {
        var w = Math.max(graphEl.clientWidth || 600, 400);
        graphWidth = w;
        svgSel.attr('height', graphHeight);
        svgSel.attr('viewBox', '0 0 ' + w + ' ' + graphHeight);
      }
      if (simulation) {
        var cw = Math.max(graphEl.clientWidth || 600, 400);
        simulation.force('center', d3.forceCenter(cw / 2, graphHeight / 2));
        simulation.alpha(0.3).restart();
      }
      setTimeout(autoFitGraph, 1000);
    }
  }

  /* ------------------------------------------------------------------------
     数据加载
     ------------------------------------------------------------------------ */

  /** 加载节点列表 */
  async function loadNodes(keyword) {
    var wrap = document.getElementById('lineage-list');
    var countEl = document.getElementById('node-count');
    if (!wrap) return;
    try {
      var nodes = [];
      var isSearch = false;
      if (keyword) {
        isSearch = true;
        var sRes = await API.searchLineage(keyword);
        nodes = (sRes && sRes.results) || [];
        totalNodes = nodes.length;
      } else {
        var offset = (currentPage - 1) * PAGE_SIZE;
        var res = await API.getLineage(PAGE_SIZE, offset);
        nodes = (res && res.nodes) || [];
        totalNodes = (res && res.total) || 0;
      }

      currentPageNodes = nodes;

      if (countEl) countEl.textContent = '共 ' + totalNodes + ' 个';

      renderNodeList(nodes, isSearch);
    } catch (err) {
      wrap.innerHTML =
        '<div class="empty-state">' +
        '<div class="empty-state__icon"><i data-lucide="alert-circle"></i></div>' +
        '<div class="empty-state__title">节点加载失败</div>' +
        '<p class="empty-state__desc">' + escapeHtml(err.message || String(err)) + '</p>' +
        '</div>';
      refreshIcons();
    }
  }

  /** 加载图谱数据并渲染 */
  async function loadGraph() {
    var wrap = document.getElementById('lineage-graph');
    if (!wrap) return;
    try {
      var res = await API.getLineageGraph();
      var nodes = (res && res.nodes) || [];
      var edges = (res && res.edges) || [];
      renderForceGraph(wrap, nodes, edges);
    } catch (err) {
      wrap.innerHTML =
        '<div class="empty-state" style="height:100%">' +
        '<div class="empty-state__icon"><i data-lucide="alert-circle"></i></div>' +
        '<div class="empty-state__title">图谱加载失败</div>' +
        '<p class="empty-state__desc">' + escapeHtml(err.message || String(err)) + '</p>' +
        '</div>';
      refreshIcons();
    }
  }

  /* ------------------------------------------------------------------------
     分页与批量操作
     ------------------------------------------------------------------------ */

  /** 绑定分页工具栏事件（全选 / 批量删除 / 翻页） */
  function bindPaginationEvents(wrap) {
    if (!wrap) return;

    // 全选复选框：仅选中/取消当前页节点
    var selectAll = wrap.querySelector('#select-all-checkbox');
    if (selectAll) {
      selectAll.addEventListener('click', function (e) { e.stopPropagation(); });
      selectAll.addEventListener('change', function () {
        var pageIds = currentPageNodes.map(function (n) { return n.id; });
        if (selectAll.checked) {
          pageIds.forEach(function (nid) { selectedNodeIds.add(nid); });
        } else {
          pageIds.forEach(function (nid) { selectedNodeIds.delete(nid); });
        }
        wrap.querySelectorAll('.node-checkbox').forEach(function (cb) {
          cb.checked = selectedNodeIds.has(cb.dataset.nodeId);
        });
        highlightSelectedInGraph();
        refreshToolbar();
      });
    }

    // 批量删除按钮
    var batchBtn = wrap.querySelector('#batch-delete-btn');
    if (batchBtn) {
      batchBtn.addEventListener('click', function () {
        confirmBatchDelete();
      });
    }

    // 上一页
    var prevBtn = wrap.querySelector('#prev-page-btn');
    if (prevBtn) {
      prevBtn.addEventListener('click', function () {
        if (currentPage > 1) {
          currentPage--;
          selectedNodeIds.clear();
          loadNodes();
        }
      });
    }

    // 下一页
    var nextBtn = wrap.querySelector('#next-page-btn');
    if (nextBtn) {
      nextBtn.addEventListener('click', function () {
        var totalPages = Math.max(1, Math.ceil(totalNodes / PAGE_SIZE));
        if (currentPage < totalPages) {
          currentPage++;
          selectedNodeIds.clear();
          loadNodes();
        }
      });
    }
  }

  /** 局部刷新分页工具栏 */
  function refreshToolbar() {
    var toolbar = document.getElementById('lineage-pagination-toolbar');
    if (!toolbar) return;
    toolbar.outerHTML = paginationToolbar();
    refreshIcons();
    var wrap = document.getElementById('lineage-list');
    if (wrap) bindPaginationEvents(wrap);
  }

  /** 删除确认 */
  function confirmDelete(id) {
    var overlay = document.createElement('div');
    overlay.className = 'drawer-overlay';
    var dialog = document.createElement('div');
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
    var container = document.getElementById('drawer-container');
    if (!container) return;
    container.appendChild(overlay);
    refreshIcons(dialog);

    var close = function () {
      overlay.style.animation = 'fadeIn 200ms reverse forwards';
      setTimeout(function () { overlay.remove(); }, 200);
    };
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });
    dialog.querySelectorAll('[data-cancel]').forEach(function (b) {
      b.addEventListener('click', close);
    });
    dialog.querySelector('[data-confirm]').addEventListener('click', async function () {
      var btn = dialog.querySelector('[data-confirm]');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> 删除中…';
      try {
        await API.deleteLineageNode(id);
        showToast('节点已删除', 'success');
        selectedNodeIds.delete(id);
        close();
        loadNodes();
        loadGraph();
      } catch (err) {
        showToast('删除失败：' + (err.message || err), 'error');
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="trash-2"></i> 删除';
        refreshIcons();
      }
    });
  }

  /** 批量删除确认 */
  function confirmBatchDelete() {
    var ids = Array.from(selectedNodeIds);
    if (!ids.length) return;

    var overlay = document.createElement('div');
    overlay.className = 'drawer-overlay';
    var dialog = document.createElement('div');
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
    var container = document.getElementById('drawer-container');
    if (!container) return;
    container.appendChild(overlay);
    refreshIcons(dialog);

    var close = function () {
      overlay.style.animation = 'fadeIn 200ms reverse forwards';
      setTimeout(function () { overlay.remove(); }, 200);
    };
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });
    dialog.querySelectorAll('[data-cancel]').forEach(function (b) {
      b.addEventListener('click', close);
    });
    dialog.querySelector('[data-confirm]').addEventListener('click', async function () {
      var btn = dialog.querySelector('[data-confirm]');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> 删除中…';
      try {
        var res = await API.batchDeleteLineage(ids);
        var deleted = (res && res.deleted) || 0;
        var failed = (res && res.failed) || [];
        if (failed.length) {
          showToast('已删除 ' + deleted + ' 个，' + failed.length + ' 个失败', 'warning');
        } else {
          showToast('已删除 ' + deleted + ' 个节点', 'success');
        }
        selectedNodeIds.clear();
        close();
        loadNodes();
        loadGraph();
      } catch (err) {
        showToast('批量删除失败：' + (err.message || err), 'error');
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="trash-2"></i> 批量删除';
        refreshIcons();
      }
    });
  }

  /* ------------------------------------------------------------------------
     导入抽屉与知识卡片
     ------------------------------------------------------------------------ */

  /** 打开导入抽屉 */
  function openImportDrawer() {
    var typeOptions = NODE_TYPES
      .map(function (t) {
        return '<option value="' + t + '">' + escapeHtml(typeMeta(t).label) + ' (' + t + ')</option>';
      })
      .join('');

    var bodyHtml =
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

    var footerHtml =
      '<button class="btn btn-secondary" data-drawer-close>取消</button>' +
      '<button id="imp-submit" class="btn btn-primary"><i data-lucide="upload"></i> 提交导入</button>';

    var pendingNodes = [];
    var pendingEdges = [];

    var drawer = showDrawer({
      title: '导入谱系',
      bodyHtml: bodyHtml,
      footerHtml: footerHtml,
      onMount: function (el) {
        refreshIcons(el);

        var pendingWrap = el.querySelector('#imp-pending');

        var renderPending = function () {
          if (!pendingNodes.length && !pendingEdges.length) {
            pendingWrap.innerHTML = '';
            return;
          }
          pendingWrap.innerHTML =
            '<div class="badge badge--success mb-sm">待导入：' + pendingNodes.length +
            ' 节点 / ' + pendingEdges.length + ' 边</div>';
        };

        var addBtn = el.querySelector('#imp-add-node');
        if (addBtn) {
          addBtn.addEventListener('click', function () {
            var typeEl = el.querySelector('#imp-type');
            var titleEl = el.querySelector('#imp-title');
            var absEl = el.querySelector('#imp-abstract');
            var title = titleEl.value.trim();
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

        var submitBtn = el.querySelector('#imp-submit');
        if (submitBtn) {
          submitBtn.addEventListener('click', async function () {
            var jsonEl = el.querySelector('#imp-json');
            var jsonText = jsonEl.value.trim();
            var nodes = pendingNodes.slice();
            var edges = pendingEdges.slice();

            if (jsonText) {
              try {
                var parsed = JSON.parse(jsonText);
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
              var res = await API.importLineage({ nodes: nodes, edges: edges });
              var nn = (res && res.imported_nodes) || 0;
              var ne = (res && res.imported_edges) || 0;
              showToast('导入成功：' + nn + ' 节点 / ' + ne + ' 边', 'success');
              closeDrawer();
              loadNodes();
              loadGraph();
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

    if (drawer) {
      var cancelBtn = drawer.drawer.querySelector('.drawer__footer [data-drawer-close]');
      if (cancelBtn) cancelBtn.addEventListener('click', function () { closeDrawer(); });
    }
  }

  /** 打开知识卡片创建抽屉 */
  function openCardDrawer() {
    var bodyHtml =
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

    var footerHtml =
      '<button class="btn btn-secondary" data-drawer-close>取消</button>' +
      '<button id="card-submit" class="btn btn-primary"><i data-lucide="plus"></i> 创建卡片</button>';

    var drawer = showDrawer({
      title: '添加知识卡片',
      bodyHtml: bodyHtml,
      footerHtml: footerHtml,
      onMount: function (el) {
        refreshIcons(el);
        var submitBtn = el.querySelector('#card-submit');
        if (submitBtn) {
          submitBtn.addEventListener('click', async function () {
            var title = el.querySelector('#card-title').value.trim();
            var content = el.querySelector('#card-content').value.trim();
            if (!title || !content) {
              showToast('标题与内容不能为空', 'warning');
              return;
            }
            var tagsRaw = el.querySelector('#card-tags').value.trim();
            var tags = tagsRaw
              ? tagsRaw.split(/[,，]/).map(function (s) { return s.trim(); }).filter(Boolean)
              : [];
            var source = el.querySelector('#card-source').value.trim();

            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span> 创建中…';
            try {
              await API.addCard({ title: title, content: content, tags: tags, source: source });
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
      var cancelBtn = drawer.drawer.querySelector('.drawer__footer [data-drawer-close]');
      if (cancelBtn) cancelBtn.addEventListener('click', function () { closeDrawer(); });
    }
  }

  /** 节点详情抽屉（列表点击时弹出完整详情） */
  function showNodeDrawer(node) {
    var meta = typeMeta(node.node_type);
    var metadata = node.metadata || {};
    var metaKeys = Object.keys(metadata);
    var bodyHtml =
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
  }

  /* ------------------------------------------------------------------------
     工具栏事件绑定
     ------------------------------------------------------------------------ */

  /** 绑定工具栏与全局动作 */
  function bindToolbar(root) {
    if (!root) return;

    // 搜索（防抖实时搜索）
    var search = root.querySelector('#lineage-search');
    if (search) {
      var handler = debounce(function (val) { handleSearch(val); }, 300);
      search.addEventListener('input', function () { handler(search.value.trim()); });
    }

    // 工具栏按钮（导入 / 卡片）
    root.querySelectorAll('[data-action]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var action = btn.dataset.action;
        if (action === 'open-import') openImportDrawer();
        else if (action === 'open-card') openCardDrawer();
      });
    });

    // 类型过滤复选框
    root.querySelectorAll('.lineage-filter__checkbox').forEach(function (cb) {
      cb.addEventListener('change', function () {
        var type = cb.dataset.filterType;
        if (cb.checked) {
          activeFilters.add(type);
        } else {
          activeFilters.delete(type);
        }
        applyFilters();
      });
    });

    // 重置布局按钮
    var resetBtn = root.querySelector('#lineage-reset-layout');
    if (resetBtn) {
      resetBtn.addEventListener('click', function () { resetLayout(); });
    }

    // 重置视图按钮（居中并自适应缩放）
    var resetViewBtn = root.querySelector('#lineage-reset-view');
    if (resetViewBtn) {
      resetViewBtn.addEventListener('click', function () { resetView(); });
    }

    // 放大 / 缩小
    var zoomInBtn = root.querySelector('#lineage-zoom-in');
    if (zoomInBtn) {
      zoomInBtn.addEventListener('click', function () { zoomIn(); });
    }
    var zoomOutBtn = root.querySelector('#lineage-zoom-out');
    if (zoomOutBtn) {
      zoomOutBtn.addEventListener('click', function () { zoomOut(); });
    }

    // 全屏按钮
    var fsBtn = root.querySelector('#lineage-fullscreen');
    if (fsBtn) {
      fsBtn.addEventListener('click', function () { toggleFullscreen(); });
    }
  }

  /** 处理搜索 */
  async function handleSearch(keyword) {
    if (!keyword) {
      currentPage = 1;
    }
    selectedNodeIds.clear();
    searchKeyword = keyword || '';
    highlightSearchInGraph();
    await loadNodes(keyword);
  }

  /** 在图谱中高亮匹配搜索关键词的节点 */
  function highlightSearchInGraph() {
    if (!nodeSel) return;
    if (!searchKeyword) {
      // 清除搜索高亮，恢复正常显示
      nodeSel.select('circle').attr('fill-opacity', 0.85);
      nodeSel.style('opacity', 1);
      return;
    }
    var kw = searchKeyword.toLowerCase();
    nodeSel.style('opacity', function (d) {
      var title = (d.title || '').toLowerCase();
      return title.indexOf(kw) >= 0 ? 1 : 0.25;
    });
    nodeSel.select('circle').attr('fill-opacity', function (d) {
      var title = (d.title || '').toLowerCase();
      return title.indexOf(kw) >= 0 ? 1 : 0.3;
    });
  }

  /* ------------------------------------------------------------------------
     页面注册（暴露给 app.js）
     ------------------------------------------------------------------------ */

  window.Pages = window.Pages || {};
  window.Pages.lineage = {
    /** 渲染页面骨架 */
    render: function () {
      return renderLineagePage();
    },

    /** app.js 调用入口：委托给 mount(container) */
    async init() {
      var container = document.getElementById('app-content');
      if (container) await this.mount(container);
    },

    /** 挂载到主内容区：绑定事件并加载数据 */
    async mount(container) {
      // 重置分页与选中状态
      currentPage = 1;
      selectedNodeIds.clear();
      selectedGraphNodeId = null;
      activeFilters = new Set(NODE_TYPES);
      searchKeyword = '';

      // 渲染图例
      var legend = document.getElementById('lineage-legend');
      if (legend) legend.innerHTML = renderLegend();

      refreshIcons();
      bindToolbar(container);

      // 绑定全屏变化事件
      document.addEventListener('fullscreenchange', handleFullscreenChange);
      document.addEventListener('webkitfullscreenchange', handleFullscreenChange);

      // 加载数据
      loadNodes();
      loadGraph();
    },

    /** 暴露内部方法供外部调用与测试 */
    renderForceGraph: renderForceGraph,
    renderNodeList: renderNodeList,
    renderNodeDetail: renderNodeDetail,
    renderToolbar: renderToolbar,
    renderLineagePage: renderLineagePage,
  };
})();
