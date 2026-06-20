# ThesisMiner v8.0 前端架构与设计规范

> 本文档详细描述 ThesisMiner v8.0 项目的前端架构、设计规范、组件体系、状态管理、路由设计、性能优化与最佳实践。

## 目录

- [1. 前端概览](#1-前端概览)
- [2. 技术栈选型](#2-技术栈选型)
- [3. 目录结构](#3-目录结构)
- [4. 页面体系](#4-页面体系)
- [5. 组件设计](#5-组件设计)
- [6. 状态管理](#6-状态管理)
- [7. API 通信层](#7-api-通信层)
- [8. 路由设计](#8-路由设计)
- [9. 样式系统](#9-样式系统)
- [10. 响应式设计](#10-响应式设计)
- [11. 主题系统](#11-主题系统)
- [12. 图表与可视化](#12-图表与可视化)
- [13. D3.js 谱系图谱](#13-d3js-谱系图谱)
- [14. 流式响应处理](#14-流式响应处理)
- [15. 实时通信](#15-实时通信)
- [16. 表单与验证](#16-表单与验证)
- [17. 错误处理](#17-错误处理)
- [18. 加载状态](#18-加载状态)
- [19. 动画与过渡](#19-动画与过渡)
- [20. 可访问性](#20-可访问性)
- [21. 国际化](#21-国际化)
- [22. 性能优化](#22-性能优化)
- [23. 构建与部署](#23-构建与部署)
- [24. 测试策略](#24-测试策略)
- [25. 代码规范](#25-代码规范)
- [26. 安全考虑](#26-安全考虑)
- [27. 浏览器兼容性](#27-浏览器兼容性)
- [28. PWA 支持](#28-pwa-支持)
- [29. 监控与埋点](#29-监控与埋点)
- [30. 附录](#30-附录)

---

## 1. 前端概览

### 1.1 设计目标

ThesisMiner v8.0 前端围绕以下目标设计：

1. **学术专业**：界面风格严谨、专业，符合学术工具气质
2. **交互流畅**：响应迅速，操作流畅，无卡顿
3. **信息密度**：合理的信息密度，既不拥挤也不空旷
4. **多任务支持**：多对话并存、多 Agent 切换、多视图并行
5. **可视化丰富**：D3.js 谱系图谱、五阶段进度条、引用卡片
6. **响应式**：适配桌面、平板、移动端
7. **可访问性**：符合 WCAG 2.1 AA 标准
8. **性能优秀**：首屏加载 < 2s，交互响应 < 100ms

### 1.2 核心页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 首页 | index.html | 项目介绍、快速入口 |
| 会话管理 | sessions.html | 多对话管理、Agent 交互 |
| 论题生成 | generate.html | 五阶段流程、多粒度生成 |
| 谱系图谱 | lineage.html | D3.js 力导向图谱 |
| 预算管理 | budgets.html | 用量统计、缓存命中率 |
| 设置 | settings.html | 模型配置、参数调整 |

---

## 2. 技术栈选型

### 2.1 核心技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| HTML5 | - | 页面结构 |
| CSS3 | - | 样式 |
| JavaScript | ES2022+ | 交互逻辑 |
| D3.js | v7 | 数据可视化 |
| Font Awesome | 6.x | 图标 |
| Google Fonts | - | 字体 |

### 2.2 为什么不用框架？

ThesisMiner v8.0 前端选择原生 JavaScript 而非 React/Vue，原因：

1. **轻量**：无需构建工具，首屏加载快
2. **可控**：完全控制渲染逻辑，便于优化
3. **简单**：项目规模适中，原生 JS 足够
4. **兼容**：无框架版本升级负担
5. **学术工具**：交互复杂度可控，不需要框架的响应式系统

### 2.3 模块化策略

使用 ES Modules 实现模块化：

```javascript
// frontend/scripts/api.js
export class ApiClient {
    async getConversations(sessionId) { ... }
    async createConversation(sessionId, data) { ... }
}

// frontend/scripts/pages/sessions.js
import { ApiClient } from '../api.js';
const api = new ApiClient();
```

---

## 3. 目录结构

```
frontend/
├── index.html              # 首页
├── sessions.html           # 会话管理页
├── generate.html           # 论题生成页
├── lineage.html            # 谱系图谱页
├── budgets.html            # 预算管理页
├── settings.html           # 设置页
├── styles/
│   ├── main.css            # 主样式
│   ├── themes.css          # 主题
│   └── vendor/
│       └── d3.min.css      # D3.js 样式
├── scripts/
│   ├── api.js              # API 通信层
│   ├── utils.js            # 工具函数
│   ├── components/         # 通用组件
│   │   ├── modal.js
│   │   ├── toast.js
│   │   ├── loading.js
│   │   └── citation-card.js
│   └── pages/              # 页面脚本
│       ├── sessions.js
│       ├── generate.js
│       ├── lineage.js
│       ├── budgets.js
│       └── settings.js
├── assets/
│   ├── images/
│   ├── fonts/
│   └── icons/
└── vendor/
    └── d3.min.js           # D3.js 本地副本
```

---

## 4. 页面体系

### 4.1 页面布局

所有页面遵循统一布局：

```
┌─────────────────────────────────────────┐
│  顶部导航栏（Logo + 导航 + 用户）        │
├─────────────────────────────────────────┤
│                                         │
│              主内容区                   │
│                                         │
├─────────────────────────────────────────┤
│  底部状态栏（版本 + 状态 + 链接）        │
└─────────────────────────────────────────┘
```

### 4.2 会话管理页布局

```
┌─────────────────────────────────────────┐
│  顶部导航                               │
├──────────┬──────────────────────────────┤
│          │  对话Tab栏                   │
│  会话    ├──────────────────────────────┤
│  列表    │                              │
│          │  消息列表                    │
│  (左侧)  │  (中间)                      │
│          │                              │
│          ├──────────────────────────────┤
│          │  Agent选择 + 输入框          │
│          │  (底部)                      │
└──────────┴──────────────────────────────┘
```

---

## 5. 组件设计

### 5.1 组件分类

1. **页面组件**：sessions.js、generate.js、lineage.js
2. **通用组件**：modal、toast、loading、citation-card
3. **业务组件**：conversation-tab、message-item、stage-progress

### 5.2 组件规范

```javascript
// 通用组件示例：Toast 通知
class Toast {
    constructor(options = {}) {
        this.duration = options.duration || 3000;
        this.type = options.type || 'info';
        this.container = this._getContainer();
    }
    
    show(message) {
        const toast = this._create(message);
        this.container.appendChild(toast);
        
        requestAnimationFrame(() => toast.classList.add('show'));
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, this.duration);
    }
    
    _create(message) {
        const div = document.createElement('div');
        div.className = `toast toast-${this.type}`;
        div.textContent = message;
        return div;
    }
    
    _getContainer() {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }
}
```

---

## 6. 状态管理

### 6.1 状态分类

1. **全局状态**：当前会话、用户配置、主题
2. **页面状态**：当前对话、当前阶段、加载状态
3. **组件状态**：表单值、展开/折叠、选中项

### 6.2 简单状态管理

```javascript
// frontend/scripts/state.js
class StateManager {
    constructor() {
        this._state = {};
        this._listeners = new Map();
    }
    
    get(key) {
        return this._state[key];
    }
    
    set(key, value) {
        const oldValue = this._state[key];
        this._state[key] = value;
        this._notify(key, value, oldValue);
    }
    
    subscribe(key, callback) {
        if (!this._listeners.has(key)) {
            this._listeners.set(key, new Set());
        }
        this._listeners.get(key).add(callback);
        return () => this._listeners.get(key).delete(callback);
    }
    
    _notify(key, newValue, oldValue) {
        const listeners = this._listeners.get(key);
        if (listeners) {
            listeners.forEach(cb => cb(newValue, oldValue));
        }
    }
}

export const state = new StateManager();
```

---

## 7. API 通信层

### 7.1 API 客户端

```javascript
// frontend/scripts/api.js
class ApiClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }
    
    async request(method, path, options = {}) {
        const url = `${this.baseUrl}${path}`;
        const response = await fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: options.body ? JSON.stringify(options.body) : undefined,
            signal: options.signal
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new ApiError(response.status, error.detail || response.statusText);
        }
        
        return response.json();
    }
    
    // 会话相关
    async getSessions() {
        return this.request('GET', '/api/sessions');
    }
    
    async createSession(data) {
        return this.request('POST', '/api/sessions', { body: data });
    }
    
    // 对话相关
    async getConversations(sessionId) {
        return this.request('GET', `/api/sessions/${sessionId}/conversations`);
    }
    
    async createConversation(sessionId, data) {
        return this.request('POST', `/api/sessions/${sessionId}/conversations`, { body: data });
    }
    
    // 流式消息
    async streamMessage(conversationId, data, onChunk) {
        const response = await fetch(`${this.baseUrl}/api/conversations/${conversationId}/messages/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n').filter(l => l.startsWith('data: '));
            
            for (const line of lines) {
                const data = JSON.parse(line.slice(6));
                onChunk(data);
            }
        }
    }
}
```

---

## 8. 路由设计

### 8.1 多页面路由

ThesisMiner 采用多页面应用（MPA）架构，每个页面独立 HTML 文件：

```html
<!-- 导航栏 -->
<nav class="navbar">
    <a href="index.html" class="nav-link">首页</a>
    <a href="sessions.html" class="nav-link">会话</a>
    <a href="generate.html" class="nav-link">生成</a>
    <a href="lineage.html" class="nav-link">谱系</a>
    <a href="budgets.html" class="nav-link">预算</a>
</nav>
```

### 8.2 页面内路由

单页面内使用 Hash 路由管理视图切换：

```javascript
class HashRouter {
    constructor(routes) {
        this.routes = routes;
        window.addEventListener('hashchange', () => this.handle());
        this.handle();
    }
    
    handle() {
        const hash = window.location.hash.slice(1) || '/';
        const route = this.routes[hash] || this.routes['/'];
        route();
    }
    
    navigate(path) {
        window.location.hash = path;
    }
}
```

---

## 9. 样式系统

### 9.1 CSS 变量

```css
:root {
    /* 颜色 */
    --color-primary: #2563eb;
    --color-primary-dark: #1d4ed8;
    --color-secondary: #64748b;
    --color-success: #16a34a;
    --color-warning: #d97706;
    --color-error: #dc2626;
    
    /* 背景 */
    --bg-primary: #ffffff;
    --bg-secondary: #f8fafc;
    --bg-tertiary: #f1f5f9;
    
    /* 文字 */
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-tertiary: #94a3b8;
    
    /* 边框 */
    --border-color: #e2e8f0;
    --border-radius: 8px;
    
    /* 阴影 */
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
    --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);
    
    /* 间距 */
    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 32px;
    
    /* 字体 */
    --font-sans: 'Inter', 'Noto Sans SC', sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
    --font-size-sm: 14px;
    --font-size-base: 16px;
    --font-size-lg: 18px;
    --font-size-xl: 20px;
}
```

### 9.2 暗色主题

```css
[data-theme="dark"] {
    --color-primary: #3b82f6;
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --bg-tertiary: #334155;
    --text-primary: #f1f5f9;
    --text-secondary: #cbd5e1;
    --text-tertiary: #64748b;
    --border-color: #334155;
}
```

---

## 10. 响应式设计

### 10.1 断点

```css
/* 移动端 */
@media (max-width: 640px) { ... }

/* 平板 */
@media (min-width: 641px) and (max-width: 1024px) { ... }

/* 桌面 */
@media (min-width: 1025px) { ... }

/* 大屏 */
@media (min-width: 1440px) { ... }
```

### 10.2 响应式布局

```css
.session-layout {
    display: grid;
    grid-template-columns: 240px 1fr;
    height: calc(100vh - 60px);
}

@media (max-width: 768px) {
    .session-layout {
        grid-template-columns: 1fr;
        grid-template-rows: auto 1fr;
    }
    
    .session-sidebar {
        height: 200px;
        overflow-y: auto;
    }
}
```

---

## 11. 主题系统

### 11.1 主题切换

```javascript
class ThemeManager {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'light';
        this.apply(this.theme);
    }
    
    apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        this.theme = theme;
    }
    
    toggle() {
        this.apply(this.theme === 'light' ? 'dark' : 'light');
    }
}
```

---

## 12. 图表与可视化

### 12.1 图表类型

1. **力导向图谱**：谱系关系图（D3.js force）
2. **进度条**：五阶段流程进度
3. **雷达图**：新颖性评分
4. **柱状图**：用量统计
5. **饼图**：缓存命中率

### 12.2 图表组件

```javascript
class ChartComponent {
    constructor(container, options) {
        this.container = container;
        this.options = options;
        this.svg = null;
    }
    
    render(data) {
        // 子类实现
    }
    
    resize() {
        if (this.svg) {
            const rect = this.container.getBoundingClientRect();
            this.svg.attr('width', rect.width).attr('height', rect.height);
            this.render(this._lastData);
        }
    }
    
    destroy() {
        if (this.svg) {
            this.svg.remove();
            this.svg = null;
        }
    }
}
```

---

## 13. D3.js 谱系图谱

### 13.1 力导向布局

```javascript
class LineageGraph {
    constructor(container) {
        this.container = container;
        this.width = container.clientWidth;
        this.height = container.clientHeight;
        this.svg = d3.select(container).append('svg')
            .attr('width', this.width)
            .attr('height', this.height);
        
        this.g = this.svg.append('g');
        
        // 缩放
        this.zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });
        this.svg.call(this.zoom);
        
        // 力导向
        this.simulation = d3.forceSimulation()
            .force('link', d3.forceLink().id(d => d.id).distance(100))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide().radius(30));
    }
    
    render(nodes, links) {
        // 渲染边
        const link = this.g.selectAll('.link')
            .data(links)
            .enter().append('line')
            .attr('class', 'link')
            .attr('stroke', '#999')
            .attr('stroke-opacity', 0.6);
        
        // 渲染节点
        const node = this.g.selectAll('.node')
            .data(nodes)
            .enter().append('g')
            .attr('class', 'node')
            .call(this._drag());
        
        node.append('circle')
            .attr('r', d => d.size || 10)
            .attr('fill', d => this._color(d.type));
        
        node.append('text')
            .text(d => d.label)
            .attr('dx', 12)
            .attr('dy', '.35em');
        
        // 力导向更新
        this.simulation
            .nodes(nodes)
            .on('tick', () => {
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                node.attr('transform', d => `translate(${d.x},${d.y})`);
            });
        
        this.simulation.force('link').links(links);
    }
    
    _drag() {
        const drag = d3.drag()
            .on('start', (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on('drag', (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on('end', (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            });
        return drag;
    }
    
    _color(type) {
        const colors = {
            thesis: '#2563eb',
            method: '#16a34a',
            paper: '#d97706',
            advisor: '#dc2626'
        };
        return colors[type] || '#64748b';
    }
}
```

---

## 14. 流式响应处理

### 14.1 SSE 流式接收

```javascript
class StreamHandler {
    constructor(onMessage, onComplete, onError) {
        this.onMessage = onMessage;
        this.onComplete = onComplete;
        this.onError = onError;
        this.controller = null;
    }
    
    async start(url, body) {
        this.controller = new AbortController();
        
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal: this.controller.signal
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        this.onMessage(data);
                    }
                }
            }
            
            this.onComplete();
        } catch (error) {
            if (error.name !== 'AbortError') {
                this.onError(error);
            }
        }
    }
    
    abort() {
        if (this.controller) {
            this.controller.abort();
        }
    }
}
```

---

## 15. 实时通信

### 15.1 WebSocket

```javascript
class WebSocketClient {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }
    
    connect() {
        this.ws = new WebSocket(this.url);
        
        this.ws.onopen = () => {
            this.reconnectAttempts = 0;
            console.log('WebSocket connected');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                setTimeout(() => this.connect(), 1000 * Math.pow(2, this.reconnectAttempts));
                this.reconnectAttempts++;
            }
        };
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }
    
    handleMessage(data) {
        // 子类实现
    }
}
```

---

## 16. 表单与验证

### 16.1 表单验证

```javascript
class FormValidator {
    constructor(form, rules) {
        this.form = form;
        this.rules = rules;
        this.errors = {};
    }
    
    validate() {
        this.errors = {};
        
        for (const [field, rule] of Object.entries(this.rules)) {
            const value = this.form[field]?.value;
            const error = this._validateField(value, rule);
            if (error) {
                this.errors[field] = error;
            }
        }
        
        return Object.keys(this.errors).length === 0;
    }
    
    _validateField(value, rule) {
        if (rule.required && !value) {
            return rule.message || '此字段必填';
        }
        if (rule.minLength && value.length < rule.minLength) {
            return `最少 ${rule.minLength} 个字符`;
        }
        if (rule.maxLength && value.length > rule.maxLength) {
            return `最多 ${rule.maxLength} 个字符`;
        }
        if (rule.pattern && !rule.pattern.test(value)) {
            return rule.message || '格式不正确';
        }
        return null;
    }
}
```

---

## 17. 错误处理

### 17.1 全局错误处理

```javascript
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    toast.error('操作失败，请稍后重试');
});

window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    toast.error('系统错误，请刷新页面');
});
```

### 17.2 API 错误处理

```javascript
class ApiError extends Error {
    constructor(status, message) {
        super(message);
        this.status = status;
    }
}

async function handleApiCall(fn) {
    try {
        return await fn();
    } catch (error) {
        if (error instanceof ApiError) {
            if (error.status === 401) {
                toast.error('请先登录');
                window.location.href = '/login';
            } else if (error.status === 429) {
                toast.error('请求过于频繁，请稍后重试');
            } else {
                toast.error(error.message);
            }
        } else {
            toast.error('网络错误，请检查连接');
        }
        throw error;
    }
}
```

---

## 18. 加载状态

### 18.1 加载指示器

```javascript
class LoadingIndicator {
    show(container) {
        const loader = document.createElement('div');
        loader.className = 'loading-spinner';
        loader.innerHTML = '<div class="spinner"></div>';
        container.appendChild(loader);
        return loader;
    }
    
    hide(loader) {
        if (loader && loader.parentNode) {
            loader.parentNode.removeChild(loader);
        }
    }
}
```

---

## 19. 动画与过渡

### 19.1 CSS 过渡

```css
.fade-enter {
    opacity: 0;
    transform: translateY(10px);
}

.fade-enter-active {
    opacity: 1;
    transform: translateY(0);
    transition: opacity 300ms, transform 300ms;
}

.fade-exit {
    opacity: 1;
}

.fade-exit-active {
    opacity: 0;
    transition: opacity 300ms;
}
```

---

## 20. 可访问性

### 20.1 ARIA 标签

```html
<button 
    aria-label="新建对话"
    aria-describedby="new-conversation-help"
    class="btn btn-primary">
    + 新建
</button>
<span id="new-conversation-help" class="sr-only">
    点击创建新的对话
</span>
```

### 20.2 键盘导航

```javascript
document.addEventListener('keydown', (e) => {
    // Ctrl+K 快速搜索
    if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        openSearch();
    }
    
    // Esc 关闭模态框
    if (e.key === 'Escape') {
        closeAllModals();
    }
});
```

---

## 21. 国际化

### 21.1 i18n 基础

```javascript
const i18n = {
    'zh-CN': {
        'session.new': '新建会话',
        'session.delete': '删除会话',
        'conversation.new': '新建对话',
        'message.send': '发送'
    },
    'en-US': {
        'session.new': 'New Session',
        'session.delete': 'Delete Session',
        'conversation.new': 'New Conversation',
        'message.send': 'Send'
    }
};

class I18n {
    constructor(locale = 'zh-CN') {
        this.locale = locale;
        this.messages = i18n[locale] || i18n['zh-CN'];
    }
    
    t(key) {
        return this.messages[key] || key;
    }
}
```

---

## 22. 性能优化

### 22.1 代码分割

```javascript
// 按需加载页面脚本
async function loadPage(pageName) {
    const module = await import(`./pages/${pageName}.js`);
    return module.default;
}
```

### 22.2 虚拟滚动

```javascript
class VirtualScroll {
    constructor(container, items, itemHeight) {
        this.container = container;
        this.items = items;
        this.itemHeight = itemHeight;
        this.visibleCount = Math.ceil(container.clientHeight / itemHeight);
        this.scrollTop = 0;
        
        container.addEventListener('scroll', () => {
            this.scrollTop = container.scrollTop;
            this.render();
        });
        
        this.render();
    }
    
    render() {
        const startIndex = Math.floor(this.scrollTop / this.itemHeight);
        const endIndex = Math.min(startIndex + this.visibleCount + 5, this.items.length);
        
        const visibleItems = this.items.slice(startIndex, endIndex);
        // 渲染可见项...
    }
}
```

### 22.3 防抖与节流

```javascript
function debounce(fn, delay) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

function throttle(fn, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            fn.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
```

---

## 23. 构建与部署

### 23.1 开发环境

```bash
# 启动开发服务器
python main.py

# 访问前端
# http://localhost:8000/frontend/index.html
```

### 23.2 生产环境

前端为静态文件，由 FastAPI 直接提供：

```python
# main.py
from fastapi.staticfiles import StaticFiles

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
```

---

## 24. 测试策略

### 24.1 前端测试

1. **单元测试**：工具函数、组件逻辑
2. **E2E测试**：Playwright 页面测试
3. **视觉回归**：截图对比
4. **性能测试**：Lighthouse 审计

---

## 25. 代码规范

### 25.1 JavaScript 规范

- 使用 ES2022+ 语法
- 2 空格缩进
- 单引号字符串
- 分号结尾
- 驼峰命名

---

## 26. 安全考虑

### 26.1 XSS 防护

```javascript
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 使用 textContent 而非 innerHTML
element.textContent = userInput;
```

---

## 27. 浏览器兼容性

### 27.1 支持的浏览器

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

---

## 28. PWA 支持

### 28.1 Service Worker

```javascript
// sw.js
const CACHE_NAME = 'thesisminer-v8';
const ASSETS = [
    '/frontend/index.html',
    '/frontend/styles/main.css',
    '/frontend/scripts/api.js'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
    );
});
```

---

## 29. 监控与埋点

### 29.1 前端监控

```javascript
class Monitor {
    track(event, properties = {}) {
        // 上报到后端
        navigator.sendBeacon('/api/track', JSON.stringify({
            event,
            properties,
            timestamp: Date.now(),
            url: window.location.href
        }));
    }
    
    trackError(error) {
        this.track('error', {
            message: error.message,
            stack: error.stack
        });
    }
    
    trackPerformance() {
        const timing = performance.getEntriesByType('navigation')[0];
        this.track('performance', {
            domContentLoaded: timing.domContentLoadedEventEnd,
            loadComplete: timing.loadEventEnd,
            ttfb: timing.responseStart - timing.requestStart
        });
    }
}
```

---

## 30. 附录

### 30.1 调试技巧

```javascript
// 启用调试模式
localStorage.setItem('debug', 'true');

// 调试日志
if (localStorage.getItem('debug') === 'true') {
    console.log('[Debug]', ...args);
}
```

### 30.2 常用工具函数

```javascript
// frontend/scripts/utils.js
export const utils = {
    formatDate(date) {
        return new Intl.DateTimeFormat('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        }).format(new Date(date));
    },
    
    truncate(text, length) {
        return text.length > length ? text.slice(0, length) + '...' : text;
    },
    
    copyToClipboard(text) {
        navigator.clipboard.writeText(text);
    }
};
```

---

## 结语

ThesisMiner v8.0 前端采用原生 JavaScript + D3.js 的轻量架构，在保证性能与可控性的同时，实现了丰富的交互体验。通过模块化、组件化、状态管理等手段，确保代码的可维护性与可扩展性。
