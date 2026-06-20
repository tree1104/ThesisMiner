# ThesisMiner v8.0 安全设计文档

> **版本**：v8.0
> **日期**：2026-06-19
> **文档定位**：完整的安全设计文档，覆盖认证、授权、加密、输入校验、注入防护、XSS/CSRF 防护、速率限制与审计
> **关联模块**：全栈（前端 / API 路由 / 数据库 / AI 代理层）

---

## 目录

1. [安全设计原则](#1-安全设计原则)
2. [威胁模型](#2-威胁模型)
3. [认证与授权](#3-认证与授权)
4. [API Key 管理](#4-api-key-管理)
5. [数据加密](#5-数据加密)
6. [输入校验](#6-输入校验)
7. [SQL 注入防护](#7-sql-注入防护)
8. [XSS 防护](#8-xss-防护)
9. [CSRF 防护](#9-csrf-防护)
10. [速率限制](#10-速率限制)
11. [审计日志](#11-审计日志)
12. [安全配置清单](#12-安全配置清单)
13. [应急响应](#13-应急响应)
14. [附录](#14-附录)

---

## 1. 安全设计原则

### 1.1 核心原则

ThesisMiner v8.0 遵循以下安全设计原则：

1. **最小权限原则（Least Privilege）**
   - 服务以非 root 用户运行
   - API Key 仅授予必要权限
   - 数据库文件权限 600
   - 配置文件权限 600

2. **纵深防御原则（Defense in Depth）**
   - 输入校验（Pydantic 模型）
   - 参数化查询（SQL 注入防护）
   - 输出编码（XSS 防护）
   - 网络隔离（防火墙 + 反向代理）

3. **失败安全原则（Fail Safe）**
   - 异常发生时拒绝服务而非降级到不安全状态
   - 默认拒绝（Default Deny）
   - 错误响应不泄露敏感信息

4. **可审计原则（Auditable）**
   - 所有敏感操作记录审计日志
   - 日志包含操作时间、操作者、操作内容
   - 日志不可篡改（追加模式）

5. **密钥保护原则（Key Protection）**
   - API Key 在配置文件中存储，权限 600
   - 前端展示时脱敏（仅显示是否已配置）
   - 日志中不记录 Key 明文
   - 传输仅通过 HTTPS

### 1.2 安全边界

```text
┌─────────────────────────────────────────────────────────────┐
│                       安全边界图                              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 互联网（不可信区域）                                  │    │
│  │                                                     │    │
│  │  ┌─────────┐                                       │    │
│  │  │ 攻击者  │                                       │    │
│  │  └────┬────┘                                       │    │
│  └───────┼────────────────────────────────────────────┘    │
│          │                                                  │
│          ▼                                                  │
│  ┌───────────────────────────────────────────────────┐     │
│  │ 边界1: 防火墙（仅开放 80/443）                    │     │
│  └───────┬───────────────────────────────────────────┘     │
│          │                                                  │
│          ▼                                                  │
│  ┌───────────────────────────────────────────────────┐     │
│  │ 边界2: Nginx 反向代理                             │     │
│  │ - HTTPS 终止                                      │     │
│  │ - 速率限制                                        │     │
│  │ - 请求体大小限制                                  │     │
│  │ - Origin 校验                                     │     │
│  └───────┬───────────────────────────────────────────┘     │
│          │                                                  │
│          ▼                                                  │
│  ┌───────────────────────────────────────────────────┐     │
│  │ 边界3: FastAPI 应用                               │     │
│  │ - Pydantic 输入校验                               │     │
│  │ - 参数化查询                                      │     │
│  │ - 异常处理（不泄露堆栈）                          │     │
│  └───────┬───────────────────────────────────────────┘     │
│          │                                                  │
│          ▼                                                  │
│  ┌───────────────────────────────────────────────────┐     │
│  │ 边界4: 数据库（文件权限 600）                     │     │
│  │ - WAL 模式                                        │     │
│  │ - 外键约束                                        │     │
│  │ - CHECK 约束                                      │     │
│  └───────┬───────────────────────────────────────────┘     │
│          │                                                  │
│          ▼                                                  │
│  ┌───────────────────────────────────────────────────┐     │
│  │ 边界5: AI 服务商（API Key 认证）                  │     │
│  │ - HTTPS 传输                                      │     │
│  │ - Key 不落日志                                    │     │
│  └───────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 威胁模型

### 2.1 STRIDE 威胁分析

| 威胁类型 | 威胁描述 | 风险等级 | 缓解措施 |
|----------|----------|----------|----------|
| **Spoofing（伪装）** | 攻击者伪装成合法用户访问系统 | 中 | 反向代理认证、API Key |
| **Tampering（篡改）** | 攻击者篡改传输中的数据 | 高 | HTTPS、参数校验 |
| **Repudiation（抵赖）** | 用户否认操作行为 | 中 | 审计日志 |
| **Information Disclosure（信息泄露）** | 敏感信息（API Key、用户数据）泄露 | 高 | 文件权限、脱敏、HTTPS |
| **Denial of Service（拒绝服务）** | 攻击者耗尽系统资源 | 中 | 速率限制、超时控制 |
| **Elevation of Privilege（权限提升）** | 攻击者获取未授权权限 | 低 | 最小权限、非 root 运行 |

### 2.2 攻击面分析

| 攻击面 | 暴露点 | 风险 | 缓解 |
|--------|--------|------|------|
| HTTP API | 60+ 端点 | 中 | 速率限制、输入校验 |
| 前端 SPA | 静态资源 | 低 | CSP、输出编码 |
| 数据库文件 | 本地文件 | 低 | 文件权限 600 |
| 配置文件 | API Key 存储 | 高 | 文件权限 600、脱敏 |
| AI 服务调用 | 公网请求 | 中 | HTTPS、Key 保护 |
| 文献检索 API | 公网请求 | 低 | 超时控制、降级 |

### 2.3 攻击场景

#### 场景1：API Key 泄露

```text
攻击路径:
1. 攻击者获取服务器文件系统访问权
2. 读取 data/config.json 获取 AI API Key
3. 使用 Key 调用 AI 服务，产生费用

缓解措施:
- 文件权限 600（仅 owner 可读写）
- 服务以非 root 用户运行
- 配置文件不纳入版本控制（.gitignore）
- 定期轮换 Key
- 监控异常调用模式
```

#### 场景2：SQL 注入

```text
攻击路径:
1. 攻击者在输入框注入 SQL 语句
2. 应用拼接 SQL 并执行
3. 攻击者获取或篡改数据

缓解措施:
- 所有 SQL 使用参数化查询（? 占位符）
- Pydantic 模型校验输入类型
- 业务层不直接拼接 SQL
```

#### 场景3：XSS 攻击

```text
攻击路径:
1. 攻击者在论题标题中注入恶意脚本
2. 其他用户查看论题时脚本执行
3. 攻击者窃取用户会话

缓解措施:
- 前端使用 textContent 而非 innerHTML
- Markdown 渲染禁用原生 HTML
- CSP 策略限制脚本来源
```

---

## 3. 认证与授权

### 3.1 当前认证机制

ThesisMiner v8.0 当前为单用户本地部署模式，暂不提供内置认证。生产环境部署建议通过反向代理实现认证。

### 3.2 反向代理认证方案

#### 3.2.1 Nginx Basic Auth

```nginx
server {
    listen 443 ssl;
    server_name thesisminer.example.com;

    ssl_certificate /etc/ssl/certs/thesisminer.pem;
    ssl_certificate_key /etc/ssl/private/thesisminer.key;

    # Basic Auth
    auth_basic "Restricted Access";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

生成密码文件：

```bash
# 安装 htpasswd 工具
apt-get install apache2-utils

# 创建用户
htpasswd -c /etc/nginx/.htpasswd admin

# 添加用户
htpasswd /etc/nginx/.htpasswd user2
```

#### 3.2.2 OAuth2 代理

```nginx
server {
    listen 443 ssl;
    server_name thesisminer.example.com;

    location / {
        proxy_pass http://127.0.0.1:4180;  # oauth2-proxy
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /oauth2/ {
        proxy_pass http://127.0.0.1:4180;
    }
}
```

#### 3.2.3 网络隔离

```bash
# 仅允许内网访问
server {
    listen 443 ssl;
    server_name thesisminer.internal;

    allow 192.168.1.0/24;    # 内网网段
    allow 10.0.0.0/8;        # VPN 网段
    deny all;

    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

### 3.3 授权策略

当前版本无细粒度授权，所有操作对认证用户开放。未来 v9.0 规划：

| 角色 | 权限 |
|------|------|
| admin | 所有操作 + 用户管理 + 系统配置 |
| researcher | 论题生成 + 会话管理 + 谱系管理 |
| viewer | 只读访问 |

### 3.4 会话管理

```text
┌─────────────────────────────────────────────────────────────┐
│                    会话安全策略                              │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 会话创建    │  │ 会话维持    │  │ 会话销毁    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  - 服务端生成  - 超时自动过期  - 用户主动登出               │
│    UUID       - 滑动窗口续期  - 服务重启清理                │
│  - 不存 Cookie - IP 绑定       - 数据库清理                 │
│                                                             │
│  当前版本:                                                  │
│  - 会话 ID 由服务端生成（UUID）                             │
│  - 会话状态存储在 SQLite                                    │
│  - 无 Cookie（API 模式）                                    │
│  - 超时由业务层控制（5 分钟无操作）                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. API Key 管理

### 4.1 Key 存储策略

```text
┌─────────────────────────────────────────────────────────────┐
│                    API Key 存储策略                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 存储位置: data/config.json                          │    │
│  │ 文件权限: 600 (owner read/write only)               │    │
│  │ 格式: JSON                                          │    │
│  │ {                                                   │    │
│  │   "ai_api_key": "sk-xxxxxxxxxxxxxxxx",              │    │
│  │   "ai_base_url": "https://api.deepseek.com/v1"      │    │
│  │ }                                                   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 备用存储: .env 文件                                  │    │
│  │ 文件权限: 600                                       │    │
│  │ 格式: KEY=VALUE                                     │    │
│  │ AI_API_KEY=sk-xxxxxxxxxxxxxxxx                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  优先级: data/config.json > .env > 默认值                   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Key 保护措施

| 措施 | 实现方式 |
|------|----------|
| 文件权限 | `chmod 600 data/config.json` |
| 版本控制排除 | `.gitignore` 包含 `data/config.json` |
| 前端脱敏 | `GET /api/config` 不返回 Key 明文，仅返回 `api_key_configured: bool` |
| 日志脱敏 | 日志中 Key 替换为 `sk-***xxxx` |
| 传输加密 | 仅通过 HTTPS 传输 |
| 环境隔离 | 开发/生产环境使用不同 Key |

### 4.3 Key 轮换流程

```text
1. 在 AI 服务商后台生成新 Key
2. 通过 POST /api/config 更新 Key
   {
     "ai_api_key": "sk-new-key-xxxxx"
   }
3. 验证新 Key 可用
4. 在服务商后台吊销旧 Key
5. 检查日志确认无异常调用
```

### 4.4 Key 泄露应急响应

```text
发现 Key 泄露
   │
   ▼
┌─────────────────────────────┐
│ 1. 立即在服务商后台吊销 Key │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 2. 生成新 Key 并更新配置    │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 3. 重启服务                 │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 4. 审计日志确认无异常调用   │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 5. 排查泄露原因             │
│ - 检查文件权限              │
│ - 检查 Git 历史             │
│ - 检查日志文件              │
│ - 检查备份文件              │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 6. 修复漏洞，防止再次泄露   │
└─────────────────────────────┘
```

---

## 5. 数据加密

### 5.1 传输加密

```text
┌─────────────────────────────────────────────────────────────┐
│                    传输加密策略                              │
│                                                             │
│  浏览器                                                     │
│    │                                                        │
│    │ HTTPS (TLS 1.3)                                        │
│    ▼                                                        │
│  Nginx (HTTPS 终止)                                         │
│    │                                                        │
│    │ HTTP (内网，127.0.0.1)                                 │
│    ▼                                                        │
│  FastAPI (Uvicorn)                                          │
│    │                                                        │
│    │ HTTPS (TLS 1.2+)                                       │
│    ▼                                                        │
│  AI 服务商 API                                              │
│                                                             │
│  加密段:                                                    │
│  - 浏览器 ↔ Nginx: TLS 1.3                                  │
│  - FastAPI ↔ AI 服务商: TLS 1.2+                            │
│                                                             │
│  未加密段（内网，可信）:                                     │
│  - Nginx ↔ FastAPI: HTTP (127.0.0.1)                        │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Nginx SSL 配置

```nginx
server {
    listen 443 ssl http2;
    server_name thesisminer.example.com;

    # SSL 证书
    ssl_certificate /etc/ssl/certs/thesisminer.pem;
    ssl_certificate_key /etc/ssl/private/thesisminer.key;

    # SSL 协议（仅允许 TLS 1.2+）
    ssl_protocols TLSv1.2 TLSv1.3;

    # 加密套件
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # HSTS（强制 HTTPS）
    add_header Strict-Transport-Security "max-age=63072000" always;

    # 会话缓存
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
}
```

### 5.3 静态数据加密

当前版本静态数据未加密（SQLite 文件明文存储）。未来规划：

| 数据类型 | 加密方案 | 优先级 |
|----------|----------|--------|
| API Key | AES-256 加密存储 | 高 |
| 用户隐私 | 字段级加密 | 中 |
| 数据库文件 | 全盘加密（LUKS） | 低 |

### 5.4 敏感字段处理

```python
# backend/config.py 敏感字段脱敏
def get_config_safe() -> dict:
    """获取配置（脱敏，用于前端展示）"""
    settings = get_settings()
    return {
        "ai_api_key_configured": bool(settings.ai_api_key),
        "ai_api_key_masked": mask_api_key(settings.ai_api_key),
        "ai_base_url": settings.ai_base_url,
        "ai_model": settings.ai_model,
        # ... 其他非敏感字段
    }


def mask_api_key(key: str) -> str:
    """API Key 脱敏"""
    if not key or len(key) < 8:
        return ""
    return key[:3] + "***" + key[-4:]


def mask_key_in_log(key: str) -> str:
    """日志中 Key 脱敏"""
    if not key:
        return "<empty>"
    if len(key) <= 8:
        return "***"
    return key[:3] + "***" + key[-4:]
```

---

## 6. 输入校验

### 6.1 Pydantic 模型校验

所有 API 请求体通过 Pydantic 模型校验，拒绝非法字段：

```python
# backend/models.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal


class SessionCreate(BaseModel):
    """创建会话请求模型"""
    title: str = Field(..., min_length=1, max_length=200, description="会话标题")
    degree: Literal["master", "doctor"] = Field(..., description="学位层次")
    discipline: Optional[str] = Field(None, max_length=100, description="学科方向")
    mentor_info: Optional[str] = Field(None, max_length=5000, description="导师信息")

    @validator("title")
    def validate_title(cls, v):
        """标题不能含特殊字符"""
        if any(char in v for char in ["<", ">", "&", '"', "'"]):
            raise ValueError("标题不能含特殊字符")
        return v


class ProposalGenerate(BaseModel):
    """生成论题请求模型"""
    degree: Literal["master", "doctor"]
    discipline: str = Field(..., min_length=1, max_length=100)
    mentor_info: Optional[str] = Field(None, max_length=5000)
    mode: Literal["quick", "deep"] = "quick"
    count: int = Field(3, ge=1, le=10, description="生成数量 1-10")
    session_id: Optional[str] = None


class MessageCreate(BaseModel):
    """发送消息请求模型"""
    content: str = Field(..., min_length=1, max_length=10000, description="消息内容")
    metadata: Optional[dict] = None
```

### 6.2 路径参数校验

```python
# backend/routes/proposals.py
from fastapi import HTTPException


@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str):
    # 校验 proposal_id 格式（UUID）
    if not is_valid_uuid(proposal_id):
        raise HTTPException(status_code=400, detail="无效的论题 ID 格式")

    proposal = fetch_one("SELECT * FROM proposals WHERE id = ?", (proposal_id,))
    if not proposal:
        raise HTTPException(status_code=404, detail="论题不存在")

    return proposal


def is_valid_uuid(uuid_str: str) -> bool:
    """校验 UUID 格式"""
    import re
    pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(pattern.match(uuid_str))
```

### 6.3 文件路径校验

```python
# backend/utils/path_validator.py
import os
from pathlib import Path


def validate_file_path(file_path: str, allowed_base: str) -> bool:
    """校验文件路径，防止路径穿越攻击

    Args:
        file_path: 待校验的文件路径
        allowed_base: 允许的基础目录

    Returns:
        路径安全返回 True，否则 False
    """
    base = Path(allowed_base).resolve()
    target = Path(file_path).resolve()

    # 检查目标路径是否在允许的基础目录内
    try:
        target.relative_to(base)
        return True
    except ValueError:
        return False


# 使用示例
def read_user_file(filename: str) -> str:
    base_dir = "data/uploads"
    if not validate_file_path(filename, base_dir):
        raise HTTPException(status_code=400, detail="非法文件路径")
    with open(os.path.join(base_dir, filename), "r") as f:
        return f.read()
```

### 6.4 长度限制

| 字段 | 最大长度 | 说明 |
|------|----------|------|
| 会话标题 | 200 字符 | 防止缓冲区溢出 |
| 学科方向 | 100 字符 | - |
| 导师信息 | 5000 字符 | - |
| 消息内容 | 10000 字符 | - |
| 论题标题 | 20 字符 | 硬约束 |
| 知识卡片内容 | 50000 字符 | - |
| 请求体总大小 | 1MB | Nginx 限制 |

---

## 7. SQL 注入防护

### 7.1 参数化查询

所有 SQL 查询使用 `?` 占位符，禁止字符串拼接：

```python
# 正确：参数化查询
def get_session(session_id: str):
    return fetch_one(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,)
    )

# 错误：字符串拼接（SQL 注入风险）
def get_session_insecure(session_id: str):
    return fetch_one(
        f"SELECT * FROM sessions WHERE id = '{session_id}'"
    )  # 危险！
```

### 7.2 LIKE 查询防护

```python
def search_lineage(keyword: str):
    """搜索谱系节点（LIKE 查询防护）"""
    # 转义 LIKE 特殊字符
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return fetch_all(
        "SELECT * FROM lineage_nodes WHERE title LIKE ? ESCAPE '\\'",
        (f"%{escaped}%",)
    )
```

### 7.3 批量操作防护

```python
def batch_delete_nodes(node_ids: list[str]):
    """批量删除节点（防护 IN 子句注入）"""
    if not node_ids:
        return 0

    # 校验每个 ID 格式
    for nid in node_ids:
        if not is_valid_uuid(nid):
            raise ValueError(f"无效的节点 ID: {nid}")

    # 使用参数化查询
    placeholders = ",".join("?" * len(node_ids))
    return execute_query(
        f"DELETE FROM lineage_nodes WHERE id IN ({placeholders})",
        tuple(node_ids)
    )
```

### 7.4 ORM 抽象

通过 `database.py` 的 CRUD 辅助函数统一执行 SQL，业务层不直接拼接：

```python
# backend/database.py
def execute_insert(query: str, params: tuple) -> str:
    """执行 INSERT，强制参数化"""
    if "%" in query and "LIKE" not in query.upper():
        raise ValueError("INSERT 语句不应包含 % 格式化")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    return cursor.lastrowid
```

---

## 8. XSS 防护

### 8.1 输出编码

前端展示用户输入时使用 `textContent` 而非 `innerHTML`：

```javascript
// frontend/scripts/app.js
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 正确：使用 textContent
element.textContent = userInput;

// 正确：使用 escapeHtml
element.innerHTML = `<span>${escapeHtml(userInput)}</span>`;

// 错误：直接拼接（XSS 风险）
element.innerHTML = `<span>${userInput}</span>`;
```

### 8.2 CSP 策略

```html
<!-- frontend/index.html -->
<meta http-equiv="Content-Security-Policy" content="
    default-src 'self';
    script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com;
    style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com;
    font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com;
    img-src 'self' data: https:;
    connect-src 'self' https://api.openai.com https://api.deepseek.com;
    frame-ancestors 'none';
    base-uri 'self';
    form-action 'self';
">
```

### 8.3 Markdown 渲染防护

开题报告 Markdown 渲染时禁用原生 HTML 标签：

```javascript
// frontend/scripts/pages/generate.js
function renderMarkdown(markdown) {
    // 使用 marked.js 渲染，禁用 HTML
    marked.setOptions({
        sanitize: true,  // 禁用原生 HTML
        silent: true,
    });
    return marked.parse(markdown);
}
```

### 8.4 Tailwind 安全

Tailwind CDN 自带 XSS 防护，不执行内联脚本。但需注意：

```javascript
// 错误：动态拼接 class（潜在风险）
element.className = `bg-${userColor}`;

// 正确：使用预定义的 class 映射
const colorMap = {
    red: 'bg-red-500',
    green: 'bg-green-500',
    blue: 'bg-blue-500',
};
element.className = colorMap[userColor] || 'bg-gray-500';
```

---

## 9. CSRF 防护

### 9.1 SameSite Cookie

```python
# backend/routes/auth.py（未来版本）
from fastapi import Response


@router.post("/login")
async def login(response: Response):
    response.set_cookie(
        key="session",
        value="session_token",
        httponly=True,      # 防止 JS 读取
        secure=True,        # 仅 HTTPS 传输
        samesite="strict",  # 防止 CSRF
        max_age=3600,
    )
```

### 9.2 Origin 校验

```python
# backend/middleware/csrf.py
from fastapi import Request, HTTPException


async def csrf_middleware(request: Request, call_next):
    """CSRF 防护中间件"""
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        origin = request.headers.get("origin", "")
        host = request.headers.get("host", "")

        # 校验 Origin 头
        if origin and host not in origin:
            raise HTTPException(status_code=403, detail="CSRF 校验失败")

    return await call_next(request)
```

### 9.3 双因素确认

敏感操作（配置变更、删除）要求双因素确认：

```python
@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    confirm: bool = False,  # 必须显式确认
):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="删除操作需显式确认（confirm=true）"
        )
    # 执行删除
```

---

## 10. 速率限制

### 10.1 速率限制策略

| 端点类别 | 限制 | 窗口 | 说明 |
|----------|------|------|------|
| 论题生成 | 10 次 | 每分钟 | 防止滥用 LLM 调用 |
| 文献检索 | 20 次 | 每分钟 | 防止 arXiv/S2 API 封禁 |
| 配置变更 | 5 次 | 每分钟 | 防止配置抖动 |
| 消息发送 | 30 次 | 每分钟 | 防止刷屏 |
| 读操作 | 100 次 | 每分钟 | 防止爬虫 |
| 全局 | 200 次 | 每分钟 | 总体限制 |

### 10.2 Nginx 速率限制配置

```nginx
# 定义速率限制区域
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
limit_req_zone $binary_remote_addr zone=generate:10m rate=10r/m;
limit_req_zone $binary_remote_addr zone=search:10m rate=20r/m;

server {
    # 全局限制
    limit_req zone=api burst=20 nodelay;

    # 论题生成限制
    location /api/proposals/generate {
        limit_req zone=generate burst=5 nodelay;
        proxy_pass http://127.0.0.1:8000;
    }

    # 文献检索限制
    location /api/constraints/search-literature {
        limit_req zone=search burst=10 nodelay;
        proxy_pass http://127.0.0.1:8000;
    }

    # 其他 API
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

### 10.3 应用层速率限制

```python
# backend/middleware/rate_limit.py
import time
from collections import defaultdict
from fastapi import Request, HTTPException


class RateLimiter:
    """简单的内存速率限制器"""

    def __init__(self):
        self.requests = defaultdict(list)  # {ip: [timestamp, ...]}

    def check(self, ip: str, limit: int, window: int = 60) -> bool:
        """检查是否超过限制

        Args:
            ip: 客户端 IP
            limit: 窗口内最大请求数
            window: 窗口大小（秒）

        Returns:
            未超限返回 True，超限返回 False
        """
        now = time.time()
        # 清理过期记录
        self.requests[ip] = [
            ts for ts in self.requests[ip]
            if now - ts < window
        ]
        # 检查是否超限
        if len(self.requests[ip]) >= limit:
            return False
        # 记录请求
        self.requests[ip].append(now)
        return True


rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """速率限制中间件"""
    client_ip = request.client.host
    path = request.url.path

    # 根据路径设置限制
    if "/proposals/generate" in path:
        limit = 10
    elif "/search-literature" in path:
        limit = 20
    elif "/config" in path and request.method == "POST":
        limit = 5
    else:
        limit = 100

    if not rate_limiter.check(client_ip, limit):
        raise HTTPException(
            status_code=429,
            detail=f"请求过于频繁，请 {60} 秒后重试"
        )

    return await call_next(request)
```

### 10.4 429 响应格式

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "请求过于频繁",
    "detail": {
      "limit": 10,
      "window": 60,
      "retry_after": 45
    },
    "request_id": "req_abc123",
    "timestamp": "2026-06-19T10:30:45Z"
  }
}
```

---

## 11. 审计日志

### 11.1 审计日志架构

```text
┌─────────────────────────────────────────────────────────────┐
│                    审计日志架构                              │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 应用日志    │  │ 访问日志    │  │ 账本日志    │         │
│  │ (Python     │  │ (Nginx      │  │ (SQLite     │         │
│  │  logging)   │  │  access)    │  │  budget_    │         │
│  │             │  │             │  │  ledger)    │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┴────────────────┘                 │
│                          │                                  │
│                          ▼                                  │
│                   ┌─────────────┐                           │
│                   │ 日志收集器   │                           │
│                   │ (Filebeat)  │                           │
│                   └──────┬──────┘                           │
│                          │                                  │
│                          ▼                                  │
│                   ┌─────────────┐                           │
│                   │ 日志存储     │                           │
│                   │ (Elasticsearch│                         │
│                   │  / Loki)    │                           │
│                   └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

### 11.2 审计事件清单

| 事件 | 日志级别 | 记录内容 | 保留期 |
|------|----------|----------|--------|
| 服务启动 | INFO | version, db_path, ai_configured | 30 天 |
| 服务停止 | INFO | uptime, total_requests | 30 天 |
| 配置变更 | WARNING | 变更字段名（不含值）、IP、时间 | 90 天 |
| API Key 更新 | WARNING | 时间、IP（不记录 Key 明文） | 90 天 |
| 论题删除 | INFO | 论题 ID、会话 ID、时间 | 30 天 |
| 会话删除 | INFO | 会话 ID、关联论题数、时间 | 30 天 |
| LLM 调用失败 | ERROR | Agent ID、模型、错误、重试次数 | 30 天 |
| 硬约束拦截 | WARNING | 拦截类型、违规详情、请求 ID | 30 天 |
| 速率限制触发 | WARNING | IP、端点、限制值 | 7 天 |
| 数据库异常 | ERROR | 操作、错误信息 | 30 天 |
| 文件操作 | INFO | 文件路径、操作类型、大小 | 30 天 |

### 11.3 日志格式

应用日志采用结构化 JSON 格式：

```json
{
  "timestamp": "2026-06-19T10:30:45.123Z",
  "level": "WARNING",
  "logger": "backend.routes.config",
  "message": "Configuration updated",
  "event_type": "config_update",
  "changed_fields": ["ai_model", "currency"],
  "source_ip": "192.168.1.100",
  "request_id": "req_abc123",
  "session_id": "sess_xyz789",
  "user_agent": "Mozilla/5.0..."
}
```

### 11.4 日志脱敏

```python
# backend/utils/log_sanitizer.py
import re
import logging


class SanitizingFilter(logging.Filter):
    """日志脱敏过滤器"""

    PATTERNS = {
        "api_key": (re.compile(r'sk-[a-zA-Z0-9]{20,}'), 'sk-***'),
        "email": (re.compile(r'\b[\w.-]+@[\w.-]+\.\w+\b'), '***@***.***'),
        "phone": (re.compile(r'\b1[3-9]\d{9}\b'), '1**-****-****'),
        "id_card": (re.compile(r'\b\d{17}[\dXx]\b'), '******************'),
    }

    def filter(self, record):
        if isinstance(record.msg, str):
            for name, (pattern, replacement) in self.PATTERNS.items():
                record.msg = pattern.sub(replacement, record.msg)
        return True


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
    handlers=[
        logging.FileHandler("data/logs/thesisminer.log"),
        logging.StreamHandler(),
    ]
)

# 添加脱敏过滤器
for handler in logging.getLogger().handlers:
    handler.addFilter(SanitizingFilter())
```

### 11.5 日志保护

```bash
# 日志文件权限（仅 owner 可读写）
chmod 600 data/logs/thesisminer.log

# 日志追加模式（防止篡改）
chattr +a data/logs/thesisminer.log  # Linux 仅追加属性

# 日志轮转（logrotate）
cat > /etc/logrotate.d/thesisminer << 'EOF'
data/logs/thesisminer.log {
    daily
    rotate 90
    compress
    delaycompress
    missingok
    notifempty
    create 600 thesisminer thesisminer
}
EOF
```

---

## 12. 安全配置清单

### 12.1 部署前检查清单

#### 文件权限

- [ ] `data/config.json` 权限 600
- [ ] `.env` 文件权限 600
- [ ] `data/` 目录权限 700
- [ ] `data/thesis_miner.db` 权限 600
- [ ] `data/logs/` 目录权限 700
- [ ] 日志文件权限 600

#### 网络配置

- [ ] 防火墙仅开放 80/443 端口
- [ ] 服务监听 127.0.0.1（仅通过反向代理对外）
- [ ] HTTPS 证书已配置
- [ ] HSTS 已启用

#### 服务配置

- [ ] 服务以非 root 用户运行
- [ ] Uvicorn worker 数量合理（4 个）
- [ ] 超时设置合理（30 秒）
- [ ] 请求体大小限制（1MB）

#### AI 服务配置

- [ ] AI API Key 已配置且测试通过
- [ ] API Key 不在版本控制中
- [ ] API Key 在日志中脱敏
- [ ] AI 服务调用通过 HTTPS

#### 数据库配置

- [ ] WAL 模式已启用
- [ ] 外键约束已启用
- [ ] busy_timeout 已设置（5000ms）
- [ ] 定期备份已配置

### 12.2 运行时检查清单

- [ ] 定期检查日志中的 ERROR 事件
- [ ] 监控 API 调用速率
- [ ] 监控 LLM 调用费用
- [ ] 定期更新依赖包（`pip audit`）
- [ ] 监控磁盘空间
- [ ] 监控内存占用
- [ ] 定期备份验证

### 12.3 安全扫描

```bash
# 依赖漏洞扫描
pip install pip-audit
pip-audit

# 代码静态分析
pip install bandit
bandit -r backend/

# SSL 证书检查
openssl s_client -connect thesisminer.example.com:443 -servername thesisminer.example.com

# 端口扫描
nmap -sT -O localhost
```

---

## 13. 应急响应

### 13.1 应急响应流程

```text
安全事件发生
   │
   ▼
┌─────────────────────────┐
│ 1. 识别与确认            │
│ - 确认事件类型           │
│ - 评估影响范围           │
│ - 记录初始信息           │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 2. 遏制与隔离            │
│ - 停止受影响服务         │
│ - 隔离受影响系统         │
│ - 撤销受影响的凭证       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 3. 根除与恢复            │
│ - 修复漏洞              │
│ - 恢复服务              │
│ - 验证修复效果           │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 4. 事后分析              │
│ - 分析事件原因           │
│ - 评估损失              │
│ - 改进安全措施           │
│ - 编写事件报告           │
└─────────────────────────┘
```

### 13.2 常见事件响应

#### 13.2.1 API Key 泄露

```bash
# 1. 吊销 Key
# 在 AI 服务商后台吊销泄露的 Key

# 2. 生成新 Key 并更新
curl -X POST https://thesisminer.example.com/api/config \
  -H "Content-Type: application/json" \
  -d '{"ai_api_key": "sk-new-key-xxxxx"}'

# 3. 重启服务
systemctl restart thesisminer

# 4. 审计日志
grep "config_update" /var/log/thesisminer/app.log | tail -20

# 5. 检查异常调用
# 在 AI 服务商后台查看近期调用记录
```

#### 13.2.2 数据库损坏

```bash
# 1. 停止服务
systemctl stop thesisminer

# 2. 备份损坏的数据库
cp data/thesis_miner.db data/thesis_miner.db.corrupted.$(date +%Y%m%d)

# 3. 尝试恢复
sqlite3 data/thesis_miner.db ".recover" > recovered.sql
sqlite3 data/thesis_miner_new.db < recovered.sql

# 4. 验证完整性
sqlite3 data/thesis_miner_new.db "PRAGMA integrity_check;"

# 5. 替换数据库
mv data/thesis_miner.db data/thesis_miner.db.corrupted
mv data/thesis_miner_new.db data/thesis_miner.db

# 6. 重启服务
systemctl start thesisminer
```

#### 13.2.3 DDoS 攻击

```bash
# 1. 查看攻击来源
tail -f /var/log/nginx/access.log | grep "403\|429"

# 2. 临时封禁 IP
iptables -A INPUT -s <attacker_ip> -j DROP

# 3. 收紧速率限制
# 编辑 Nginx 配置，降低 rate 值
nginx -s reload

# 4. 启用 CDN 防护（如 Cloudflare）
```

#### 13.2.4 未授权访问

```bash
# 1. 查看访问日志
grep "POST\|DELETE\|PUT" /var/log/nginx/access.log | tail -50

# 2. 检查认证配置
cat /etc/nginx/.htpasswd

# 3. 重置所有密码
htpasswd -c /etc/nginx/.htpasswd admin

# 4. 重启 Nginx
nginx -s reload
```

---

## 14. 附录

### 14.1 安全相关文件清单

| 文件 | 用途 |
|------|------|
| `backend/config.py` | API Key 存储与脱敏 |
| `backend/database.py` | 参数化查询、连接管理 |
| `backend/models.py` | Pydantic 输入校验 |
| `backend/middleware/rate_limit.py` | 速率限制中间件 |
| `backend/middleware/csrf.py` | CSRF 防护中间件 |
| `backend/utils/log_sanitizer.py` | 日志脱敏 |
| `backend/utils/path_validator.py` | 路径校验 |
| `.gitignore` | 排除敏感文件 |
| `.env.example` | 环境变量示例（不含真实 Key） |

### 14.2 安全测试清单

- [ ] SQL 注入测试（所有输入字段）
- [ ] XSS 测试（所有展示字段）
- [ ] CSRF 测试（所有写操作）
- [ ] 路径穿越测试（文件操作）
- [ ] 速率限制测试（高频请求）
- [ ] 权限提升测试（未授权访问）
- [ ] 信息泄露测试（错误响应）
- [ ] 依赖漏洞扫描（pip-audit）
- [ ] 代码静态分析（bandit）
- [ ] SSL 配置检查（SSL Labs）

### 14.3 安全参考资料

1. OWASP Top 10：<https://owasp.org/Top10/>
2. FastAPI 安全：<https://fastapi.tiangolo.com/tutorial/security/>
3. SQLite 安全：<https://www.sqlite.org/security.html>
4. Nginx 安全配置：<https://nginx.org/en/docs/http/configuring_https_servers.html>
5. CSP 策略：<https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP>
6. TLS 最佳实践：<https://ssl-config.mozilla.org/>

### 14.4 安全联系人

| 角色 | 职责 | 联系方式 |
|------|------|----------|
| 安全负责人 | 安全事件响应 | security@thesisminer.example.com |
| 运维负责人 | 系统运维 | ops@thesisminer.example.com |
| 开发负责人 | 代码安全 | dev@thesisminer.example.com |

---

> **文档版本**：v8.0
> **最后更新**：2026-06-19
> **维护团队**：ThesisMiner 安全组

---

> **文档结束**
> 本文档完整覆盖 ThesisMiner v8.0 的安全设计，包括认证授权、API Key 管理、数据加密、输入校验、SQL 注入防护、XSS/CSRF 防护、速率限制、审计日志与应急响应，作为安全工程师与运维人员的综合性参考。
