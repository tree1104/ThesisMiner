# ThesisMiner v8.0 故障排查完整指南

> **文档版本**：v8.0.0  
> **最后更新**：2026-06-19  
> **文档定位**：ThesisMiner 常见问题的诊断与解决指南，覆盖启动、连接、Agent、缓存、前端、数据库、性能等 50+ 已知问题  
> **适用对象**：开发者、运维人员、终端用户  

---

## 目录

- [1. 故障排查方法论](#1-故障排查方法论)
- [2. 启动失败类问题](#2-启动失败类问题)
- [3. 连接错误类问题](#3-连接错误类问题)
- [4. Agent 异常类问题](#4-agent-异常类问题)
- [5. 缓存问题类问题](#5-缓存问题类问题)
- [6. 前端渲染类问题](#6-前端渲染类问题)
- [7. 数据库类问题](#7-数据库类问题)
- [8. 性能调优类问题](#8-性能调优类问题)
- [9. 日志分析](#9-日志分析)
- [10. 诊断工具集](#10-诊断工具集)
- [11. 附录](#11-附录)

---

## 1. 故障排查方法论

### 1.1 故障排查流程

```
┌──────────────────────────────────────────────────────┐
│              故障排查标准流程                          │
├──────────────────────────────────────────────────────┤
│                                                      │
│  步骤 1：现象收集                                     │
│  ─────────                                           │
│  · 错误消息是什么？                                   │
│  · 错误何时发生？                                     │
│  · 错误在什么操作后发生？                             │
│  · 错误是否可复现？                                   │
│  · 错误的影响范围？                                   │
│                                                      │
│  步骤 2：日志分析                                     │
│  ─────────                                           │
│  · 查看应用日志（logs/thesisminer.log）              │
│  · 查看错误日志（grep ERROR）                        │
│  · 查看请求 ID 追踪                                  │
│  · 查看时间线                                        │
│                                                      │
│  步骤 3：环境检查                                     │
│  ─────────                                           │
│  · Python 版本是否正确？                              │
│  · 依赖是否完整？                                     │
│  · 配置是否正确？                                     │
│  · 网络是否通畅？                                     │
│  · 资源是否充足？                                     │
│                                                      │
│  步骤 4：假设验证                                     │
│  ─────────                                           │
│  · 根据现象和日志提出假设                             │
│  · 设计验证实验                                       │
│  · 执行验证                                           │
│  · 记录结果                                           │
│                                                      │
│  步骤 5：解决方案                                     │
│  ─────────                                           │
│  · 应用修复方案                                       │
│  · 验证修复效果                                       │
│  · 记录解决方案                                       │
│  · 更新文档                                           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 1.2 问题分类索引

| 类别 | 问题数 | 严重程度 | 典型症状 |
|------|--------|---------|---------|
| 启动失败 | 12 | 高 | 服务无法启动 |
| 连接错误 | 10 | 高 | AI 调用失败 |
| Agent 异常 | 10 | 中 | 论题生成失败 |
| 缓存问题 | 8 | 中 | 缓存命中率低 |
| 前端渲染 | 8 | 低 | 页面显示异常 |
| 数据库 | 6 | 高 | 数据操作失败 |
| 性能调优 | 6 | 低 | 响应缓慢 |
| **总计** | **60** | - | - |

---

## 2. 启动失败类问题

### 问题 2.1：端口被占用

**症状**：

```
ERROR:    [uvicorn.error][ERROR] Uvicorn running on http://0.0.0.0:8000
ERROR:    [uvicorn.error][ERROR] Address already in use
```

**原因**：8000 端口已被其他进程占用。

**诊断步骤**：

```bash
# Linux/Mac
lsof -i :8000
# 或
netstat -tlnp | grep 8000

# Windows
netstat -ano | findstr :8000
```

**解决方案**：

```bash
# 方案 1：终止占用进程
kill -9 <PID>  # Linux/Mac
taskkill /PID <PID> /F  # Windows

# 方案 2：更换端口
python main.py --port 8001

# 方案 3：修改配置
# 在 .env 文件中设置
SERVER_PORT=8001
```

### 问题 2.2：Python 依赖缺失

**症状**：

```
ModuleNotFoundError: No module named 'fastapi'
```

**原因**：未安装项目依赖或虚拟环境未激活。

**诊断步骤**：

```bash
# 检查虚拟环境是否激活
which python  # Linux/Mac
where python  # Windows

# 检查已安装的包
pip list | grep fastapi
```

**解决方案**：

```bash
# 方案 1：激活虚拟环境后安装
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt

# 方案 2：重新创建虚拟环境
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 方案 3：使用 pip-sync 精确安装
pip install pip-tools
pip-sync requirements.txt
```

### 问题 2.3：配置文件缺失

**症状**：

```
FileNotFoundError: [Errno 2] No such file or directory: 'config.json'
```

**原因**：配置文件不存在或路径错误。

**诊断步骤**：

```bash
# 检查配置文件
ls -la config.json .env

# 检查配置路径
python -c "from backend.config import Config; print(Config.config_path)"
```

**解决方案**：

```bash
# 方案 1：创建默认配置
cp config.example.json config.json

# 方案 2：使用环境变量
export OPENAI_API_KEY=sk-xxx
export DEEPSEEK_API_KEY=sk-xxx

# 方案 3：创建 .env 文件
cat > .env << EOF
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
DATABASE_PATH=data/thesisminer.db
EOF
```

### 问题 2.4：数据库初始化失败

**症状**：

```
sqlite3.OperationalError: unable to open database file
```

**原因**：数据库目录不存在或权限不足。

**诊断步骤**：

```bash
# 检查数据库目录
ls -la data/

# 检查目录权限
ls -ld data/
```

**解决方案**：

```bash
# 方案 1：创建数据目录
mkdir -p data
chmod 755 data

# 方案 2：修改数据库路径
# 在 .env 文件中设置
DATABASE_PATH=/tmp/thesisminer.db

# 方案 3：检查磁盘空间
df -h
```

### 问题 2.5：API Key 未配置

**症状**：

```
ValueError: OPENAI_API_KEY is not set
```

**原因**：未配置 AI 模型的 API Key。

**诊断步骤**：

```bash
# 检查环境变量
echo $OPENAI_API_KEY
echo $DEEPSEEK_API_KEY

# 检查 .env 文件
cat .env | grep API_KEY
```

**解决方案**：

```bash
# 方案 1：设置环境变量
export OPENAI_API_KEY=sk-xxx
export DEEPSEEK_API_KEY=sk-xxx

# 方案 2：在 .env 文件中配置
echo 'OPENAI_API_KEY=sk-xxx' >> .env
echo 'DEEPSEEK_API_KEY=sk-xxx' >> .env

# 方案 3：在 config.json 中配置
{
  "api_keys": {
    "openai": "sk-xxx",
    "deepseek": "sk-xxx"
  }
}
```

### 问题 2.6：Python 版本不兼容

**症状**：

```
SyntaxError: invalid syntax
```

**原因**：Python 版本低于 3.10，不支持新语法。

**诊断步骤**：

```bash
python --version
```

**解决方案**：

```bash
# 方案 1：升级 Python
# Linux
sudo apt update && sudo apt install python3.11

# Mac
brew install python@3.11

# Windows: 从 python.org 下载安装

# 方案 2：使用 pyenv 管理版本
pyenv install 3.11
pyenv local 3.11
```

### 问题 2.7：权限不足

**症状**：

```
PermissionError: [Errno 13] Permission denied
```

**原因**：文件或目录权限不足。

**解决方案**：

```bash
# 修改文件权限
chmod 644 config.json
chmod 755 data/
chmod 755 logs/

# 修改所有者
chown user:group data/
chown user:group logs/
```

### 问题 2.8：CORS 配置错误

**症状**：

```
Access to fetch at 'http://localhost:8000/api/...' from origin 'http://localhost:3000' 
has been blocked by CORS policy
```

**原因**：CORS 配置未包含前端域名。

**解决方案**：

```python
# 在 main.py 中配置 CORS
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 问题 2.9：静态文件路径错误

**症状**：前端页面加载 404。

**原因**：静态文件路径配置错误。

**解决方案**：

```python
# 在 main.py 中正确挂载静态文件
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```

### 问题 2.10：自动打开浏览器失败

**症状**：

```
Failed to open browser automatically
```

**原因**：服务器环境无图形界面。

**解决方案**：

```bash
# 方案 1：禁用自动打开浏览器
# 在 .env 文件中设置
AUTO_OPEN_BROWSER=false

# 方案 2：手动打开浏览器
# 访问 http://localhost:8000
```

### 问题 2.11：Uvicorn worker 数量配置错误

**症状**：服务器启动后响应缓慢。

**原因**：worker 数量配置不当。

**解决方案**：

```bash
# 方案 1：使用合适的 worker 数量（CPU 核心数 × 2 + 1）
uvicorn main:app --workers 5

# 方案 2：在配置文件中设置
# config.json
{
  "uvicorn": {
    "workers": 5,
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

### 问题 2.12：日志目录不存在

**症状**：

```
FileNotFoundError: [Errno 2] No such file or directory: 'logs/thesisminer.log'
```

**解决方案**：

```bash
# 创建日志目录
mkdir -p logs
chmod 755 logs
```

---

## 3. 连接错误类问题

### 问题 3.1：OpenAI API 连接失败

**症状**：

```
openai.APIConnectionError: Error communicating with OpenAI
```

**诊断步骤**：

```bash
# 1. 检查 API Key
python -c "import os; print(os.getenv('OPENAI_API_KEY'))"

# 2. 测试网络连通性
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 3. 检查代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

**解决方案**：

```bash
# 方案 1：检查并更新 API Key
export OPENAI_API_KEY=sk-xxx

# 方案 2：配置代理
export HTTP_PROXY=http://proxy:8080
export HTTPS_PROXY=http://proxy:8080

# 方案 3：配置 base_url（使用代理或镜像）
# .env 文件
OPENAI_BASE_URL=https://your-proxy.com/v1
```

### 问题 3.2：DeepSeek API 超时

**症状**：

```
openai.APITimeoutError: Request timed out
```

**原因**：DeepSeek API 响应超过超时时间。

**解决方案**：

```python
# 方案 1：增加超时时间
client = openai.OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
    timeout=180,  # 180 秒
)

# 方案 2：使用重试机制
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def call_deepseek(prompt):
    return client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[{"role": "user", "content": prompt}],
    )
```

### 问题 3.3：SSL 证书错误

**症状**：

```
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**解决方案**：

```bash
# 方案 1：更新 CA 证书
# Linux
sudo apt update && sudo apt install ca-certificates

# Mac
brew install ca-certificates

# 方案 2：设置证书路径
export SSL_CERT_FILE=/path/to/cacert.pem
export REQUESTS_CA_BUNDLE=/path/to/cacert.pem

# 方案 3：临时跳过验证（不推荐，仅用于调试）
# 在代码中
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```

### 问题 3.4：DNS 解析失败

**症状**：

```
socket.gaierror: [Errno -2] Name or service not known
```

**诊断步骤**：

```bash
# 检查 DNS 解析
nslookup api.openai.com
dig api.openai.com

# 检查 DNS 配置
cat /etc/resolv.conf
```

**解决方案**：

```bash
# 方案 1：更换 DNS 服务器
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf

# 方案 2：添加 hosts 记录
echo "104.18.6.192 api.openai.com" | sudo tee -a /etc/hosts
```

### 问题 3.5：网络代理配置错误

**症状**：API 调用超时或连接被拒绝。

**解决方案**：

```bash
# 方案 1：正确配置代理
export HTTP_PROXY=http://user:password@proxy:8080
export HTTPS_PROXY=http://user:password@proxy:8080
export NO_PROXY=localhost,127.0.0.1

# 方案 2：在代码中配置
import os
os.environ['HTTP_PROXY'] = 'http://proxy:8080'
os.environ['HTTPS_PROXY'] = 'http://proxy:8080'

# 方案 3：使用 socks 代理
pip install pysocks
export ALL_PROXY=socks5://proxy:1080
```

### 问题 3.6：API Key 无效

**症状**：

```
openai.AuthenticationError: Incorrect API key provided
```

**解决方案**：

```bash
# 1. 检查 API Key 格式
echo $OPENAI_API_KEY  # 应以 sk- 开头

# 2. 验证 API Key 有效性
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 3. 重新生成 API Key
# 访问 https://platform.openai.com/api-keys
```

### 问题 3.7：API 速率限制

**症状**：

```
openai.RateLimitError: Rate limit reached
```

**解决方案**：

```python
# 方案 1：实现指数退避重试
import time
import openai

def call_with_retry(prompt, max_retries=5):
    for i in range(max_retries):
        try:
            return openai.ChatCompletion.create(
                model="gpt-4.1",
                messages=[{"role": "user", "content": prompt}],
            )
        except openai.RateLimitError:
            wait = 2 ** i
            print(f"速率限制，等待 {wait} 秒...")
            time.sleep(wait)
    raise Exception("重试次数耗尽")

# 方案 2：切换到备用模型
def call_with_fallback(prompt):
    models = ["gpt-4.1", "deepseek-chat-v3", "qwen-plus"]
    for model in models:
        try:
            return call_model(model, prompt)
        except openai.RateLimitError:
            continue
    raise Exception("所有模型均被限流")
```

### 问题 3.8：WebSocket 连接断开

**症状**：流式输出中断。

**解决方案**：

```javascript
// 前端实现自动重连
class SSEClient {
  constructor(url) {
    this.url = url
    this.reconnectDelay = 1000
    this.maxReconnectDelay = 30000
  }

  connect() {
    this.eventSource = new EventSource(this.url)

    this.eventSource.onopen = () => {
      console.log('SSE 连接已建立')
      this.reconnectDelay = 1000
    }

    this.eventSource.onerror = () => {
      console.error('SSE 连接断开，尝试重连...')
      this.eventSource.close()
      setTimeout(() => this.connect(), this.reconnectDelay)
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay)
    }
  }
}
```

### 问题 3.9：防火墙阻断

**症状**：连接超时。

**解决方案**：

```bash
# 检查防火墙规则
sudo iptables -L -n
sudo ufw status

# 开放必要端口
sudo ufw allow 8000/tcp
sudo ufw allow 443/tcp
```

### 问题 3.10：CDN 加载失败

**症状**：前端样式或脚本加载失败。

**解决方案**：

```html
<!-- 使用 CDN 回退 -->
<script src="https://cdn.tailwindcss.com"></script>
<script>
  if (typeof tailwind === 'undefined') {
    document.write('<script src="/static/js/tailwind.min.js"><\/script>')
  }
</script>
```

---

## 4. Agent 异常类问题

### 问题 4.1：Reasoner Agent 超时

**症状**：

```
AGENT_REASONER_TIMEOUT_001: Reasoner 调用超时（120s）
```

**诊断步骤**：

1. 检查输入复杂度（是否过长）
2. 检查 DST 历史长度
3. 检查模型负载
4. 查看日志中的调用时间线

**解决方案**：

```python
# 方案 1：增加超时时间
REASONER_TIMEOUT = 180  # 从 120 增加到 180

# 方案 2：简化输入
def simplify_input(context: dict) -> dict:
    """简化 Reasoner 输入"""
    # 减少 DST 历史长度
    context["dst_history"] = context["dst_history"][-5:]
    # 截断过长的用户输入
    context["user_input"] = context["user_input"][:2000]
    return context

# 方案 3：切换到更快的模型
REASONER_MODEL = "deepseek-chat-v3"  # 从 deepseek-reasoner 切换
```

### 问题 4.2：Agent 上下文溢出

**症状**：

```
AGENT_CONTEXT_OVERFLOW_001: Agent 上下文溢出
Token count: 130000, Max: 128000
```

**原因**：DST 压缩不足，历史消息过长。

**解决方案**：

```python
# 方案 1：增加 DST 压缩频率
DST_COMPACT_THRESHOLD = 10  # 从 20 降到 10

# 方案 2：调整压缩参数
DST_CONFIG = {
    "max_history": 5,        # 保留最近 5 条
    "summary_ratio": 0.3,    # 压缩到 30%
    "preserve_recent": True,  # 保留最近消息
}

# 方案 3：手动清理历史
def clear_old_history(session_id: str, keep: int = 5):
    """清理旧的历史消息"""
    messages = get_messages(session_id)
    if len(messages) > keep:
        old_messages = messages[:-keep]
        for msg in old_messages:
            delete_message(msg.id)
```

### 问题 4.3：模型不可用

**症状**：

```
AGENT_MODEL_UNAVAILABLE_001: 模型 deepseek-reasoner 不可用
```

**解决方案**：

```python
# 方案 1：配置模型降级链
MODEL_FALLBACK_CHAIN = {
    "reasoner": ["deepseek-reasoner", "gpt-4.1", "deepseek-chat-v3"],
    "mentor": ["gpt-4.1", "deepseek-chat-v3", "qwen-plus"],
}

async def call_with_fallback(step: str, prompt: str):
    """带降级的模型调用"""
    models = MODEL_FALLBACK_CHAIN.get(step, ["deepseek-chat-v3"])
    for model in models:
        try:
            return await call_model(model, prompt)
        except ModelUnavailableError:
            continue
    raise Exception(f"所有模型均不可用: {models}")

# 方案 2：检查模型健康状态
async def check_model_health():
    """检查所有模型可用性"""
    for model in REGISTERED_MODELS:
        try:
            await test_model(model)
            logger.info(f"模型 {model} 可用")
        except Exception:
            logger.warning(f"模型 {model} 不可用")
```

### 问题 4.4：JSON 解析失败

**症状**：

```
AGENT_PARSE_ERROR_001: Reasoner 响应解析失败
JSONDecodeError: Expecting value: line 1 column 1
```

**原因**：模型返回的 JSON 格式不正确。

**解决方案**：

```python
import json
import re

def parse_model_response(response: str) -> dict:
    """健壮的 JSON 解析"""
    # 方案 1：提取 JSON 块
    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    if json_match:
        response = json_match.group(1)

    # 方案 2：尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 方案 3：修复常见 JSON 错误
    fixed = response.replace("'", '"')  # 单引号转双引号
    fixed = re.sub(r',\s*}', '}', fixed)  # 移除尾逗号
    fixed = re.sub(r',\s*]', ']', fixed)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}")
        logger.debug(f"原始响应: {response}")
        raise

# 方案 4：在 Prompt 中强调 JSON 格式
PROMPT_SUFFIX = """
请确保返回严格的 JSON 格式，不要包含任何其他文本。
JSON 格式如下：
```json
{
  "title": "论题标题",
  "abstract": "摘要",
  ...
}
```
"""
```

### 问题 4.5：Agent 注册失败

**症状**：

```
AGENT_REGISTRY_001: Agent 注册失败，ID 重复
```

**解决方案**：

```python
# 方案 1：使用唯一 ID
import uuid

class CustomAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_id=f"custom-{uuid.uuid4().hex[:8]}")

# 方案 2：检查 ID 是否已存在
def register_agent(agent: BaseAgent):
    if agent.id in AGENT_REGISTRY:
        raise ValueError(f"Agent ID 已存在: {agent.id}")
    AGENT_REGISTRY[agent.id] = agent
```

### 问题 4.6：编排状态机异常

**症状**：

```
AGENT_ORCHESTRATION_001: 非法状态转换
Current: completed, Target: reasoning
```

**解决方案**：

```python
# 方案 1：检查状态转换合法性
VALID_TRANSITIONS = {
    "init": ["inspiring"],
    "inspiring": ["reasoning"],
    "reasoning": ["validating"],
    "validating": ["completed", "failed"],
    "completed": [],  # 终态
    "failed": ["init"],  # 可重试
}

def transition(current: str, target: str):
    if target not in VALID_TRANSITIONS.get(current, []):
        raise StateMachineError(
            f"非法状态转换: {current} → {target}"
        )
    return target

# 方案 2：重置状态机
def reset_state_machine(session_id: str):
    """重置会话的编排状态机"""
    session = get_session(session_id)
    session.orchestration_state = "init"
    save_session(session)
```

### 问题 4.7：Hook 执行失败

**症状**：

```
AGENT_HOOK_001: Hook pre_search 执行失败
```

**解决方案**：

```python
# 方案 1：添加 Hook 错误处理
async def safe_hook_execution(hook_name: str, context: dict):
    try:
        return await HOOKS[hook_name](context)
    except Exception as e:
        logger.error(f"Hook {hook_name} 执行失败: {e}")
        # 返回原始上下文，不中断流程
        return context

# 方案 2：禁用出问题的 Hook
DISABLED_HOOKS = ["pre_search"]  # 临时禁用

async def run_hooks(hook_name: str, context: dict):
    if hook_name in DISABLED_HOOKS:
        logger.warning(f"Hook {hook_name} 已禁用")
        return context
    return await HOOKS[hook_name](context)
```

### 问题 4.8：Searcher 检索超时

**症状**：

```
AGENT_SEARCHER_TIMEOUT_001: Searcher 检索超时（5s）
```

**解决方案**：

```python
# 方案 1：增加超时时间
SEARCHER_TIMEOUT = 10  # 从 5 增加到 10

# 方案 2：使用模拟检索
async def search_with_fallback(query: str):
    try:
        return await asyncio.wait_for(
            real_search(query),
            timeout=SEARCHER_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning("真实检索超时，降级到模拟检索")
        return await mock_search(query)
```

### 问题 4.9：Mentor 评审失败

**症状**：

```
AGENT_MENTOR_REVIEW_001: Mentor 评审失败
```

**解决方案**：

```python
# 方案 1：简化评审输入
def simplify_for_mentor(proposal: dict) -> dict:
    """简化论题数据供 Mentor 评审"""
    return {
        "title": proposal["title"],
        "abstract": proposal["abstract"][:500],
        "key_points": proposal.get("key_points", [])[:5],
    }

# 方案 2：使用模板评审
def template_review(proposal: dict) -> dict:
    """模板评审（兜底方案）"""
    return {
        "score": 70,
        "comments": "自动评审：论题基本合理，建议进一步细化研究方法。",
        "suggestions": ["明确研究方法", "增加文献支撑"],
    }
```

### 问题 4.10：Agent 结果聚合失败

**症状**：

```
AGENT_ORCHESTRATION_003: 结果聚合失败，格式不一致
```

**解决方案**：

```python
# 方案 1：标准化 Agent 输出
def standardize_result(result: dict) -> dict:
    """标准化 Agent 输出格式"""
    return {
        "title": result.get("title", ""),
        "abstract": result.get("abstract", ""),
        "confidence": result.get("confidence", 0.5),
        "metadata": result.get("metadata", {}),
    }

# 方案 2：添加结果验证
def validate_result(result: dict) -> bool:
    """验证 Agent 结果"""
    required_fields = ["title", "abstract"]
    return all(field in result for field in required_fields)
```

---

## 5. 缓存问题类问题

### 问题 5.1：缓存命中率低

**症状**：缓存命中率 < 20%。

**诊断步骤**：

```bash
# 查看缓存统计
curl http://localhost:8000/api/cache/stats

# 检查缓存日志
grep "CACHE_MISS" logs/thesisminer.log | tail -100
```

**原因分析**：

1. Prompt 前缀部分不稳定（每次变化）
2. DST 压缩参数频繁调整
3. 会话频繁切换
4. 缓存过期时间过短

**解决方案**：

```python
# 方案 1：固化 Prompt 前缀
# 确保系统提示、角色定义等前缀部分保持稳定
STABLE_PREFIX = """
你是一个学术论题生成助手。
你的任务是根据用户输入生成高质量的论题提案。
"""  # 这部分永远不变

# 方案 2：稳定 DST 压缩参数
DST_CONFIG = {
    "max_history": 10,       # 固定值，不频繁调整
    "summary_ratio": 0.3,    # 固定值
    "compact_threshold": 15, # 固定值
}

# 方案 3：减少会话切换
# 每次切换会话会导致前缀变化，降低缓存命中率
# 建议在单个会话内完成尽可能多的操作
```

### 问题 5.2：缓存前缀不一致

**症状**：相同请求的 SHA-256 前缀哈希不同。

**诊断步骤**：

```python
# 打印前缀哈希
def debug_cache_prefix(prompt: str):
    prefix = prompt[:CACHE_PREFIX_LENGTH]
    hash_val = hashlib.sha256(prefix.encode()).hexdigest()
    print(f"前缀长度: {len(prefix)}")
    print(f"SHA-256: {hash_val}")
    print(f"前缀内容: {prefix[:100]}...")
```

**解决方案**：

```python
# 方案 1：确保前缀部分完全一致
# 检查前缀是否包含动态内容（时间戳、随机数等）
def build_prompt(system: str, user: str, dst: str) -> str:
    # 前缀部分（稳定）
    prefix = system  # 只包含系统提示

    # 中段（动态）
    middle = user

    # 尾部（DST）
    tail = dst

    return prefix + middle + tail

# 方案 2：调整前缀长度
CACHE_PREFIX_LENGTH = 1024  # 确保前缀长度固定
```

### 问题 5.3：DST 压缩异常

**症状**：DST 压缩后内容丢失或格式错误。

**解决方案**：

```python
# 方案 1：调整压缩参数
DST_CONFIG = {
    "max_history": 10,
    "summary_ratio": 0.3,
    "preserve_keywords": True,  # 保留关键词
    "preserve_entities": True,  # 保留实体
}

# 方案 2：添加压缩验证
def validate_compressed_dst(original: str, compressed: str) -> bool:
    """验证压缩后的 DST 是否保留了关键信息"""
    keywords = extract_keywords(original)
    return all(kw in compressed for kw in keywords[:5])

# 方案 3：禁用压缩（临时）
DST_COMPRESSION_ENABLED = False
```

### 问题 5.4：缓存数据损坏

**症状**：

```
CACHE_INVALID_001: 缓存数据损坏
```

**解决方案**：

```bash
# 方案 1：清除所有缓存
curl -X DELETE http://localhost:8000/api/cache/clear

# 方案 2：删除缓存文件
rm -rf data/cache/
mkdir -p data/cache/

# 方案 3：重建缓存索引
python -m backend.cache.rebuild_index
```

### 问题 5.5：缓存过期过快

**症状**：缓存数据很快过期。

**解决方案**：

```python
# 调整缓存 TTL
CACHE_CONFIG = {
    "ttl": 3600,  # 1 小时（从 300 秒增加）
    "max_size": 1000,  # 最大缓存条目数
    "eviction_policy": "lru",  # 最近最少使用
}
```

### 问题 5.6：缓存内存占用过高

**症状**：服务器内存使用持续增长。

**解决方案**：

```python
# 方案 1：限制缓存大小
CACHE_CONFIG = {
    "max_size": 500,  # 限制最大 500 条
    "max_memory_mb": 100,  # 限制 100MB
}

# 方案 2：使用磁盘缓存
from diskcache import Cache
cache = Cache("data/cache/")

# 方案 3：定期清理
import schedule

def clean_cache():
    """定期清理过期缓存"""
    cache.cleanup()
    logger.info("缓存清理完成")

schedule.every().hour.do(clean_cache)
```

### 问题 5.7：会话切换导致缓存失效

**症状**：切换会话后缓存命中率骤降。

**解决方案**：

```python
# 方案 1：会话级缓存隔离
SESSION_CACHE = {}  # 每个会话独立缓存

def get_session_cache(session_id: str):
    if session_id not in SESSION_CACHE:
        SESSION_CACHE[session_id] = LRUCache(maxsize=100)
    return SESSION_CACHE[session_id]

# 方案 2：共享前缀缓存
# 前缀部分（系统提示）可以跨会话共享
PREFIX_CACHE = {}  # 全局前缀缓存

def get_prefix_hash(system_prompt: str) -> str:
    """获取前缀哈希（跨会话共享）"""
    if system_prompt not in PREFIX_CACHE:
        PREFIX_CACHE[system_prompt] = sha256(system_prompt.encode()).hexdigest()
    return PREFIX_CACHE[system_prompt]
```

### 问题 5.8：缓存统计不准确

**症状**：缓存命中率统计与实际不符。

**解决方案**：

```python
# 方案 1：重置统计
def reset_cache_stats():
    """重置缓存统计"""
    cache_stats = {
        "hits": 0,
        "misses": 0,
        "errors": 0,
    }

# 方案 2：使用原子计数器
from threading import Lock

class CacheStats:
    def __init__(self):
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def record_hit(self):
        with self._lock:
            self._hits += 1

    def record_miss(self):
        with self._lock:
            self._misses += 1

    @property
    def hit_rate(self):
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0
```

---

## 6. 前端渲染类问题

### 问题 6.1：D3.js 谱系图谱不显示

**症状**：谱系图谱页面空白。

**诊断步骤**：

1. 打开浏览器开发者工具（F12）
2. 检查 Console 是否有错误
3. 检查 Network 是否有 404 请求
4. 检查数据是否正确返回

**解决方案**：

```javascript
// 方案 1：检查 D3.js 是否加载
if (typeof d3 === 'undefined') {
  console.error('D3.js 未加载')
  // 手动加载
  const script = document.createElement('script')
  script.src = 'https://d3js.org/d3.v7.min.js'
  document.head.appendChild(script)
}

// 方案 2：检查数据格式
function validateGraphData(data) {
  if (!data.nodes || !data.edges) {
    console.error('图谱数据格式错误', data)
    return false
  }
  if (!Array.isArray(data.nodes) || !Array.isArray(data.edges)) {
    console.error('图谱数据应为数组')
    return false
  }
  return true
}

// 方案 3：检查 SVG 容器
function checkContainer() {
  const container = document.getElementById('lineage-graph')
  if (!container) {
    console.error('图谱容器不存在')
    return false
  }
  if (container.clientWidth === 0 || container.clientHeight === 0) {
    console.error('图谱容器尺寸为 0')
    return false
  }
  return true
}
```

### 问题 6.2：流式输出中断

**症状**：SSE 流式输出在中间断开。

**解决方案**：

```javascript
// 方案 1：实现自动重连
class RobustSSEClient {
  constructor(url, onMessage) {
    this.url = url
    this.onMessage = onMessage
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
  }

  connect() {
    this.eventSource = new EventSource(this.url)

    this.eventSource.onmessage = (event) => {
      this.reconnectAttempts = 0
      this.onMessage(JSON.parse(event.data))
    }

    this.eventSource.onerror = () => {
      this.eventSource.close()
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++
        const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000)
        console.log(`${delay}ms 后重连...`)
        setTimeout(() => this.connect(), delay)
      }
    }
  }
}

// 方案 2：使用 fetch + ReadableStream
async function streamFetch(url, onChunk) {
  const response = await fetch(url)
  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const text = decoder.decode(value)
    text.split('\n').forEach(line => {
      if (line.startsWith('data: ')) {
        onChunk(line.slice(6))
      }
    })
  }
}
```

### 问题 6.3：Tab 切换异常

**症状**：切换 Tab 后内容不更新。

**解决方案**：

```javascript
// 方案 1：确保 Tab 切换时重新渲染
function switchTab(tabName) {
  // 隐藏所有 Tab 内容
  document.querySelectorAll('.tab-content').forEach(el => {
    el.style.display = 'none'
  })

  // 显示目标 Tab
  const target = document.getElementById(`tab-${tabName}`)
  if (target) {
    target.style.display = 'block'
    // 触发重新渲染
    renderTabContent(tabName)
  }
}

// 方案 2：使用数据驱动渲染
function renderTabContent(tabName) {
  const data = getState(tabName)
  const container = document.getElementById(`tab-${tabName}`)
  container.innerHTML = renderTemplate(data)
}
```

### 问题 6.4：Tailwind CSS 样式不生效

**症状**：页面没有样式。

**解决方案**：

```html
<!-- 方案 1：检查 Tailwind CDN -->
<script src="https://cdn.tailwindcss.com"></script>

<!-- 方案 2：配置 Tailwind -->
<script>
  tailwind.config = {
    theme: {
      extend: {
        colors: {
          primary: '#3b82f6',
        }
      }
    }
  }
</script>

<!-- 方案 3：检查 Content Security Policy -->
<meta http-equiv="Content-Security-Policy" 
      content="style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com">
```

### 问题 6.5：响应式布局异常

**症状**：移动端布局错乱。

**解决方案**：

```css
/* 方案 1：添加 viewport meta */
<meta name="viewport" content="width=device-width, initial-scale=1.0">

/* 方案 2：使用响应式断点 */
.container {
  width: 100%;
  padding: 1rem;
}

@media (min-width: 768px) {
  .container {
    max-width: 768px;
    padding: 2rem;
  }
}

@media (min-width: 1024px) {
  .container {
    max-width: 1024px;
    padding: 3rem;
  }
}
```

### 问题 6.6：前端路由 404

**症状**：刷新页面后 404。

**解决方案**：

```python
# 方案：在后端添加 SPA 回退路由
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # 如果不是 API 请求，返回前端页面
    if not full_path.startswith("api/"):
        return FileResponse("frontend/index.html")
    raise HTTPException(status_code=404)
```

### 问题 6.7：JavaScript 控制台错误

**症状**：控制台显示 `Uncaught TypeError`。

**解决方案**：

```javascript
// 方案 1：添加全局错误处理
window.onerror = function(message, source, lineno, colno, error) {
  console.error('全局错误:', message, error)
  // 上报错误
  reportError({ message, source, lineno, colno, stack: error?.stack })
}

// 方案 2：使用 try-catch 包裹关键代码
try {
  renderGraph(data)
} catch (error) {
  console.error('图谱渲染失败:', error)
  showErrorMessage('图谱渲染失败，请刷新页面重试')
}
```

### 问题 6.8：内存泄漏

**症状**：页面使用时间越长越卡。

**解决方案**：

```javascript
// 方案 1：清理事件监听器
class GraphRenderer {
  constructor() {
    this.listeners = []
  }

  addListener(element, event, handler) {
    element.addEventListener(event, handler)
    this.listeners.push({ element, event, handler })
  }

  destroy() {
    this.listeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler)
    })
    this.listeners = []
  }
}

// 方案 2：清理定时器
let updateTimer = null

function startAutoUpdate() {
  updateTimer = setInterval(updateData, 5000)
}

function stopAutoUpdate() {
  if (updateTimer) {
    clearInterval(updateTimer)
    updateTimer = null
  }
}

// 页面卸载时清理
window.addEventListener('beforeunload', () => {
  stopAutoUpdate()
  graphRenderer.destroy()
})
```

---

## 7. 数据库类问题

### 问题 7.1：SQLite 数据库锁定

**症状**：

```
sqlite3.OperationalError: database is locked
```

**原因**：并发写入导致数据库锁定。

**解决方案**：

```python
# 方案 1：启用 WAL 模式
import sqlite3

def init_db():
    conn = sqlite3.connect("data/thesisminer.db")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")  # 5 秒超时
    return conn

# 方案 2：使用连接池
from queue import Queue

class ConnectionPool:
    def __init__(self, db_path, max_connections=5):
        self.pool = Queue(max_connections)
        for _ in range(max_connections):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            self.pool.put(conn)

    def get(self):
        return self.pool.get()

    def put(self, conn):
        self.pool.put(conn)

# 方案 3：重试机制
import time

def execute_with_retry(conn, sql, params, max_retries=3):
    for i in range(max_retries):
        try:
            return conn.execute(sql, params)
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                time.sleep(0.1 * (i + 1))
                continue
            raise
```

### 问题 7.2：数据库迁移失败

**症状**：

```
sqlite3.OperationalError: no such column: new_column
```

**解决方案**：

```python
# 方案 1：使用迁移脚本
def migrate_v7_to_v8():
    """v7 到 v8 的数据库迁移"""
    conn = get_db()

    # 检查当前版本
    version = conn.execute("PRAGMA user_version").fetchone()[0]

    if version < 8:
        # 添加新列
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN agent_type TEXT")
        except sqlite3.OperationalError:
            pass  # 列已存在

        # 更新版本号
        conn.execute("PRAGMA user_version = 8")
        conn.commit()

# 方案 2：备份数据后迁移
def safe_migrate():
    # 1. 备份
    import shutil
    shutil.copy("data/thesisminer.db", "data/thesisminer.db.bak")

    # 2. 迁移
    try:
        migrate_v7_to_v8()
    except Exception as e:
        # 3. 回滚
        shutil.copy("data/thesisminer.db.bak", "data/thesisminer.db")
        raise
```

### 问题 7.3：外键约束失败

**症状**：

```
sqlite3.IntegrityError: FOREIGN KEY constraint failed
```

**解决方案**：

```python
# 方案 1：启用外键检查
def init_db():
    conn = sqlite3.connect("data/thesisminer.db")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

# 方案 2：按正确顺序删除
def delete_session(session_id: str):
    conn = get_db()
    # 先删除关联数据
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM proposals WHERE session_id = ?", (session_id,))
    # 再删除会话
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()

# 方案 3：使用级联删除
# CREATE TABLE messages (
#     id TEXT PRIMARY KEY,
#     session_id TEXT,
#     content TEXT,
#     FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
# )
```

### 问题 7.4：查询缓慢

**症状**：数据库查询响应缓慢。

**解决方案**：

```python
# 方案 1：添加索引
def create_indexes():
    conn = get_db()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_proposals_session ON proposals(session_id)")
    conn.commit()

# 方案 2：使用 EXPLAIN QUERY PLAN 分析
def analyze_query(sql: str):
    conn = get_db()
    plan = conn.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
    for row in plan:
        print(row)

# 方案 3：优化查询
# ❌ 慢查询
# SELECT * FROM messages WHERE session_id = ? ORDER BY created_at DESC

# ✅ 优化后
# SELECT id, content, created_at FROM messages 
# WHERE session_id = ? ORDER BY created_at DESC LIMIT 50
```

### 问题 7.5：数据库文件过大

**症状**：数据库文件持续增长。

**解决方案**：

```python
# 方案 1：定期清理旧数据
def cleanup_old_data(days: int = 90):
    """清理 90 天前的数据"""
    conn = get_db()
    conn.execute("""
        DELETE FROM messages 
        WHERE session_id IN (
            SELECT id FROM sessions 
            WHERE created_at < datetime('now', ?)
        )
    """, (f'-{days} days',))
    conn.commit()

# 方案 2：VACUUM 压缩
def vacuum_database():
    """压缩数据库"""
    conn = get_db()
    conn.execute("VACUUM")
    conn.commit()

# 方案 3：归档旧数据
def archive_old_data():
    """归档旧数据到归档数据库"""
    # 将旧数据移动到归档数据库
    pass
```

### 问题 7.6：数据库连接泄漏

**症状**：数据库连接数持续增长。

**解决方案**：

```python
# 方案 1：使用上下文管理器
from contextlib import contextmanager

@contextmanager
def get_db():
    conn = sqlite3.connect("data/thesisminer.db")
    try:
        yield conn
    finally:
        conn.close()

# 使用
with get_db() as conn:
    conn.execute("SELECT * FROM sessions")

# 方案 2：使用连接池
# 见问题 7.1 的方案 2

# 方案 3：定期检查连接数
def check_connection_count():
    conn = get_db()
    count = conn.execute("SELECT count(*) FROM pragma_database_list").fetchone()[0]
    if count > 10:
        logger.warning(f"数据库连接数过高: {count}")
```

---

## 8. 性能调优类问题

### 问题 8.1：API 响应缓慢

**症状**：API 响应时间超过 5 秒。

**诊断步骤**：

```python
# 添加性能监控
import time
from functools import wraps

def monitor_performance(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start
        if elapsed > 2:
            logger.warning(f"{func.__name__} 耗时 {elapsed:.2f}s")
        return result
    return wrapper
```

**解决方案**：

```python
# 方案 1：添加数据库索引
create_indexes()  # 见问题 7.4

# 方案 2：使用缓存
from functools import lru_cache

@lru_cache(maxsize=100)
def get_config(key: str):
    """缓存配置查询"""
    return db_query(f"SELECT value FROM config WHERE key = '{key}'")

# 方案 3：异步并行
async def get_dashboard_data():
    """并获取仪表盘数据"""
    sessions, proposals, budgets = await asyncio.gather(
        get_sessions(),
        get_proposals(),
        get_budgets(),
    )
    return {sessions, proposals, budgets}

# 方案 4：分页查询
async def list_sessions(page: int = 1, size: int = 20):
    offset = (page - 1) * size
    return await db.execute(
        "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (size, offset)
    )
```

### 问题 8.2：内存使用过高

**症状**：服务器内存使用超过 80%。

**解决方案**：

```python
# 方案 1：限制缓存大小
CACHE_CONFIG = {
    "max_size": 500,
    "max_memory_mb": 100,
}

# 方案 2：及时释放资源
async def generate_proposal(session_id: str):
    session = await get_session(session_id)
    try:
        result = await process(session)
        return result
    finally:
        # 释放大对象
        del session

# 方案 3：使用生成器
async def stream_large_data():
    """流式处理大数据"""
    async for chunk in read_large_file():
        yield process_chunk(chunk)

# 方案 4：监控内存使用
import psutil
import os

def monitor_memory():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024  # MB
    if mem > 500:
        logger.warning(f"内存使用过高: {mem:.1f}MB")
        # 触发垃圾回收
        import gc
        gc.collect()
```

### 问题 8.3：并发处理能力低

**症状**：并发请求超过 10 个时响应变慢。

**解决方案**：

```python
# 方案 1：增加 Uvicorn worker
uvicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker

# 方案 2：使用异步 I/O
async def handle_request(request):
    # 确保所有 I/O 操作都是异步的
    data = await read_database()  # 异步数据库
    result = await call_ai_model(data)  # 异步 AI 调用
    return result

# 方案 3：使用连接池
# 见问题 7.1 的连接池方案

# 方案 4：请求队列
from asyncio import Queue, Semaphore

MAX_CONCURRENT = 20
semaphore = Semaphore(MAX_CONCURRENT)

async def handle_with_limit(request):
    async with semaphore:
        return await process_request(request)
```

### 问题 8.4：AI 模型调用缓慢

**症状**：AI 模型调用超过 60 秒。

**解决方案**：

```python
# 方案 1：使用流式调用
async def stream_model_call(prompt: str):
    """流式调用 AI 模型"""
    response = await client.chat.completions.create(
        model="deepseek-chat-v3",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    async for chunk in response:
        yield chunk.choices[0].delta.content

# 方案 2：使用更快的模型
# deepseek-chat-v3 > gpt-4.1 > deepseek-reasoner（速度排序）

# 方案 3：减少输入长度
def truncate_prompt(prompt: str, max_length: int = 4000) -> str:
    if len(prompt) > max_length:
        return prompt[:max_length] + "..."
    return prompt

# 方案 4：并行调用
async def parallel_agents(prompt: str):
    """并行调用多个 Agent"""
    results = await asyncio.gather(
        call_reasoner(prompt),
        call_mentor(prompt),
        call_searcher(prompt),
    )
    return results
```

### 问题 8.5：前端加载缓慢

**症状**：页面首次加载超过 5 秒。

**解决方案**：

```html
<!-- 方案 1：延迟加载非关键资源 -->
<script defer src="https://d3js.org/d3.v7.min.js"></script>

<!-- 方案 2：预加载关键资源 -->
<link rel="preload" href="/css/styles.css" as="style">

<!-- 方案 3：使用 CDN -->
<script src="https://cdn.tailwindcss.com"></script>

<!-- 方案 4：压缩资源 -->
<!-- 使用 gzip 压缩 -->
```

### 问题 8.6：D3.js 图谱渲染缓慢

**症状**：节点数量超过 100 时图谱渲染卡顿。

**解决方案**：

```javascript
// 方案 1：使用 Canvas 替代 SVG
const canvas = d3.select('#graph').append('canvas')
  .attr('width', width)
  .attr('height', height)

const ctx = canvas.node().getContext('2d')

// 方案 2：节点聚合
function aggregateNodes(nodes, threshold = 100) {
  if (nodes.length <= threshold) return nodes
  // 按类型聚合
  return groupByType(nodes)
}

// 方案 3：虚拟渲染
function renderVisibleNodes(nodes, viewport) {
  return nodes.filter(node => 
    node.x >= viewport.x && node.x <= viewport.x + viewport.width &&
    node.y >= viewport.y && node.y <= viewport.y + viewport.height
  )
}

// 方案 4：Web Worker
const worker = new Worker('graph-worker.js')
worker.postMessage({ nodes, edges })
worker.onmessage = (e) => {
  renderGraph(e.data)
}
```

---

## 9. 日志分析

### 9.1 日志配置

```python
# backend/config.py 中的日志配置
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": "%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "%(asctime)s | %(levelname)s | %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "INFO",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/thesisminer.log",
            "formatter": "detailed",
            "level": "DEBUG",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/error.log",
            "formatter": "detailed",
            "level": "ERROR",
            "maxBytes": 10485760,
            "backupCount": 5,
        },
    },
    "loggers": {
        "thesisminer": {
            "handlers": ["console", "file", "error_file"],
            "level": "DEBUG",
        },
    },
}
```

### 9.2 日志级别使用指南

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| DEBUG | 详细调试信息 | 请求参数、响应内容、变量值 |
| INFO | 正常操作记录 | 会话创建、论题生成、用户登录 |
| WARNING | 异常但可处理 | 缓存未命中、降级操作、重试 |
| ERROR | 错误但不影响系统 | 单个请求失败、Agent 超时 |
| CRITICAL | 严重错误影响系统 | 数据库连接断开、服务崩溃 |

### 9.3 日志分析技巧

```bash
# 查看最近 100 条错误
tail -100 logs/thesisminer.log | grep ERROR

# 按错误码过滤
grep "AGENT_TIMEOUT" logs/thesisminer.log

# 按请求 ID 追踪
grep "req-abc123" logs/thesisminer.log

# 按时间范围过滤
grep "2026-06-19 10:" logs/thesisminer.log

# 统计错误类型
grep ERROR logs/thesisminer.log | awk -F'|' '{print $3}' | sort | uniq -c | sort -rn

# 查看错误上下文
grep -B 2 -A 5 "ERROR" logs/thesisminer.log

# 实时监控错误
tail -f logs/thesisminer.log | grep ERROR
```

### 9.4 日志轮转

```bash
# 使用 logrotate 配置日志轮转
cat > /etc/logrotate.d/thesisminer << EOF
/path/to/thesisminer/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 thesisminer thesisminer
}
EOF
```

---

## 10. 诊断工具集

### 10.1 系统健康检查脚本

```python
#!/usr/bin/env python3
"""ThesisMiner 系统健康检查脚本"""

import sys
import os
import sqlite3
import requests
import psutil

def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    if version >= (3, 10):
        print(f"✅ Python 版本: {version.major}.{version.minor}.{version.micro}")
    else:
        print(f"❌ Python 版本过低: {version.major}.{version.minor}（需要 3.10+）")

def check_dependencies():
    """检查依赖"""
    required = ["fastapi", "uvicorn", "openai", "pydantic"]
    for pkg in required:
        try:
            __import__(pkg)
            print(f"✅ {pkg} 已安装")
        except ImportError:
            print(f"❌ {pkg} 未安装")

def check_database():
    """检查数据库"""
    db_path = "data/thesisminer.db"
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"✅ 数据库正常，共 {len(tables)} 个表")
        conn.close()
    except Exception as e:
        print(f"❌ 数据库错误: {e}")

