# ThesisMiner v8.0 测试指南

> 版本：v8.0 | 更新日期：2026-06-19 | 适用范围：所有开发者与 CI 环境

本文档详细说明 ThesisMiner v8.0 的测试体系架构、编写规范、运行方式与覆盖率要求。项目采用分层测试策略，确保多 Agent 架构、五阶段闭环导航流、DeepSeek 缓存优化等核心功能的正确性与稳定性。

---

## 目录

1. [测试体系总览](#1-测试体系总览)
2. [环境准备](#2-环境准备)
3. [测试目录结构](#3-测试目录结构)
4. [单元测试规范](#4-单元测试规范)
5. [集成测试规范](#5-集成测试规范)
6. [端到端测试规范](#6-端到端测试规范)
7. [压力测试规范](#7-压力测试规范)
8. [测试数据与夹具](#8-测试数据与夹具)
9. [Mock 与 AI 调用隔离](#9-mock-与-ai-调用隔离)
10. [运行测试](#10-运行测试)
11. [覆盖率要求](#11-覆盖率要求)
12. [CI 集成](#12-ci-集成)
13. [常见问题排查](#13-常见问题排查)

---

## 1. 测试体系总览

ThesisMiner v8.0 采用经典的测试金字塔模型，自下而上分为四层：

```
            /\
           /  \        压力测试（tests/load/）
          /----\       少量，验证性能与并发
         /      \
        /--------\     端到端测试（tests/e2e/）
       /          \    少量，验证完整用户流程
      /------------\
     /              \  集成测试（tests/integration/）
    /----------------\ 中等，验证模块间协作
   /                  \
  /--------------------\ 单元测试（tests/unit/）
 /                      \大量，验证独立函数与类
```

### 各层职责

| 层级 | 目录 | 数量目标 | 运行速度 | 验证范围 |
|------|------|----------|----------|----------|
| 单元测试 | `tests/unit/` | ≥30 文件，每文件 ≥10 用例 | <30 秒 | 单个函数/类的逻辑正确性 |
| 集成测试 | `tests/integration/` | ≥10 文件 | <2 分钟 | 模块间协作、API 端点、数据库交互 |
| 端到端测试 | `tests/e2e/` | ≥5 文件 | <5 分钟 | 完整用户流程（浏览器自动化） |
| 压力测试 | `tests/load/` | ≥3 文件 | <10 分钟 | 并发、大数据量、性能基线 |

---

## 2. 环境准备

### 安装测试依赖

```bash
pip install -r requirements-dev.txt
```

`requirements-dev.txt` 包含：

- `pytest` >= 8.0：测试框架
- `pytest-asyncio`：异步测试支持
- `pytest-cov`：覆盖率统计
- `pytest-mock`：Mock 工具
- `httpx`：API 测试客户端
- `playwright`：前端 E2E 测试
- `locust`：压力测试
- `ruff`：代码 lint
- `mypy`：类型检查

### 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 配置测试环境变量

创建 `.env.test` 文件：

```env
TESTING=true
DATABASE_URL=sqlite:///./test_thesisminer.db
# 测试环境禁用真实 AI 调用，使用 Mock
AI_CALL_MODE=mock
```

---

## 3. 测试目录结构

```
tests/
├── conftest.py                 # 全局夹具（pytest 配置、数据库初始化）
├── unit/                       # 单元测试
│   ├── test_models_v8.py       # 模型注册表测试
│   ├── test_cache_hit.py       # DeepSeek 缓存命中率测试
│   ├── test_orchestrator.py    # Orchestrator 编排逻辑测试
│   ├── test_conversations.py   # 多对话管理测试
│   ├── test_constraints_v8.py  # 约束工程测试
│   ├── test_state_machine_v8.py# 状态机测试
│   ├── test_citation_parser.py # 引用解析测试
│   ├── test_novelty_checker.py # 新颖性评分测试
│   ├── test_style_normalizer.py# 去 AI 痕迹测试
│   └── ...                     # 其他模块测试
├── integration/                # 集成测试
│   ├── test_five_stage_flow.py # 五阶段完整流程
│   ├── test_multi_agent.py     # 多 Agent 协作
│   ├── test_multi_conversation.py # 多对话切换
│   └── test_api_endpoints.py   # API 端点集成
├── e2e/                        # 端到端测试
│   ├── test_lineage_graph.py   # 谱系图谱交互
│   ├── test_session_ui.py      # 会话管理 UI
│   └── test_generate_flow.py   # 生成流程 UI
├── load/                       # 压力测试
│   ├── test_concurrent_sessions.py # 并发会话
│   ├── test_large_lineage.py   # 大规模谱系图
│   └── test_message_volume.py  # 消息吞吐量
└── fixtures/                   # 测试数据
    ├── sample_proposals.json   # 样本论题
    ├── sample_papers.json      # 样本文献
    ├── sample_responses.json   # 样本 AI 回复（含引用）
    └── sample_lineage.json     # 样本谱系图数据
```

---

## 4. 单元测试规范

### 命名规范

- 文件名：`test_<被测模块>.py`
- 函数名：`test_<被测行为>_<场景>()`
- 使用 `Arrange-Act-Assert`（3A）模式组织用例

### 示例：新颖性评分测试

```python
import pytest
from backend.constraints.novelty_checker import NoveltyChecker

class TestNoveltyChecker:
    """新颖性评分器单元测试。"""

    @pytest.fixture
    def checker(self):
        return NoveltyChecker(weights_config="config/constraints/novelty_weights.yaml")

    def test_high_novelty_passes_threshold(self, checker):
        """高新颖性论题应通过阈值。"""
        # Arrange
        candidate = {
            "title": "基于拓扑数据分析的神经科学认知机制研究",
            "dimensions": {
                "cross_discipline": 92,
                "method_transfer": 85,
                "pain_point_breakthrough": 78,
                "trend_foresight": 88
            },
            "similarity": 0.15
        }
        # Act
        result = checker.evaluate(candidate)
        # Assert
        assert result.total_score >= 60
        assert result.risk_level == "low"
        assert result.passed is True

    def test_low_novelty_blocked(self, checker):
        """低新颖性论题应被阻断。"""
        candidate = {
            "title": "BERT 文本分类研究",
            "dimensions": {
                "cross_discipline": 20,
                "method_transfer": 15,
                "pain_point_breakthrough": 25,
                "trend_foresight": 10
            },
            "similarity": 0.65
        }
        result = checker.evaluate(candidate)
        assert result.total_score < 60
        assert result.risk_level == "high"
        assert result.passed is False

    def test_shortboard_detection(self, checker):
        """单维度低于阈值应标记短板。"""
        candidate = {
            "title": "跨学科方法迁移研究",
            "dimensions": {
                "cross_discipline": 85,
                "method_transfer": 80,
                "pain_point_breakthrough": 25,  # 短板
                "trend_foresight": 70
            },
            "similarity": 0.2
        }
        result = checker.evaluate(candidate)
        assert "pain_point_breakthrough" in result.shortboards
```

### 示例：去 AI 痕迹测试

```python
from backend.constraints.style_normalizer import StyleNormalizer

class TestStyleNormalizer:

    def test_replaces_template_words(self):
        """模板词应被替换。"""
        normalizer = StyleNormalizer("config/constraints/style_rules.yaml")
        text = "首先，本研究具有重要意义。其次，方法有效。最后，结论可靠。"
        result = normalizer.normalize(text)
        assert "首先，" not in result.normalized_text
        assert "其次，" not in result.normalized_text
        assert "最后，" not in result.normalized_text

    def test_ai_trace_score_decreases(self):
        """处理后 AI 痕迹评分应下降。"""
        normalizer = StyleNormalizer()
        text = "综上所述，本研究至关重要，具有重大的理论意义。"
        result = normalizer.normalize(text)
        assert result.ai_trace_score_after < result.ai_trace_score_before
```

---

## 5. 集成测试规范

集成测试验证多个模块协作的正确性，使用真实数据库（内存 SQLite）但 Mock AI 调用。

### 示例：五阶段流程集成测试

```python
import pytest
from httpx import AsyncClient
from backend.main import app

@pytest.mark.asyncio
class TestFiveStageFlow:

    async def test_info_confirmation_gate_blocks(self):
        """信息确权门禁应阻断未确认的请求。"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 发起生成请求
            response = await client.post("/api/conversations/c1/generate", json={
                "user_input": "我想研究大模型方向"
            })
            # 应停留在信息确权阶段，返回文献摘要
            assert response.status_code == 200
            data = response.json()
            assert data["stage"] == "info_confirmation"
            assert len(data["papers"]) > 0
            assert data["requires_confirmation"] is True

    async def test_flow_advances_after_confirmation(self):
        """用户确认后应进入创意阶段。"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/conversations/c1/generate", json={"user_input": "大模型"})
            response = await client.post("/api/conversations/c1/confirm", json={
                "confirmed": True
            })
            assert response.json()["stage"] == "creativity"
```

---

## 6. 端到端测试规范

端到端测试使用 Playwright 模拟真实浏览器操作，验证完整用户交互流程。

### 示例：谱系图谱交互测试

```python
from playwright.sync_api import sync_playwright

class TestLineageGraph:

    def test_graph_renders_and_drags(self):
        """谱系图谱应正确渲染并支持拖拽。"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto("http://localhost:8000/lineage")

            # 验证图谱节点渲染
            nodes = page.query_selector_all(".graph-node")
            assert len(nodes) > 0

            # 验证拖拽功能
            first_node = nodes[0]
            box = first_node.bounding_box()
            page.mouse.move(box["x"] + 10, box["y"] + 10)
            page.mouse.down()
            page.mouse.move(box["x"] + 100, box["y"] + 100)
            page.mouse.up()

            new_box = first_node.bounding_box()
            assert abs(new_box["x"] - box["x"] - 90) < 10

            browser.close()
```

---

## 7. 压力测试规范

压力测试使用 locust 模拟高并发场景，验证系统性能基线。

### 性能基线要求

| 场景 | 指标 | 基线 |
|------|------|------|
| 100 并发会话 | 平均响应时间 | < 2 秒 |
| 1000 条消息写入 | 总耗时 | < 30 秒 |
| 500 节点谱系图渲染 | 首屏时间 | < 3 秒 |
| DeepSeek 连续调用 | 缓存命中率 | ≥ 95% |

### 示例：并发会话压测

```python
from locust import HttpUser, task, between

class ThesisMinerUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def create_session_and_chat(self):
        self.client.post("/api/sessions", json={"title": "压测会话"})
        self.client.post("/api/sessions/s1/conversations", json={"agent_id": "orchestrator"})
```

运行：`locust -f tests/load/test_concurrent_sessions.py --host=http://localhost:8000`

---

## 8. 测试数据与夹具

### 全局夹具（conftest.py）

```python
import pytest
from backend.database import init_db, get_db

@pytest.fixture(scope="function")
def db_session():
    """每个测试函数使用独立的内存数据库。"""
    init_db(url="sqlite:///:memory:")
    db = next(get_db())
    yield db
    db.close()

@pytest.fixture
def sample_proposal():
    """加载样本论题。"""
    import json
    with open("tests/fixtures/sample_proposals.json", encoding="utf-8") as f:
        return json.load(f)[0]
```

### 夹具数据规范

- 所有测试数据存放在 `tests/fixtures/`，使用 JSON 格式
- 样本数据应覆盖正常、边界、异常三类场景
- 不包含真实用户数据与真实 API Key
- AI 回复样本需包含 citations 字段以测试引用解析

---

## 9. Mock 与 AI 调用隔离

测试环境**禁止**调用真实 AI API，所有 AI 调用必须 Mock。

### Mock 策略

```python
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_llm_call():
    """Mock AI 代理层，返回预设响应。"""
    mock_response = {
        "content": "这是 Mock 的 AI 回复",
        "reasoning": "推理过程",
        "citations": [{"url": "https://example.com", "title": "示例"}],
        "cached_tokens": 1500,
        "prompt_tokens": 1600
    }
    with patch("backend.ai.ai_proxy.call_llm", new_callable=AsyncMock) as mock:
        mock.return_value = mock_response
        yield mock
```

### DeepSeek 缓存测试的 Mock

缓存命中率测试需 Mock 返回的 `cached_tokens` 与 `prompt_tokens`，验证 `cache_monitor` 正确计算比率：

```python
def test_cache_hit_rate_calculation(mock_llm_call):
    """连续 10 次调用应达到 95% 缓存命中率。"""
    for i in range(10):
        mock_llm_call.return_value["cached_tokens"] = 1520
        mock_llm_call.return_value["prompt_tokens"] = 1600
        call_llm(...)
    rate = cache_monitor.get_average_hit_rate()
    assert rate >= 0.95
```

---

## 10. 运行测试

### 运行全部测试

```bash
pytest tests/ -v
```

### 按层级运行

```bash
# 仅单元测试
pytest tests/unit/ -v

# 仅集成测试
pytest tests/integration/ -v

# 仅端到端测试（需先启动服务器）
pytest tests/e2e/ -v

# 仅压力测试
pytest tests/load/ -v
```

### 按标记运行

```bash
pytest -m "not slow"          # 跳过慢测试
pytest -m "asyncio"           # 仅异步测试
pytest -m "critical"          # 仅关键路径测试
```

### 生成覆盖率报告

```bash
pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing
```

HTML 报告生成在 `htmlcov/index.html`。

### 并行执行

```bash
pytest tests/unit/ -n auto    # 使用 pytest-xdist 并行
```

---

## 11. 覆盖率要求

### 总体要求

| 模块 | 覆盖率要求 |
|------|------------|
| `backend/agents/` | ≥ 90% |
| `backend/constraints/` | ≥ 90% |
| `backend/orchestration/` | ≥ 90% |
| `backend/sessions/` | ≥ 85% |
| `backend/ai/` | ≥ 85% |
| `backend/routes/` | ≥ 80% |
| 新增代码 | ≥ 80% |
| 全项目平均 | ≥ 85% |

### 覆盖率豁免

以下代码可申请覆盖率豁免（在 PR 中说明）：

- 纯数据模型定义（`dataclass`、`Pydantic` 模型）
- 日志与监控代码
- 第三方适配层的异常分支
- 不可达的防御性代码

---

## 12. CI 集成

GitHub Actions 配置（`.github/workflows/ci.yml`）在每次 PR 与推送时自动运行：

1. **Lint 检查**：`ruff check` + `mypy`
2. **单元测试**：`pytest tests/unit/`
3. **集成测试**：`pytest tests/integration/`
4. **覆盖率检查**：低于阈值则失败
5. **E2E 测试**：仅 `main` 与 `develop` 分支触发

CI 失败的 PR 不可合并。如 CI 因环境问题失败（非代码问题），可在 PR 中说明并申请重跑。

---

## 13. 常见问题排查

### 测试数据库冲突

**问题**：测试间数据库状态污染。
**解决**：确保每个测试使用 `function` 作用域的 `db_session` 夹具，每次测试重建内存数据库。

### 异步测试报错

**问题**：`RuntimeError: asyncio.run() cannot be called from a running event loop`。
**解决**：使用 `@pytest.mark.asyncio` 装饰器，并在 `pytest.ini` 配置 `asyncio_mode = auto`。

### Playwright 超时

**问题**：E2E 测试浏览器启动超时。
**解决**：确认已执行 `playwright install chromium`；CI 环境使用 `playwright install --with-deps`。

### Mock 未生效

**问题**：测试仍发起了真实 AI 调用。
**解决**：检查 Mock 的 patch 路径是否正确（应 patch 调用方导入的位置，而非定义位置）。

### 覆盖率统计遗漏

**问题**：覆盖率报告显示部分文件未覆盖。
**解决**：确认 `--cov=backend` 路径正确；动态导入的模块需在测试中显式 import 触发加载。

---

如遇本指南未覆盖的测试问题，请提交 Issue 并标注 `question` 标签，维护团队将协助排查。
