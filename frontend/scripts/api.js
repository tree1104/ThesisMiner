/* ==========================================================================
   ThesisMiner v6.0 - API 客户端封装
   统一处理请求、JSON 序列化、错误归集与超时
   ========================================================================== */

const API = {
  // 接口基础路径
  baseUrl: '/api',

  // 默认请求超时（毫秒）
  timeout: 60000,

  /**
   * 统一请求方法
   * @param {string} path - 接口路径（相对 baseUrl）
   * @param {RequestInit} [options={}] - fetch 配置
   * @returns {Promise<any>} 解析后的 JSON 数据
   * @throws {Error} 当网络异常或业务失败时抛出带 message 的错误
   */
  async request(path, options = {}) {
    const url = `${API.baseUrl}${path}`;

    // 默认请求头
    const headers = {
      'Accept': 'application/json',
      ...(options.headers || {}),
    };

    // 若 body 是对象且未显式设置 Content-Type，则按 JSON 处理
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }

    // 超时控制：使用 AbortController
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), API.timeout);
    options.signal = controller.signal;

    let response;
    try {
      response = await fetch(url, { ...options, headers });
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error('请求超时，请检查网络或稍后重试');
      }
      throw new Error(`网络请求失败：${err.message || err}`);
    }
    clearTimeout(timer);

    // 尝试解析 JSON，兼容空响应
    let data = null;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      try {
        data = text ? JSON.parse(text) : null;
      } catch (_) {
        data = { raw: text };
      }
    }

    // HTTP 状态码非 2xx 视为错误
    if (!response.ok) {
      // 优先取后端约定的错误信息
      const message =
        (data && (data.detail || data.error || data.message)) ||
        `请求失败（HTTP ${response.status}）`;
      const error = new Error(message);
      error.status = response.status;
      error.data = data;
      throw error;
    }

    // 业务层错误：后端返回 { success: false, error: ... }
    if (data && data.success === false) {
      const message = data.error || data.message || '操作失败';
      const error = new Error(message);
      error.data = data;
      throw error;
    }

    return data;
  },

  /**
   * 流式请求方法（支持 SSE / chunked transfer）
   * @param {string} path - 接口路径（相对 baseUrl）
   * @param {Object} [options={}] - 请求配置 { method, body, headers }
   * @param {function(string): void} [onChunk] - 每收到一个文本块的回调
   * @returns {Promise<string>} 完整的响应文本
   * @throws {Error} 当网络异常或 HTTP 非 2xx 时抛出
   */
  async streamRequest(path, options = {}, onChunk) {
    const url = `${API.baseUrl}${path}`;
    const headers = {
      'Accept': 'text/plain, text/event-stream',
      ...(options.headers || {}),
    };
    if (options.body && typeof options.body === 'object') {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), API.timeout);
    options.signal = controller.signal;

    let response;
    try {
      response = await fetch(url, { ...options, headers });
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') throw new Error('请求超时');
      throw new Error(`网络请求失败：${err.message || err}`);
    }
    clearTimeout(timer);

    if (!response.ok) {
      let msg = `请求失败（HTTP ${response.status}）`;
      try {
        const errData = await response.json();
        msg = errData.detail || errData.error || errData.message || msg;
      } catch (_) {}
      const error = new Error(msg);
      error.status = response.status;
      throw error;
    }

    // 读取流
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let fullText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      fullText += chunk;
      if (typeof onChunk === 'function') {
        onChunk(chunk);
      }
    }

    return fullText;
  },

  /* ------------------------------------------------------------------------
     配置与状态
     ------------------------------------------------------------------------ */
  /** 获取当前配置（隐藏 api_key） */
  getConfig: () => API.request('/config'),

  /** 更新配置并持久化 */
  updateConfig: (data) =>
    API.request('/config', { method: 'POST', body: JSON.stringify(data) }),

  /** 服务健康状态 */
  getStatus: () => API.request('/status'),

  /* ------------------------------------------------------------------------
     v7.0 模型管理
     ------------------------------------------------------------------------ */
  /** 获取所有模型配置 */
  getModels: () => API.request('/models'),

  /** 新增模型 */
  addModel: (model) =>
    API.request('/models', { method: 'POST', body: JSON.stringify(model) }),

  /** 更新模型 */
  updateModel: (modelId, model) =>
    API.request(`/models/${modelId}`, { method: 'PUT', body: JSON.stringify(model) }),

  /** 删除模型 */
  deleteModel: (modelId) =>
    API.request(`/models/${modelId}`, { method: 'DELETE' }),

  /** 获取步骤路由配置 */
  getStepModels: () => API.request('/step-models'),

  /** 更新步骤路由配置 */
  updateStepModels: (data) =>
    API.request('/step-models', { method: 'PUT', body: JSON.stringify(data) }),

  /** 切换计价货币 */
  updateCurrency: (currency) =>
    API.request('/currency', { method: 'PUT', body: JSON.stringify({ currency }) }),

  /* ------------------------------------------------------------------------
     谱系管理
     ------------------------------------------------------------------------ */
  /** 获取谱系节点列表（支持分页） */
  getLineage: (limit = 20, offset = 0) =>
    API.request(`/lineage?limit=${limit}&offset=${offset}`),

  /** 批量导入谱系节点与边 */
  importLineage: (data) =>
    API.request('/lineage/import', { method: 'POST', body: JSON.stringify(data) }),

  /** 获取谱系图（节点 + 边） */
  getLineageGraph: () => API.request('/lineage/graph'),

  /** 按关键词检索谱系 */
  searchLineage: (keyword) =>
    API.request(`/lineage/search?keyword=${encodeURIComponent(keyword)}`),

  /** 批量删除谱系节点 */
  batchDeleteLineage: (nodeIds) =>
    API.request('/lineage/batch', { method: 'DELETE', body: JSON.stringify({ node_ids: nodeIds }) }),

  /** 删除指定谱系节点 */
  deleteLineageNode: (id) =>
    API.request(`/lineage/${id}`, { method: 'DELETE' }),

  /** 新增知识卡片 */
  addCard: (data) =>
    API.request('/lineage/cards', { method: 'POST', body: JSON.stringify(data) }),

  /** 查询知识卡片，可按标签过滤 */
  getCards: (tag) =>
    API.request(`/lineage/cards${tag ? `?tag=${encodeURIComponent(tag)}` : ''}`),

  /* ------------------------------------------------------------------------
     创意引擎
     ------------------------------------------------------------------------ */
  /** 问题意识激发 */
  inspire: (data) =>
    API.request('/creativity/inspire', { method: 'POST', body: JSON.stringify(data) }),

  /** 跨域联想 */
  crossDomain: (data) =>
    API.request('/creativity/cross-domain', { method: 'POST', body: JSON.stringify(data) }),

  /** 趋势嫁接 */
  trendGraft: (data) =>
    API.request('/creativity/trend-graft', { method: 'POST', body: JSON.stringify(data) }),

  /** 候选排序 */
  rankCandidates: (data) =>
    API.request('/creativity/rank', { method: 'POST', body: JSON.stringify(data) }),

  /** 获取候选列表 */
  getCandidates: (degree, discipline, mentorInfo) =>
    API.request(
      `/creativity/candidates?degree=${degree}&discipline=${discipline}&mentor_info=${encodeURIComponent(mentorInfo)}`,
    ),

  /* ------------------------------------------------------------------------
     论题生成
     ------------------------------------------------------------------------ */
  /** 生成论题提案 */
  generateProposals: (data) =>
    API.request('/proposals/generate', { method: 'POST', body: JSON.stringify(data) }),

  /**
   * 流式生成论题提案（当后端支持流式端点时使用）
   * @param {object} data - 生成参数
   * @param {function(string): void} [onChunk] - 文本块回调
   * @returns {Promise<string>} 完整响应文本
   */
  streamGenerateProposals: (data, onChunk) =>
    API.streamRequest(
      '/proposals/generate-stream',
      { method: 'POST', body: data },
      onChunk,
    ),

  /** 分页查询论题列表 */
  getProposals: (limit = 20, offset = 0, sessionId = null) =>
    API.request(
      `/proposals?limit=${limit}&offset=${offset}${sessionId ? `&session_id=${sessionId}` : ''}`,
    ),

  /** 获取单个论题详情 */
  getProposal: (id) => API.request(`/proposals/${id}`),

  /** 删除论题 */
  deleteProposal: (id) =>
    API.request(`/proposals/${id}`, { method: 'DELETE' }),

  /** 生成开题报告 Markdown 文档 */
  generateReport: (proposalId, useAi = true) =>
    API.request(`/proposals/${proposalId}/report?use_ai=${useAi}`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  /* ------------------------------------------------------------------------
     约束校验
     ------------------------------------------------------------------------ */
  /** 标题格式校验 */
  validateTitle: (data) =>
    API.request('/constraints/validate-title', { method: 'POST', body: JSON.stringify(data) }),

  /** 可行性检查 */
  checkFeasibility: (data) =>
    API.request('/constraints/check-feasibility', { method: 'POST', body: JSON.stringify(data) }),

  /** 文献基线检查 */
  checkLiterature: (data) =>
    API.request('/constraints/check-literature', { method: 'POST', body: JSON.stringify(data) }),

  /** 获取真实文献检索状态（v6.0 新增） */
  getSearchStatus: () => API.request('/constraints/search-status'),

  /** 更新真实文献检索开关（通过 config 端点持久化） */
  updateSearchConfig: (enabled) =>
    API.request('/config', {
      method: 'POST',
      body: JSON.stringify({ real_search_enabled: enabled }),
    }),

  /** 获取学术日历 */
  getCalendar: (degree) => API.request(`/constraints/calendar/${degree}`),

  /** 获取文献基线 */
  getBaseline: (degree) => API.request(`/constraints/baseline/${degree}`),

  /* ------------------------------------------------------------------------
     会话管理
     ------------------------------------------------------------------------ */
  /** 创建会话 */
  createSession: (data) =>
    API.request('/sessions', { method: 'POST', body: JSON.stringify(data) }),

  /** 分页查询会话列表 */
  getSessions: (limit = 20, offset = 0) =>
    API.request(`/sessions?limit=${limit}&offset=${offset}`),

  /** 获取会话详情 */
  getSession: (id) => API.request(`/sessions/${id}`),

  /** 删除会话 */
  deleteSession: (id) =>
    API.request(`/sessions/${id}`, { method: 'DELETE' }),

  /** 更新会话状态 */
  updateSessionStatus: (id, status) =>
    API.request(`/sessions/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),

  /* ------------------------------------------------------------------------
     预算控制
     ------------------------------------------------------------------------ */
  /** 查询预算账本明细 */
  getLedger: (sessionId = null, limit = 50, offset = 0) =>
    API.request(
      `/budgets/ledger?${sessionId ? `session_id=${sessionId}&` : ''}limit=${limit}&offset=${offset}`,
    ),

  /** 预算估算 */
  estimateBudget: (data) =>
    API.request('/budgets/estimate', { method: 'POST', body: JSON.stringify(data) }),

  /** 预算汇总 */
  getBudgetSummary: () => API.request('/budgets/summary'),

  /** 单会话成本 */
  getSessionCost: (sessionId) => API.request(`/budgets/session/${sessionId}`),

  /** 获取定价表 */
  getPricing: () => API.request('/budgets/pricing'),

  /* ------------------------------------------------------------------------
     v8.0 对话管理（多对话隔离 / Agent 路由）
     ------------------------------------------------------------------------ */
  /** 获取指定会话下的全部对话 */
  getConversations: (sessionId) =>
    API.request(`/sessions/${sessionId}/conversations`),

  /** 创建新对话（指定初始 Agent 类型） */
  createConversation: (sessionId, title = '新对话', agentId = 'orchestrator') =>
    API.request(`/sessions/${sessionId}/conversations`, {
      method: 'POST',
      body: JSON.stringify({ title, agent_id: agentId }),
    }),

  /** 获取对话消息列表 */
  getConversationMessages: (conversationId, limit = 100) =>
    API.request(`/conversations/${conversationId}/messages?limit=${limit}`),

  /** 追加一条消息到对话 */
  addMessage: (conversationId, role, content, agentId = '', reasoning = '', citations = []) =>
    API.request(`/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({
        role,
        content,
        agent_id: agentId,
        reasoning,
        citations,
      }),
    }),

  /** 删除对话 */
  deleteConversation: (conversationId) =>
    API.request(`/conversations/${conversationId}`, { method: 'DELETE' }),

  /** 重命名对话 */
  renameConversation: (conversationId, title) =>
    API.request(`/conversations/${conversationId}`, {
      method: 'PUT',
      body: JSON.stringify({ title }),
    }),

  /** 获取可用 Agent 列表 */
  getAgents: () => API.request('/agents'),

  /** 获取指定消息的引用卡片 */
  getMessageCitations: (messageId) =>
    API.request(`/messages/${messageId}/citations`),

  /** 设置会话的当前激活对话 */
  setActiveConversation: (sessionId, conversationId) =>
    API.request(`/sessions/${sessionId}/active-conversation?cid=${conversationId}`, {
      method: 'PUT',
    }),
};

// 暴露到全局，供各页面脚本使用
window.API = API;