def check_api_key():
    """检查 API Key"""
    keys = ["OPENAI_API_KEY", "DEEPSEEK_API_KEY"]
    for key in keys:
        value = os.getenv(key)
        if value:
            print(f"✅ {key} 已设置")
        else:
            print(f"⚠️  {key} 未设置")

def check_system_resources():
    """检查系统资源"""
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent

    print(f"📊 CPU 使用率: {cpu}%")
    print(f"📊 内存使用率: {mem}%")
    print(f"📊 磁盘使用率: {disk}%")

    if cpu > 80:
        print("⚠️  CPU 使用率过高")
    if mem > 80:
        print("⚠️  内存使用率过高")
    if disk > 90:
        print("⚠️  磁盘使用率过高")

def check_api_health():
    """检查 API 健康"""
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ API 服务正常")
        else:
            print(f"❌ API 服务异常: {response.status_code}")
    except requests.ConnectionError:
        print("❌ API 服务未启动")
    except Exception as e:
        print(f"❌ API 检查失败: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("ThesisMiner 系统健康检查")
    print("=" * 50)

    check_python_version()
    check_dependencies()
    check_database()
    check_api_key()
    check_system_resources()
    check_api_health()

    print("=" * 50)
```

### 10.2 性能分析工具

```python
# 使用 cProfile 分析性能
import cProfile
import pstats

def profile_function(func, *args, **kwargs):
    """分析函数性能"""
    profiler = cProfile.Profile()
    profiler.enable()
    result = func(*args, **kwargs)
    profiler.disable()

    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # 打印前 20 个最耗时的函数

    return result
```

---

## 11. 附录

### 11.1 常见错误码速查

| 错误码 | 含义 | 参考章节 |
|--------|------|---------|
| HTTP_500 | 服务器内部错误 | 问题 7.1, 8.1 |
| HTTP_502 | 网关错误 | 问题 3.1, 4.3 |
| HTTP_504 | 网关超时 | 问题 3.2, 4.1 |
| AGENT_TIMEOUT | Agent 超时 | 问题 4.1, 4.8 |
| CACHE_MISS | 缓存未命中 | 问题 5.1, 5.2 |
| CONSTRAINT_VIOLATION | 约束违规 | 错误码文档 |

### 11.2 获取帮助

如果本文档无法解决您的问题，可以通过以下渠道获取帮助：

1. **查看日志**：`logs/thesisminer.log` 和 `logs/error.log`
2. **运行健康检查**：`python scripts/health_check.py`
3. **查看 GitHub Issues**：提交 Issue 并附上日志和错误信息
4. **联系维护团队**：附上错误码、请求 ID 和日志片段

### 11.3 提交 Bug 报告

提交 Bug 报告时请包含以下信息：

```
## Bug 描述
简要描述遇到的问题。

## 复现步骤
1. 执行 '...'
2. 点击 '...'
3. 看到 '...'

## 期望行为
描述期望看到的行为。

## 实际行为
描述实际看到的行为。

## 环境信息
- OS: [e.g. Ubuntu 22.04]
- Python: [e.g. 3.11.4]
- ThesisMiner: [e.g. v8.0.0]
- 浏览器: [e.g. Chrome 120]

## 日志
```
粘贴相关日志...
```

## 请求 ID
如果有请求 ID，请提供：req-xxx
```

---

> **文档结束**  
> 本文档涵盖 ThesisMiner v8.0 的 60+ 常见问题的诊断与解决方案。如需了解更多信息，请参阅错误码参考文档和 FAQ 文档。