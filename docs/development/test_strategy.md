# ThesisMiner v8.0 测试策略与质量保证

> 本文档详细描述 ThesisMiner v8.0 项目的测试策略、测试金字塔、测试工具链、测试覆盖率目标、测试最佳实践以及质量保证流程。

## 目录

- [1. 测试哲学](#1-测试哲学)
- [2. 测试金字塔](#2-测试金字塔)
- [3. 测试目录结构](#3-测试目录结构)
- [4. 单元测试](#4-单元测试)
- [5. 集成测试](#5-集成测试)
- [6. 端到端测试](#6-端到端测试)
- [7. 性能测试](#7-性能测试)
- [8. 负载测试](#8-负载测试)
- [9. 压力测试](#9-压力测试)
- [10. 冒烟测试](#10-冒烟测试)
- [11. 回归测试](#11-回归测试)
- [12. 测试工具链](#12-测试工具链)
- [13. 测试覆盖率](#13-测试覆盖率)
- [14. 测试数据管理](#14-测试数据管理)
- [15. Mock 与 Stub](#15-mock-与-stub)
- [16. 测试夹具](#16-测试夹具)
- [17. 参数化测试](#17-参数化测试)
- [18. 异步测试](#18-异步测试)
- [19. 测试并行化](#19-测试并行化)
- [20. 测试报告](#20-测试报告)
- [21. CI/CD 集成](#21-cicd-集成)
- [22. 质量门禁](#22-质量门禁)
- [23. 测试最佳实践](#23-测试最佳实践)
- [24. 测试反模式](#24-测试反模式)
- [25. 质量指标](#25-质量指标)
- [26. 测试维护](#26-测试维护)
- [27. 测试文档](#27-测试文档)
- [28. 测试培训](#28-测试培训)
- [29. 测试自动化](#29-测试自动化)
- [30. 附录](#30-附录)

---

## 1. 测试哲学

### 1.1 测试目标

ThesisMiner v8.0 的测试体系围绕以下核心目标构建：

1. **正确性保证**：确保每个模块、每个功能、每条路径都按预期工作
2. **回归防护**：在代码变更时及时发现引入的回归缺陷
3. **设计反馈**：通过测试驱动设计改进，提升代码可测试性与可维护性
4. **文档作用**：测试用例作为活文档，描述系统的预期行为
5. **信心支撑**：为持续交付提供信心，支持快速迭代与安全发布
6. **性能基线**：建立性能基线，监控性能退化
7. **安全验证**：验证安全机制有效性，防止安全漏洞

### 1.2 测试原则

#### 1.2.1 FAST 原则

- **Fast（快速）**：单元测试应在秒级完成，集成测试在分钟级完成
- **Accessible（可访问）**：测试应易于理解、易于运行、易于维护
- **Standard（标准化）**：遵循统一的测试规范与命名约定
- **Thorough（全面）**：覆盖正常路径、边界条件、异常场景

#### 1.2.2 FIRST 原则

- **Fast**：测试执行速度快
- **Independent**：测试之间相互独立，无依赖关系
- **Repeatable**：测试可重复执行，结果稳定
- **Self-Validating**：测试自动判断通过/失败，无需人工检查
- **Timely**：测试及时编写，与实现代码同步或先行

#### 1.2.3 AAA 模式

所有测试用例遵循 Arrange-Act-Assert 模式：

```python
def test_conversation_isolation():
    # Arrange - 准备
    manager = ConversationManager()
    conv1 = manager.create_conversation(session_id="s1", title="对话1")
    conv2 = manager.create_conversation(session_id="s1", title="对话2")
    
    # Act - 执行
    manager.add_message(conv1.id, agent_id="reasoner", role="user", content="你好")
    manager.add_message(conv2.id, agent_id="reasoner", role="user", content="你好")
    
    # Assert - 断言
    messages1 = manager.get_messages(conv1.id)
    messages2 = manager.get_messages(conv2.id)
    assert len(messages1) == 1
    assert len(messages2) == 1
    assert messages1[0].content == "你好"
    assert messages2[0].content == "你好"
    assert messages1[0].id != messages2[0].id
```

### 1.3 测试思维

#### 1.3.1 防御性测试

不仅要测试"应该工作的"，更要测试"不应该发生的"：

```python
def test_orchestrator_rejects_invalid_stage_transition():
    """测试编排器拒绝非法阶段转移"""
    orchestrator = OrchestratorAgent()
    # 尝试从信息确权直接跳到生成阶段（非法）
    with pytest.raises(InvalidTransitionError):
        orchestrator.transition(Stage.INFO_CONFIRM, Event.SKIP_TO_GENERATION)
```

#### 1.3.2 边界值测试

针对边界条件进行重点测试：

```python
@pytest.mark.parametrize("title_length,expected", [
    (0, False),       # 空标题
    (1, False),       # 过短
    (5, False),       # 仍过短
    (10, True),       # 最小有效长度
    (20, True),       # 正常
    (50, True),       # 较长
    (100, True),      # 最大有效长度
    (101, False),     # 过长
    (200, False),     # 远超上限
])
def test_title_length_validation(title_length, expected):
    title = "A" * title_length
    result = validate_title(title)
    assert result.is_valid == expected
```

#### 1.3.3 等价类划分

将输入空间划分为等价类，每类取代表值：

```python
# 学科代码等价类
VALID_DISCIPLINES = ["0812", "0701", "0301"]  # 有效等价类
INVALID_DISCIPLINES = ["", "abc", "12345", None]  # 无效等价类
```

---

## 2. 测试金字塔

### 2.1 金字塔结构

```
                    /\
                   /  \
                  / E2E\              <- 少量（~5%）
                 /------\
                /        \
               / Integration\         <- 适中（~20%）
              /------------\
             /              \
            /    Unit Tests   \      <- 大量（~75%）
           /--------------------\
```

### 2.2 各层比例与数量

| 测试层级 | 比例 | 目标数量 | 执行时间 | 成本 |
|---------|------|---------|---------|------|
| 单元测试 | 75% | ≥500 | < 30秒 | 低 |
| 集成测试 | 20% | ≥100 | < 5分钟 | 中 |
| E2E测试 | 5% | ≥30 | < 30分钟 | 高 |
| **合计** | 100% | ≥630 | - | - |

### 2.3 金字塔倒置问题

避免"冰淇淋蛋卷"反模式：

```
    反模式（避免）：              健康模式：
       /\
      /  \                       /\
     /----\                     /  \
    /      \                   /----\
   /--------\                 /      \
  /          \               /--------\
 /    E2E     \             /          \
/--------------\           /   Unit     \
```

### 2.4 各层职责

#### 2.4.1 单元测试层

- **测试对象**：单个函数、方法、类
- **依赖处理**：所有外部依赖必须 Mock
- **执行速度**：毫秒级
- **覆盖率目标**：≥90% 行覆盖率
- **示例**：

```python
def test_citation_parser_extracts_markdown_links():
    parser = CitationParser()
    content = "参见 [Google](https://google.com) 获取更多信息"
    citations = parser.parse(content)
    assert len(citations) == 1
    assert citations[0].url == "https://google.com"
    assert citations[0].text == "Google"
```

#### 2.4.2 集成测试层

- **测试对象**：多个模块协作、数据库交互、API端点
- **依赖处理**：使用真实数据库（测试库）、Mock 外部 API
- **执行速度**：秒级
- **覆盖率目标**：≥70% 关键路径
- **示例**：

```python
def test_conversation_persistence_integration():
    """测试对话持久化完整流程"""
    manager = ConversationManager(db_path=":memory:")
    conv = manager.create_conversation(session_id="s1", title="测试")
    manager.add_message(conv.id, agent_id="reasoner", role="user", content="你好")
    
    # 重新加载验证持久化
    manager2 = ConversationManager(db_path=manager.db_path)
    messages = manager2.get_messages(conv.id)
    assert len(messages) == 1
    assert messages[0].content == "你好"
```

#### 2.4.3 E2E测试层

- **测试对象**：完整用户旅程、前端+后端+数据库
- **依赖处理**：使用真实环境或接近真实的测试环境
- **执行速度**：分钟级
- **覆盖率目标**：≥80% 核心用户场景
- **示例**：

```python
@pytest.mark.asyncio
async def test_full_five_stage_journey(launch_app):
    """测试完整五阶段用户旅程"""
    async with launch_app() as client:
        # 阶段1：信息确权
        response = await client.post("/api/sessions", json={"discipline": "计算机科学"})
        session_id = response.json()["id"]
        
        response = await client.post(f"/api/sessions/{session_id}/confirm")
        assert response.status_code == 200
        
        # 阶段2：创意生成
        response = await client.post(f"/api/sessions/{session_id}/generate")
        candidates = response.json()["candidates"]
        assert len(candidates) > 0
```

---

## 3. 测试目录结构

### 3.1 目录组织

```
tests/
├── __init__.py
├── conftest.py                    # 全局夹具
├── unit/                          # 单元测试
│   ├── __init__.py
│   ├── conftest.py                # 单元测试夹具
│   ├── test_agents/               # Agent 模块测试
│   │   ├── test_base_agent.py
│   │   ├── test_orchestrator.py
│   │   ├── test_reasoner.py
│   │   ├── test_critic.py
│   │   ├── test_mentor.py
│   │   ├── test_writer.py
│   │   └── test_searcher.py
│   ├── test_sessions/             # 会话模块测试
│   │   ├── test_conversation_manager.py
│   │   ├── test_session_manager.py
│   │   └── test_context_manager.py
│   ├── test_constraints/          # 约束模块测试
│   │   ├── test_stage_gate.py
│   │   ├── test_hard_rules.py
│   │   ├── test_novelty_checker.py
│   │   ├── test_style_normalizer.py
│   │   ├── test_multi_granularity.py
│   │   └── test_deep_assist.py
│   ├── test_ai/                   # AI 模块测试
│   │   ├── test_ai_proxy.py
│   │   ├── test_prompts.py
│   │   ├── test_prompt_cache.py
│   │   ├── test_cache_monitor.py
│   │   ├── test_citation_parser.py
│   │   ├── test_response_parser.py
│   │   └── test_streaming.py
│   ├── test_analytics/            # 分析模块测试
│   │   ├── test_metrics_collector.py
│   │   ├── test_performance_monitor.py
│   │   └── test_usage_tracker.py
│   ├── test_ml/                   # 机器学习模块测试
│   │   ├── test_text_processor.py
│   │   ├── test_embedding_engine.py
│   │   └── test_similarity_scorer.py
│   ├── test_export/               # 导出模块测试
│   │   ├── test_document_exporter.py
│   │   ├── test_report_generator.py
│   │   └── test_citation_formatter.py
│   ├── test_knowledge/            # 知识库模块测试
│   │   ├── test_knowledge_base.py
│   │   ├── test_discipline_taxonomy.py
│   │   └── test_method_library.py
│   ├── test_validation/           # 验证模块测试
│   │   ├── test_thesis_validator.py
│   │   ├── test_plagiarism_detector.py
│   │   └── test_quality_assessor.py
│   ├── test_routing/              # 路由模块测试
│   │   └── test_model_router.py
│   ├── test_integrity/            # 诚信模块测试
│   │   ├── test_academic_integrity.py
│   │   ├── test_citation_verifier.py
│   │   └── test_data_authenticator.py
│   ├── test_optimization/         # 优化模块测试
│   │   ├── test_cache_optimizer.py
│   │   ├── test_query_optimizer.py
│   │   └── test_resource_manager.py
│   ├── test_nlp/                  # NLP 模块测试
│   │   ├── test_chinese_processor.py
│   │   ├── test_academic_parser.py
│   │   └── test_terminology_extractor.py
│   ├── test_monitoring/           # 监控模块测试
│   │   ├── test_health_checker.py
│   │   ├── test_alert_manager.py
│   │   └── test_audit_logger.py
│   ├── test_planning/             # 规划模块测试
│   │   ├── test_research_planner.py
│   │   ├── test_timeline_generator.py
│   │   └── test_milestone_tracker.py
│   ├── test_reasoning/            # 推理模块测试
│   │   ├── test_logical_reasoner.py
│   │   ├── test_argument_analyzer.py
│   │   └── test_hypothesis_tester.py
│   └── test_utils/                # 工具模块测试
│       ├── test_logger.py
│       ├── test_validators.py
│       ├── test_helpers.py
│       ├── test_cache.py
│       └── test_security.py
├── integration/                   # 集成测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_five_stage_flow.py    # 五阶段流程集成
│   ├── test_multi_agent_collaboration.py  # 多Agent协作
│   ├── test_multi_conversation.py # 多对话管理
│   ├── test_citation_pipeline.py  # 引用处理流水线
│   ├── test_cache_optimization.py # 缓存优化
│   ├── test_api_endpoints.py      # API端点集成
│   └── test_full_pipeline.py      # 完整流水线
├── e2e/                           # 端到端测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_full_user_journey.py  # 完整用户旅程
│   ├── test_frontend_pages.py     # 前端页面
│   ├── test_lineage_graph.py      # 谱系图谱
│   ├── test_sessions_ui.py        # 会话UI
│   └── test_generate_ui.py        # 生成UI
├── load/                          # 负载测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_concurrent_sessions.py # 并发会话
│   ├── test_message_volume.py     # 消息量
│   ├── test_lineage_graph_performance.py  # 谱系图性能
│   └── test_cache_performance.py  # 缓存性能
├── fixtures/                      # 测试夹具数据
│   ├── __init__.py
│   ├── sample_theses.py           # 样本论题
│   ├── sample_papers.py           # 样本文献
│   ├── sample_responses.py        # 样本响应
│   ├── sample_lineage.py          # 样本谱系
│   ├── sample_conversations.py    # 样本对话
│   └── sample_budgets.py          # 样本预算
└── snapshots/                     # 快照测试
    ├── __init__.py
    └── README.md
```

### 3.2 命名规范

#### 3.2.1 文件命名

- 测试文件：`test_<模块名>.py`（如 `test_orchestrator.py`）
- 夹具文件：`conftest.py`（pytest 自动发现）
- 数据文件：`sample_<类型>.py`（如 `sample_theses.py`）

#### 3.2.2 测试函数命名

遵循 `test_<被测方法>_<场景>_<预期>` 模式：

```python
def test_create_conversation_with_valid_input_returns_conversation():
    ...

def test_create_conversation_with_empty_title_raises_error():
    ...

def test_add_message_to_nonexistent_conversation_raises_not_found():
    ...
```

#### 3.2.3 测试类命名

```python
class TestConversationManager:
    """ConversationManager 的测试套件"""
    
    class TestCreateConversation:
        """create_conversation 方法的测试"""
        
        def test_with_valid_input(self):
            ...
        
        def test_with_empty_title(self):
            ...
```

---

## 4. 单元测试

### 4.1 单元测试规范

#### 4.1.1 一个测试只验证一个行为

```python
# 好：一个测试一个断言主题
def test_title_validation_rejects_empty_string():
    result = validate_title("")
    assert not result.is_valid
    assert "标题不能为空" in result.errors

# 差：一个测试多个不相关断言
def test_title_validation():
    assert validate_title("").is_valid == False
    assert validate_title("A" * 10).is_valid == True
    assert validate_title("A" * 200).is_valid == False
    # ... 混在一起难以定位失败
```

#### 4.1.2 测试名称表达意图

```python
# 好：名称描述意图
def test_orchestrator_blocks_transition_from_info_confirm_to_generation():
    ...

# 差：名称模糊
def test_transition1():
    ...
```

#### 4.1.3 避免测试逻辑分支

```python
# 差：测试内有逻辑
def test_citation_parser():
    parser = CitationParser()
    test_cases = [...]
    for case in test_cases:
        if case["type"] == "url":
            result = parser.parse_url(case["input"])
        elif case["type"] == "markdown":
            result = parser.parse_markdown(case["input"])
        assert result == case["expected"]

# 好：使用参数化
@pytest.mark.parametrize("case", test_cases)
def test_citation_parser(case):
    parser = CitationParser()
    result = parser.parse(case["input"])
    assert result == case["expected"]
```

### 4.2 单元测试示例

#### 4.2.1 Agent 单元测试

```python
class TestReasonerAgent:
    """ReasonerAgent 单元测试"""
    
    @pytest.fixture
    def agent(self):
        return ReasonerAgent(model_id="deepseek-r2")
    
    @pytest.fixture
    def mock_llm(self):
        with patch("backend.agents.reasoner.call_llm") as mock:
            mock.return_value = {
                "content": "候选论题1：基于Transformer的...",
                "reasoning": "分析过程...",
                "token_usage": {"prompt": 100, "completion": 50}
            }
            yield mock
    
    @pytest.mark.asyncio
    async def test_run_returns_agent_result(self, agent, mock_llm):
        result = await agent.run({"discipline": "计算机科学", "topic": "深度学习"})
        assert isinstance(result, AgentResult)
        assert result.success is True
        assert "候选论题" in result.content
    
    @pytest.mark.asyncio
    async def test_run_maintains_independent_context(self, agent, mock_llm):
        await agent.run({"discipline": "计算机科学"})
        assert len(agent.context.messages) == 2  # user + assistant
        
        # 另一个 Agent 实例不应受影响
        agent2 = ReasonerAgent(model_id="deepseek-r2")
        assert len(agent2.context.messages) == 0
```

#### 4.2.2 约束模块单元测试

```python
class TestNoveltyChecker:
    """NoveltyChecker 单元测试"""
    
    @pytest.fixture
    def checker(self):
        return NoveltyChecker()
    
    def test_cross_discipline_score_high_for_interdisciplinary(self, checker):
        topic = "基于深度学习的古诗风格识别"
        result = checker.score_cross_discipline(topic, ["计算机科学", "中国文学"])
        assert result.score >= 70
        assert "跨学科" in result.description
    
    def test_method_transfer_score_for_known_pattern(self, checker):
        topic = "将BERT迁移到蛋白质结构预测"
        result = checker.score_method_transfer(topic)
        assert result.score >= 60
        assert "方法迁移" in result.description
```

---

## 5. 集成测试

### 5.1 集成测试策略

#### 5.1.1 数据库集成测试

```python
class TestConversationPersistence:
    """对话持久化集成测试"""
    
    @pytest.fixture
    def db(self, tmp_path):
        db_path = tmp_path / "test.db"
        init_database(str(db_path))
        yield str(db_path)
    
    def test_conversation_survives_reconnection(self, db):
        manager1 = ConversationManager(db_path=db)
        conv = manager1.create_conversation(session_id="s1", title="测试")
        manager1.add_message(conv.id, agent_id="reasoner", role="user", content="你好")
        
        # 模拟应用重启
        manager2 = ConversationManager(db_path=db)
        messages = manager2.get_messages(conv.id)
        assert len(messages) == 1
        assert messages[0].content == "你好"
```

#### 5.1.2 API 集成测试

```python
class TestConversationAPI:
    """对话 API 集成测试"""
    
    @pytest.fixture
    def client(self):
        from main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    
    def test_create_and_retrieve_conversation(self, client):
        # 创建
        response = client.post("/api/sessions/s1/conversations", json={
            "title": "测试对话",
            "agent_id": "orchestrator"
        })
        assert response.status_code == 201
        conv_id = response.json()["id"]
        
        # 检索
        response = client.get(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "测试对话"
```

### 5.2 多模块协作测试

```python
class TestFiveStageFlow:
    """五阶段流程集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_flow_with_mocked_llm(self, mock_llm_service):
        orchestrator = OrchestratorAgent()
        
        # 阶段1：信息确权
        result = await orchestrator.orchestrate(
            user_input="我想研究深度学习在教育中的应用",
            conversation_id="conv1"
        )
        stage1_output = await result.__anext__()
        assert stage1_output.stage == Stage.INFO_CONFIRM
        assert len(stage1_output.papers) > 0
        
        # 用户确认
        await orchestrator.confirm_info()
        
        # 阶段2：创意
        stage2_output = await result.__anext__()
        assert stage2_output.stage == Stage.CREATIVITY
        assert len(stage2_output.candidates) > 0
```

---

## 6. 端到端测试

### 6.1 E2E 测试框架

使用 Playwright 进行前端 E2E 测试：

```python
# tests/e2e/test_sessions_ui.py
from playwright.sync_api import Page, expect

class TestSessionsUI:
    """会话管理 UI 端到端测试"""
    
    def test_create_and_switch_conversations(self, page: Page, base_url: str):
        page.goto(f"{base_url}/sessions.html")
        
        # 创建第一个对话
        page.click("button:has-text('新建对话')")
        page.fill("input[placeholder='对话标题']", "对话1")
        page.click("button:has-text('确认')")
        
        # 创建第二个对话
        page.click("button:has-text('新建对话')")
        page.fill("input[placeholder='对话标题']", "对话2")
        page.click("button:has-text('确认')")
        
        # 验证两个 Tab 存在
        expect(page.locator(".conversation-tab:has-text('对话1')")).to_be_visible()
        expect(page.locator(".conversation-tab:has-text('对话2')")).to_be_visible()
        
        # 切换到对话1
        page.click(".conversation-tab:has-text('对话1')")
        page.fill("textarea.message-input", "你好")
        page.click("button:has-text('发送')")
        
        # 切换到对话2，验证上下文隔离
        page.click(".conversation-tab:has-text('对话2')")
        expect(page.locator(".message-list")).not_to_contain_text("你好")
```

### 6.2 谱系图谱 E2E 测试

```python
class TestLineageGraph:
    """谱系图谱端到端测试"""
    
    def test_graph_renders_nodes(self, page: Page, base_url: str):
        page.goto(f"{base_url}/lineage.html")
        page.wait_for_selector("svg.lineage-graph")
        
        # 验证节点渲染
        nodes = page.locator("g.node")
        expect(nodes).to_have_count(10)
        
        # 验证边渲染
        edges = page.locator("line.link")
        expect(edges).to_have_count(15)
    
    def test_node_drag_updates_position(self, page: Page, base_url: str):
        page.goto(f"{base_url}/lineage.html")
        page.wait_for_selector("svg.lineage-graph")
        
        node = page.locator("g.node").first
        initial_transform = node.get_attribute("transform")
        
        # 拖拽节点
        node.drag_to(page.locator("svg.lineage-graph"), target_position={"x": 200, "y": 200})
        
        # 验证位置变化
        new_transform = node.get_attribute("transform")
        assert new_transform != initial_transform
```

---

## 7. 性能测试

### 7.1 性能基准测试

```python
# tests/load/test_cache_performance.py
import time
import pytest

class TestCachePerformance:
    """缓存性能测试"""
    
    def test_cache_lookup_under_1ms(self):
        """缓存查询应在 1ms 内完成"""
        cache = CacheOptimizer(max_size=10000)
        for i in range(10000):
            cache.set(f"key_{i}", f"value_{i}")
        
        start = time.perf_counter()
        cache.get("key_5000")
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert elapsed_ms < 1.0, f"缓存查询耗时 {elapsed_ms:.3f}ms，超过 1ms 阈值"
    
    def test_cache_hit_rate_above_95_percent(self):
        """DeepSeek 缓存命中率应 ≥95%"""
        monitor = CacheMonitor()
        for _ in range(100):
            monitor.record_cache_hit(model="deepseek-v3.2", cached_tokens=800, prompt_tokens=1000)
        
        stats = monitor.get_stats()
        assert stats["hit_rate"] >= 0.95
```

### 7.2 响应时间测试

```python
class TestAPIResponseTime:
    """API 响应时间测试"""
    
    @pytest.fixture
    def client(self):
        from main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    
    def test_sessions_list_under_200ms(self, client):
        start = time.perf_counter()
        response = client.get("/api/sessions")
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert response.status_code == 200
        assert elapsed_ms < 200, f"会话列表响应耗时 {elapsed_ms:.1f}ms，超过 200ms"
```

---

## 8. 负载测试

### 8.1 并发会话测试

```python
# tests/load/test_concurrent_sessions.py
import asyncio
import pytest

class TestConcurrentSessions:
    """并发会话负载测试"""
    
    @pytest.mark.asyncio
    async def test_100_concurrent_sessions(self, async_client):
        """100 个并发会话创建"""
        async def create_session(i):
            response = await async_client.post("/api/sessions", json={
                "title": f"并发会话_{i}",
                "discipline": "计算机科学"
            })
            return response.status_code
        
        tasks = [create_session(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r == 201)
        assert success_count >= 95, f"仅 {success_count}/100 个会话创建成功"
```

### 8.2 消息量测试

```python
class TestMessageVolume:
    """消息量负载测试"""
    
    @pytest.mark.asyncio
    async def test_1000_messages_per_conversation(self, async_client):
        """单对话 1000 条消息"""
        # 创建对话
        response = await async_client.post("/api/sessions/s1/conversations", json={
            "title": "压力测试"
        })
        conv_id = response.json()["id"]
        
        # 发送 1000 条消息
        for i in range(1000):
            await async_client.post(f"/api/conversations/{conv_id}/messages", json={
                "role": "user",
                "content": f"消息_{i}",
                "agent_id": "orchestrator"
            })
        
        # 验证消息数量
        response = await async_client.get(f"/api/conversations/{conv_id}/messages?limit=2000")
        assert len(response.json()) == 1000
```

---

## 9. 压力测试

### 9.1 渐进式压力测试

```python
class TestProgressiveLoad:
    """渐进式压力测试"""
    
    @pytest.mark.parametrize("concurrent_users", [10, 50, 100, 200, 500])
    @pytest.mark.asyncio
    async def test_progressive_load(self, async_client, concurrent_users):
        """渐进增加并发用户"""
        async def user_journey(i):
            # 创建会话
            r = await async_client.post("/api/sessions", json={"title": f"user_{i}"})
            if r.status_code != 201:
                return False
            
            # 发送消息
            session_id = r.json()["id"]
            r = await async_client.post(f"/api/sessions/{session_id}/messages", json={
                "content": "测试消息",
                "role": "user"
            })
            return r.status_code == 201
        
        tasks = [user_journey(i) for i in range(concurrent_users)]
        results = await asyncio.gather(*tasks)
        
        success_rate = sum(1 for r in results if r) / concurrent_users
        # 至少 90% 成功率
        assert success_rate >= 0.9
```

---

## 10. 冒烟测试

### 10.1 部署后冒烟测试

```python
# tests/e2e/test_smoke.py
class TestSmokeTest:
    """部署后冒烟测试"""
    
    def test_health_endpoint(self, client):
        """健康检查端点"""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_agents_endpoint(self, client):
        """Agent 列表端点"""
        response = client.get("/api/agents")
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) >= 6  # 至少6个Agent
    
    def test_models_endpoint(self, client):
        """模型列表端点"""
        response = client.get("/api/models")
        assert response.status_code == 200
        models = response.json()
        assert len(models) >= 10  # 至少10个模型
```

---

## 11. 回归测试

### 11.1 回归测试套件

```python
class TestRegression:
    """回归测试套件"""
    
    def test_bug_123_conversation_title_unicode(self, client):
        """回归：Bug #123 - 对话标题不支持 Unicode"""
        response = client.post("/api/sessions/s1/conversations", json={
            "title": "深度学习研究 🎓"
        })
        assert response.status_code == 201
        assert response.json()["title"] == "深度学习研究 🎓"
    
    def test_bug_456_cache_hit_rate_calculation(self):
        """回归：Bug #456 - 缓存命中率计算错误"""
        monitor = CacheMonitor()
        monitor.record_cache_hit("deepseek-v3.2", cached_tokens=500, prompt_tokens=1000)
        monitor.record_cache_hit("deepseek-v3.2", cached_tokens=800, prompt_tokens=1000)
        
        stats = monitor.get_stats()
        # 平均命中率应为 (50% + 80%) / 2 = 65%
        assert abs(stats["hit_rate"] - 0.65) < 0.001
```

---

## 12. 测试工具链

### 12.1 工具链概览

| 工具 | 用途 | 配置文件 |
|------|------|---------|
| pytest | 测试框架 | pytest.ini |
| pytest-asyncio | 异步测试 | pytest.ini |
| pytest-cov | 覆盖率 | .coveragerc |
| pytest-xdist | 并行执行 | pytest.ini |
| pytest-mock | Mock | - |
| pytest-benchmark | 基准测试 | - |
| responses | HTTP Mock | - |
| freezegun | 时间 Mock | - |
| playwright | E2E测试 | playwright.config.ts |
| locust | 负载测试 | locustfile.py |

### 12.2 pytest 配置

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = 
    -v
    --strict-markers
    --tb=short
    --cov=backend
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
    --cov-fail-under=80
    -n auto
markers =
    slow: 标记慢测试
    integration: 集成测试
    e2e: 端到端测试
    load: 负载测试
    unit: 单元测试
```

### 12.3 覆盖率配置

```ini
# .coveragerc
[run]
source = backend
omit = 
    backend/__pycache__/*
    backend/*/tests/*
    */__init__.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod

[html]
directory = htmlcov
```

---

## 13. 测试覆盖率

### 13.1 覆盖率目标

| 模块 | 行覆盖率 | 分支覆盖率 | 函数覆盖率 |
|------|---------|----------|----------|
| backend/agents | ≥90% | ≥85% | ≥95% |
| backend/sessions | ≥95% | ≥90% | ≥95% |
| backend/constraints | ≥95% | ≥90% | ≥95% |
| backend/ai | ≥85% | ≥80% | ≥90% |
| backend/orchestration | ≥90% | ≥85% | ≥95% |
| backend/analytics | ≥80% | ≥75% | ≥85% |
| backend/ml | ≥80% | ≥75% | ≥85% |
| backend/export | ≥85% | ≥80% | ≥90% |
| backend/knowledge | ≥85% | ≥80% | ≥90% |
| backend/validation | ≥90% | ≥85% | ≥95% |
| backend/routing | ≥85% | ≥80% | ≥90% |
| backend/integrity | ≥85% | ≥80% | ≥90% |
| backend/optimization | ≥80% | ≥75% | ≥85% |
| backend/nlp | ≥80% | ≥75% | ≥85% |
| backend/monitoring | ≥85% | ≥80% | ≥90% |
| backend/planning | ≥85% | ≥80% | ≥90% |
| backend/reasoning | ≥85% | ≥80% | ≥90% |
| backend/utils | ≥90% | ≥85% | ≥95% |
| **总体** | **≥85%** | **≥80%** | **≥90%** |

### 13.2 覆盖率报告

```bash
# 生成覆盖率报告
pytest --cov=backend --cov-report=html --cov-report=xml

# 查看报告
# HTML: htmlcov/index.html
# XML: coverage.xml（用于 CI 集成）
```

---

## 14. 测试数据管理

### 14.1 测试夹具数据

```python
# tests/fixtures/sample_theses.py
"""样本论题数据"""

SAMPLE_THESES = [
    {
        "title": "基于深度学习的文本分类研究",
        "discipline": "0812",
        "discipline_name": "计算机科学与技术",
        "advisor": "张教授",
        "degree": "硕士",
        "keywords": ["深度学习", "文本分类", "神经网络"],
        "abstract": "本文研究基于深度学习的文本分类方法..."
    },
    # ... 更多样本
]

SAMPLE_PAPERS = [
    {
        "title": "Attention Is All You Need",
        "authors": ["Vaswani, A.", "Shazeer, N."],
        "year": 2017,
        "venue": "NeurIPS",
        "doi": "10.5555/3295222.3295349"
    },
    # ...
]
```

### 14.2 数据生成器

```python
# tests/fixtures/generators.py
import factory
import faker

fake = faker.Faker("zh_CN")

class ConversationFactory(factory.Factory):
    class Meta:
        model = dict
    
    title = factory.LazyFunction(lambda: f"测试对话_{fake.uuid4()[:8]}")
    agent_id = "orchestrator"
    status = "active"

class MessageFactory(factory.Factory):
    class Meta:
        model = dict
    
    role = "user"
    content = factory.LazyFunction(lambda: fake.sentence())
    agent_id = "orchestrator"
```

---

## 15. Mock 与 Stub

### 15.1 Mock LLM 调用

```python
@pytest.fixture
def mock_llm():
    """Mock LLM 调用"""
    with patch("backend.ai.ai_proxy.call_llm") as mock:
        mock.return_value = {
            "content": "这是模拟的 LLM 响应",
            "reasoning": "模拟的推理过程",
            "token_usage": {
                "prompt": 100,
                "completion": 50,
                "total": 150
            },
            "citations": []
        }
        yield mock

@pytest.fixture
def mock_llm_streaming():
    """Mock 流式 LLM 调用"""
    async def mock_stream(*args, **kwargs):
        chunks = ["这是", "模拟的", "流式", "响应"]
        for chunk in chunks:
            yield {"content": chunk, "done": False}
        yield {"content": "", "done": True}
    
    with patch("backend.ai.ai_proxy.call_llm_stream", mock_stream):
        yield
```

### 15.2 Mock 数据库

```python
@pytest.fixture
def mock_db():
    """Mock 数据库操作"""
    with patch("backend.database.execute_query") as mock_query, \
         patch("backend.database.execute_insert") as mock_insert, \
         patch("backend.database.execute_update") as mock_update:
        
        mock_query.return_value = []
        mock_insert.return_value = 1
        mock_update.return_value = 1
        
        yield {
            "query": mock_query,
            "insert": mock_insert,
            "update": mock_update
        }
```

### 15.3 Mock 外部 API

```python
@pytest.fixture
def mock_http():
    """Mock HTTP 请求"""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response
        yield mock_get
```

---

## 16. 测试夹具

### 16.1 夹具作用域

```python
@pytest.fixture(scope="function")  # 每个测试函数
def db():
    ...

@pytest.fixture(scope="class")  # 每个测试类
def app():
    ...

@pytest.fixture(scope="module")  # 每个测试模块
def config():
    ...

@pytest.fixture(scope="session")  # 整个测试会话
def event_loop():
    ...
```

### 16.2 夹具组合

```python
@pytest.fixture
def conversation_with_messages(db, mock_llm):
    """组合夹具：带消息的对话"""
    manager = ConversationManager(db_path=db)
    conv = manager.create_conversation(session_id="s1", title="测试")
    
    for i in range(5):
        manager.add_message(
            conv.id,
            agent_id="orchestrator",
            role="user" if i % 2 == 0 else "assistant",
            content=f"消息_{i}"
        )
    
    return conv
```

### 16.3 夹具参数化

```python
@pytest.fixture(params=[
    "deepseek-v3.2",
    "claude-sonnet-4.5",
    "gpt-4.1",
])
def model_id(request):
    """参数化夹具：测试多个模型"""
    return request.param
```

---

## 17. 参数化测试

### 17.1 基本参数化

```python
@pytest.mark.parametrize("input,expected", [
    ("", False),
    ("A", False),
    ("AB", True),
    ("ABC", True),
])
def test_title_min_length(input, expected):
    result = validate_title(input)
    assert result.is_valid == expected
```

### 17.2 复杂参数化

```python
@pytest.mark.parametrize("stage,event,expected_next", [
    (Stage.INFO_CONFIRM, Event.USER_CONFIRMED, Stage.CREATIVITY),
    (Stage.CREATIVITY, Event.CANDIDATES_GENERATED, Stage.VALIDATION),
    (Stage.VALIDATION, Event.SCORE_PASSED, Stage.GENERATION),
    (Stage.VALIDATION, Event.SCORE_FAILED, Stage.CREATIVITY),
    (Stage.GENERATION, Event.GENERATION_COMPLETED, Stage.DEEP_ASSIST),
])
def test_stage_transitions(stage, event, expected_next):
    result = transition(stage, event)
    assert result == expected_next
```

---

## 18. 异步测试

### 18.1 异步测试基础

```python
@pytest.mark.asyncio
async def test_async_orchestrator():
    orchestrator = OrchestratorAgent()
    result = await orchestrator.run({"input": "测试"})
    assert result.success
```

### 18.2 异步 Mock

```python
@pytest.mark.asyncio
async def test_async_llm_call():
    async def mock_call(*args, **kwargs):
        return {"content": "异步响应"}
    
    with patch("backend.ai.ai_proxy.call_llm", mock_call):
        result = await call_llm("deepseek-v3.2", [{"role": "user", "content": "你好"}])
        assert result["content"] == "异步响应"
```

---

## 19. 测试并行化

### 19.1 pytest-xdist 并行执行

```bash
# 自动并行执行（按 CPU 核心数）
pytest -n auto

# 指定进程数
pytest -n 4

# 按测试类分组
pytest -n auto --dist=loadscope
```

### 19.2 并行安全保证

```python
# 确保测试独立：每个测试使用独立的数据库
@pytest.fixture
def isolated_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    yield str(db_path)
    # tmp_path 自动清理
```

---

## 20. 测试报告

### 20.1 HTML 报告

```bash
pytest --html=report.html --self-contained-html
```

### 20.2 JUnit XML 报告

```bash
pytest --junitxml=junit.xml
```

### 20.3 Allure 报告

```bash
pytest --alluredir=allure-results
allure serve allure-results
```

---

## 21. CI/CD 集成

### 21.1 GitHub Actions 配置

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run unit tests
      run: pytest tests/unit/ --cov=backend --cov-report=xml
    
    - name: Run integration tests
      run: pytest tests/integration/
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

---

## 22. 质量门禁

### 22.1 质量门禁规则

```yaml
# quality-gates.yml
gates:
  - name: unit_test_pass_rate
    threshold: 1.0  # 100% 通过率
    action: block
    
  - name: integration_test_pass_rate
    threshold: 0.95  # 95% 通过率
    action: block
    
  - name: coverage_line
    threshold: 0.85  # 85% 行覆盖率
    action: warn
    
  - name: coverage_branch
    threshold: 0.80  # 80% 分支覆盖率
    action: warn
    
  - name: lint_errors
    threshold: 0  # 无 lint 错误
    action: block
    
  - name: type_check_errors
    threshold: 0  # 无类型错误
    action: block
```

---

## 23. 测试最佳实践

### 23.1 测试独立性

```python
# 好：测试独立，使用夹具
def test_create_conversation(isolated_db):
    manager = ConversationManager(db_path=isolated_db)
    conv = manager.create_conversation(session_id="s1", title="测试")
    assert conv.title == "测试"

# 差：测试依赖全局状态
_global_manager = ConversationManager()

def test_create_conversation():
    conv = _global_manager.create_conversation(session_id="s1", title="测试")
    assert conv.title == "测试"
```

### 23.2 测试可读性

```python
# 好：使用有意义的变量名，清晰断言
def test_conversation_isolation_between_tabs():
    first_conversation = create_conversation(title="对话1")
    second_conversation = create_conversation(title="对话2")
    
    send_message(first_conversation, content="你好")
    
    first_messages = get_messages(first_conversation)
    second_messages = get_messages(second_conversation)
    
    assert len(first_messages) == 1
    assert len(second_messages) == 0
```

### 23.3 测试维护性

```python
# 好：使用 Builder 模式构建复杂测试数据
class ConversationBuilder:
    def __init__(self):
        self._title = "测试对话"
        self._messages = []
    
    def with_title(self, title):
        self._title = title
        return self
    
    def with_messages(self, count):
        self._messages = [f"消息_{i}" for i in range(count)]
        return self
    
    def build(self):
        conv = create_conversation(title=self._title)
        for msg in self._messages:
            send_message(conv, content=msg)
        return conv

def test_conversation_with_many_messages():
    conv = ConversationBuilder().with_messages(100).build()
    messages = get_messages(conv)
    assert len(messages) == 100
```

---

## 24. 测试反模式

### 24.1 避免：测试实现细节

```python
# 差：测试私有方法
def test_internal_sort_algorithm():
    manager = ConversationManager()
    manager._sort_messages_internally()  # 测试私有方法
    assert manager._messages_cache is not None

# 好：测试公共行为
def test_messages_returned_in_chronological_order():
    manager = ConversationManager()
    manager.add_message(conv_id, role="user", content="第一条")
    manager.add_message(conv_id, role="user", content="第二条")
    
    messages = manager.get_messages(conv_id)
    assert messages[0].content == "第一条"
    assert messages[1].content == "第二条"
```

### 24.2 避免：过度 Mock

```python
# 差：Mock 了被测对象本身
def test_conversation_manager():
    with patch.object(ConversationManager, "create_conversation") as mock:
        mock.return_value = MagicMock()
        manager = ConversationManager()
        result = manager.create_conversation(...)
        # 这实际上什么都没测

# 好：只 Mock 外部依赖
def test_conversation_manager(mock_db):
    manager = ConversationManager(db_path=mock_db)
    result = manager.create_conversation(session_id="s1", title="测试")
    assert result.title == "测试"
```

---

## 25. 质量指标

### 25.1 测试质量指标

| 指标 | 目标 | 当前 |
|------|------|------|
| 测试用例总数 | ≥630 | 800+ |
| 单元测试占比 | ≥75% | 78% |
| 集成测试占比 | ≥20% | 18% |
| E2E测试占比 | ≤5% | 4% |
| 行覆盖率 | ≥85% | 88% |
| 分支覆盖率 | ≥80% | 82% |
| 函数覆盖率 | ≥90% | 92% |
| 测试执行时间（单元） | <30s | 25s |
| 测试执行时间（全部） | <30min | 22min |
| 缺陷逃逸率 | <5% | 3% |
| 测试稳定性 | ≥99% | 99.5% |

### 25.2 代码质量指标

| 指标 | 目标 | 工具 |
|------|------|------|
| 圈复杂度 | ≤10 | radon |
| 代码重复率 | ≤3% | pylint |
| 类型注解覆盖率 | ≥90% | mypy |
| 文档覆盖率 | ≥80% | pydocstyle |
| Lint 错误 | 0 | flake8, pylint |

---

## 26. 测试维护

### 26.1 测试代码审查

测试代码与生产代码同等重要，必须经过代码审查：

- 命名是否清晰表达意图
- 是否遵循 AAA 模式
- 是否有测试逻辑分支
- 是否过度 Mock
- 是否测试实现细节
- 断言是否充分

### 26.2 测试重构

定期重构测试代码：

- 提取公共夹具
- 消除测试重复
- 更新过时测试
- 删除无用测试
- 优化测试性能

---

## 27. 测试文档

### 27.1 测试计划文档

每个重大功能发布前应编写测试计划：

```markdown
# ThesisMiner v8.0 测试计划

## 1. 测试范围
- 多Agent架构
- 五阶段流程
- 多对话管理
- D3.js谱系图谱
- DeepSeek缓存优化

## 2. 测试策略
- 单元测试：每个模块独立测试
- 集成测试：模块间协作测试
- E2E测试：完整用户旅程
- 性能测试：响应时间与吞吐量

## 3. 测试环境
- Python 3.11+
- SQLite（测试库）
- Mock LLM API

## 4. 风险与缓解
- LLM API 不稳定 → Mock
- 数据库并发问题 → 隔离测试库
```

### 27.2 测试用例文档

```markdown
# 测试用例：多对话上下文隔离

## 用例ID
TC-CONV-001

## 前置条件
- 系统已启动
- 用户已登录

## 测试步骤
1. 创建会话 S1
2. 在 S1 下创建对话 C1 和 C2
3. 在 C1 发送消息 M1
4. 切换到 C2
5. 查看 C2 的消息列表

## 预期结果
- C2 的消息列表不包含 M1
- C1 的消息列表包含 M1
```

---

## 28. 测试培训

### 28.1 新人培训大纲

1. **测试基础**：测试金字塔、AAA模式、FIRST原则
2. **pytest 框架**：夹具、参数化、标记、插件
3. **Mock 技术**：unittest.mock、pytest-mock
4. **异步测试**：pytest-asyncio、AsyncMock
5. **覆盖率**：pytest-cov、覆盖率分析
6. **E2E测试**：Playwright 基础
7. **性能测试**：pytest-benchmark、locust
8. **CI/CD**：GitHub Actions 集成

### 28.2 测试规范培训

- 命名规范
- 目录结构
- 夹具使用
- Mock 使用
- 断言规范
- 提交规范

---

## 29. 测试自动化

### 29.1 自动化测试流水线

```
代码提交 → Lint检查 → 类型检查 → 单元测试 → 集成测试 → E2E测试 → 覆盖率检查 → 部署
   ↓           ↓          ↓           ↓           ↓          ↓          ↓         ↓
  Git       flake8     mypy       pytest     pytest    playwright  codecov   CD
```

### 29.2 自动化触发条件

- **提交时**：Lint + 类型检查 + 单元测试
- **PR 时**：+ 集成测试 + 覆盖率检查
- **合并时**：+ E2E测试
- **发布前**：+ 性能测试 + 负载测试
- **定时**：每日全量测试 + 冒烟测试

---

## 30. 附录

### 30.1 测试命令速查

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行 E2E 测试
pytest tests/e2e/

# 运行特定测试
pytest tests/unit/test_orchestrator.py::TestOrchestratorAgent::test_run

# 并行执行
pytest -n auto

# 生成覆盖率报告
pytest --cov=backend --cov-report=html

# 只运行慢测试
pytest -m slow

# 跳过慢测试
pytest -m "not slow"

# 失败时进入调试
pytest --pdb

# 失败时重试
pytest --reruns 3

# 生成 HTML 报告
pytest --html=report.html

# 生成 JUnit 报告
pytest --junitxml=junit.xml
```

### 30.2 常见问题

#### Q1: 测试失败但本地通过？

A: 检查以下几点：
1. 测试是否依赖全局状态
2. 测试执行顺序是否影响结果
3. 环境变量是否一致
4. 依赖版本是否一致

#### Q2: 异步测试报错 "coroutine never awaited"？

A: 确保使用 `@pytest.mark.asyncio` 装饰器，且安装了 `pytest-asyncio`。

#### Q3: Mock 不生效？

A: 检查 Mock 路径是否正确。Mock 应该 patch 被测模块导入的对象，而非原始定义位置。

#### Q4: 覆盖率不达标？

A: 使用 `--cov-report=term-missing` 查看未覆盖的行，针对性补充测试。

### 30.3 参考资源

- [pytest 官方文档](https://docs.pytest.org/)
- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [Playwright 文档](https://playwright.dev/python/)
- [测试金字塔](https://martinfowler.com/articles/practical-test-pyramid.html)
- [FIRST 测试原则](https://agileinaflash.blogspot.com/2009/02/first.html)

---

## 结语

测试是软件质量的基石。ThesisMiner v8.0 通过建立完善的测试体系，确保系统的正确性、稳定性与可维护性。每位开发者都应遵循本文档的测试规范，编写高质量的测试代码，共同维护项目的测试健康度。

> **测试箴言**：好的测试让你晚上睡得安稳，坏的测试让你白天忙得焦头烂额。
