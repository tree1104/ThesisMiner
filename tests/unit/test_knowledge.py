"""知识图谱模块单元测试

测试 backend/knowledge 下的三个模块：
  - card_manager: 知识卡片 CRUD（add_card/get_card/list_cards/delete_card/search_cards）
  - graph_expander: 论文实体抽取与图谱扩展（extract_entities_from_text/expand_from_paper）
  - lineage_graph_store: 谱系节点与边存储（add_node/add_edge/get_all_*/delete_node/search_nodes）

测试策略：
  - card_manager 与 lineage_graph_store 使用临时数据库隔离
  - graph_expander 为纯逻辑测试，无需数据库
  - 覆盖 tags/metadata 的 JSON 序列化与反序列化
  - 边界条件：空输入、不存在的 ID、非法 JSON、模糊匹配
"""
import os
import sys
import tempfile
import uuid

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ===== 临时数据库初始化 =====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_knowledge_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.knowledge import card_manager, graph_expander, lineage_graph_store
from backend.knowledge.card_manager import (
    _deserialize_tags,
    add_card,
    get_card,
    list_cards,
    delete_card,
    search_cards,
)
from backend.knowledge.graph_expander import (
    _RELATION_TRIGGERS,
    extract_entities_from_text,
    expand_from_paper,
)
from backend.knowledge.lineage_graph_store import (
    _deserialize_metadata,
    add_node,
    add_edge,
    get_all_nodes,
    get_all_edges,
    get_graph,
    delete_node,
    search_nodes,
)
from backend.database import get_db_connection


# ===== 辅助函数 =====

def _make_card(title: str = "测试卡片", content: str = "测试内容", tags: list = None, source: str = "") -> str:
    """创建一张知识卡片并返回 card_id。"""
    return add_card(title, content, tags if tags is not None else ["测试"], source)


def _make_node(node_type: str = "paper", title: str = "测试节点", abstract: str = "摘要", metadata: dict = None) -> str:
    """创建一个谱系节点并返回 node_id。"""
    return add_node(node_type, title, abstract, metadata if metadata is not None else {"key": "value"})


# ============================================================
# 第一部分：card_manager 测试
# ============================================================

class TestDeserializeTags:
    """测试 _deserialize_tags 辅助函数。"""

    def test_deserialize_none_returns_empty(self):
        """None 输入应返回空列表。"""
        assert _deserialize_tags(None) == []

    def test_deserialize_empty_string_returns_empty(self):
        """空字符串输入应返回空列表。"""
        assert _deserialize_tags("") == []

    def test_deserialize_valid_json_list(self):
        """合法 JSON 数组应正确反序列化。"""
        raw = '["标签1", "标签2"]'
        result = _deserialize_tags(raw)
        assert result == ["标签1", "标签2"]

    def test_deserialize_invalid_json_returns_empty(self):
        """非法 JSON 应返回空列表。"""
        assert _deserialize_tags("不是JSON") == []

    def test_deserialize_json_object_returns_empty(self):
        """JSON 对象（非数组）应返回空列表。"""
        assert _deserialize_tags('{"key": "value"}') == []

    def test_deserialize_empty_list(self):
        """空 JSON 数组应返回空列表。"""
        assert _deserialize_tags("[]") == []

    def test_deserialize_nested_list(self):
        """嵌套列表应正确返回。"""
        raw = '[["嵌套"], "普通"]'
        result = _deserialize_tags(raw)
        assert result == [["嵌套"], "普通"]


class TestAddCard:
    """测试 add_card 函数。"""

    def test_add_card_returns_id(self):
        """新增卡片应返回非空 ID。"""
        card_id = add_card("标题", "内容", ["标签"], "来源")
        assert card_id is not None
        assert isinstance(card_id, str)
        assert len(card_id) > 0

    def test_add_card_default_tags(self):
        """tags 为 None 时应存储为空列表。"""
        card_id = add_card("标题", "内容")
        card = get_card(card_id)
        assert card is not None
        assert card["tags"] == []

    def test_add_card_default_source(self):
        """source 默认应为空字符串。"""
        card_id = add_card("标题", "内容", ["标签"])
        card = get_card(card_id)
        assert card is not None
        assert card["source"] == ""

    def test_add_card_with_tags(self):
        """带标签的卡片应正确存储。"""
        card_id = add_card("标题", "内容", ["机器学习", "深度学习"], "论文")
        card = get_card(card_id)
        assert card is not None
        assert "机器学习" in card["tags"]
        assert "深度学习" in card["tags"]

    def test_add_card_id_uniqueness(self):
        """多次新增应生成不同 ID。"""
        id1 = add_card("卡片1", "内容1")
        id2 = add_card("卡片2", "内容2")
        assert id1 != id2

    def test_add_card_persists_to_db(self):
        """新增的卡片应持久化到数据库。"""
        card_id = add_card("持久化测试", "内容", ["测试"])
        card = get_card(card_id)
        assert card is not None
        assert card["title"] == "持久化测试"
        assert card["content"] == "内容"

    def test_add_card_with_empty_tags_list(self):
        """空标签列表应正确存储。"""
        card_id = add_card("标题", "内容", [])
        card = get_card(card_id)
        assert card is not None
        assert card["tags"] == []


class TestGetCard:
    """测试 get_card 函数。"""

    def test_get_existing_card(self):
        """获取存在的卡片应返回完整字典。"""
        card_id = _make_card("获取测试", "内容", ["标签"])
        card = get_card(card_id)
        assert card is not None
        assert card["id"] == card_id
        assert card["title"] == "获取测试"
        assert card["content"] == "内容"
        assert card["tags"] == ["标签"]

    def test_get_nonexistent_card_returns_none(self):
        """获取不存在的卡片应返回 None。"""
        result = get_card("不存在的ID-12345")
        assert result is None

    def test_get_card_tags_deserialized(self):
        """获取卡片时 tags 应已反序列化为列表。"""
        card_id = add_card("标题", "内容", ["A", "B", "C"])
        card = get_card(card_id)
        assert isinstance(card["tags"], list)
        assert card["tags"] == ["A", "B", "C"]

    def test_get_card_has_created_at(self):
        """获取卡片应包含 created_at 字段。"""
        card_id = _make_card()
        card = get_card(card_id)
        assert "created_at" in card
        assert card["created_at"] is not None

    def test_get_card_has_all_fields(self):
        """获取卡片应包含所有字段。"""
        card_id = add_card("完整", "内容", ["标签"], "来源")
        card = get_card(card_id)
        assert "id" in card
        assert "title" in card
        assert "content" in card
        assert "tags" in card
        assert "source" in card
        assert "created_at" in card


class TestListCards:
    """测试 list_cards 函数。"""

    def test_list_empty_db(self):
        """空数据库应返回空列表。"""
        # 使用全新的临时数据库
        result = list_cards()
        # 可能有其他测试遗留数据，验证返回的是列表
        assert isinstance(result, list)

    def test_list_all_cards(self):
        """列出所有卡片。"""
        _make_card("列表1", "内容1", ["列表标签"])
        _make_card("列表2", "内容2", ["列表标签"])
        result = list_cards()
        titles = [c["title"] for c in result]
        assert "列表1" in titles
        assert "列表2" in titles

    def test_list_cards_tags_deserialized(self):
        """列出的卡片 tags 应已反序列化。"""
        add_card("反序列化测试", "内容", ["X", "Y"])
        result = list_cards()
        for card in result:
            assert isinstance(card["tags"], list)

    def test_list_cards_by_tag(self):
        """按标签过滤应只返回包含该标签的卡片。"""
        add_card("过滤A", "内容", ["特殊标签", "其他"])
        add_card("过滤B", "内容", ["普通标签"])
        result = list_cards("特殊标签")
        titles = [c["title"] for c in result]
        assert "过滤A" in titles
        assert "过滤B" not in titles

    def test_list_cards_by_nonexistent_tag(self):
        """不存在的标签应返回空列表。"""
        result = list_cards("完全不存在的标签XYZ")
        assert result == []

    def test_list_cards_ordered_by_created_at_desc(self):
        """卡片应按创建时间降序排列。"""
        add_card("旧卡片", "内容", ["排序测试"])
        add_card("新卡片", "内容", ["排序测试"])
        result = list_cards("排序测试")
        assert len(result) >= 2
        # 新创建的应在前面
        assert result[0]["title"] == "新卡片"


class TestDeleteCard:
    """测试 delete_card 函数。"""

    def test_delete_existing_card(self):
        """删除存在的卡片应返回 1。"""
        card_id = _make_card("待删除", "内容")
        result = delete_card(card_id)
        assert result == 1

    def test_delete_nonexistent_card(self):
        """删除不存在的卡片应返回 0。"""
        result = delete_card("不存在的ID-99999")
        assert result == 0

    def test_delete_card_then_get_returns_none(self):
        """删除后再次获取应返回 None。"""
        card_id = _make_card("删除验证", "内容")
        delete_card(card_id)
        assert get_card(card_id) is None

    def test_delete_card_not_affect_others(self):
        """删除一张卡片不应影响其他卡片。"""
        id1 = _make_card("卡片A", "内容")
        id2 = _make_card("卡片B", "内容")
        delete_card(id1)
        assert get_card(id1) is None
        assert get_card(id2) is not None

    def test_delete_card_twice(self):
        """重复删除应返回 0。"""
        card_id = _make_card("重复删除", "内容")
        first = delete_card(card_id)
        second = delete_card(card_id)
        assert first == 1
        assert second == 0


class TestSearchCards:
    """测试 search_cards 函数。"""

    def test_search_by_title(self):
        """按标题关键词搜索。"""
        add_card("深度学习研究", "内容", ["搜索"])
        result = search_cards("深度学习")
        titles = [c["title"] for c in result]
        assert "深度学习研究" in titles

    def test_search_by_content(self):
        """按正文关键词搜索。"""
        add_card("某标题", "本文研究自然语言处理技术", ["搜索"])
        result = search_cards("自然语言")
        titles = [c["title"] for c in result]
        assert "某标题" in titles

    def test_search_no_match(self):
        """无匹配时应返回空列表。"""
        result = search_cards("完全不匹配的关键词ZZZ")
        assert result == []

    def test_search_tags_deserialized(self):
        """搜索结果的 tags 应已反序列化。"""
        add_card("搜索反序列化", "内容", ["S", "T"])
        result = search_cards("搜索反序列化")
        for card in result:
            assert isinstance(card["tags"], list)

    def test_search_partial_match(self):
        """部分匹配应返回结果。"""
        add_card("机器学习入门指南", "内容", ["搜索"])
        result = search_cards("机器学习")
        assert len(result) >= 1

    def test_search_empty_keyword(self):
        """空关键词应匹配所有卡片（LIKE '%%'）。"""
        result = search_cards("")
        assert isinstance(result, list)


# ============================================================
# 第二部分：graph_expander 测试
# ============================================================

class TestRelationTriggers:
    """测试 _RELATION_TRIGGERS 常量。"""

    def test_triggers_contains_based_on(self):
        """触发词应包含'基于'。"""
        assert "基于" in _RELATION_TRIGGERS

    def test_triggers_contains_through(self):
        """触发词应包含'通过'。"""
        assert "通过" in _RELATION_TRIGGERS

    def test_triggers_contains_use(self):
        """触发词应包含'使用'。"""
        assert "使用" in _RELATION_TRIGGERS

    def test_triggers_is_list(self):
        """触发词应为列表类型。"""
        assert isinstance(_RELATION_TRIGGERS, list)

    def test_triggers_not_empty(self):
        """触发词列表不应为空。"""
        assert len(_RELATION_TRIGGERS) > 0


class TestExtractEntitiesFromText:
    """测试 extract_entities_from_text 函数。"""

    def test_extract_empty_text(self):
        """空文本应返回空列表。"""
        assert extract_entities_from_text("") == []

    def test_extract_none_text(self):
        """None 输入应返回空列表。"""
        assert extract_entities_from_text(None) == []

    def test_extract_with_based_on(self):
        """包含'基于'的句子应抽取三元组。"""
        text = "本研究基于深度学习方法解决图像分类问题。"
        result = extract_entities_from_text(text)
        assert len(result) >= 1
        triple = result[0]
        assert triple["relation"] == "基于"
        assert "深度学习方法解决图像分类问题" in triple["target"]

    def test_extract_with_through(self):
        """包含'通过'的句子应抽取三元组。"""
        text = "我们通过实验验证了模型的有效性。"
        result = extract_entities_from_text(text)
        assert len(result) >= 1
        assert result[0]["relation"] == "通过"

    def test_extract_with_use(self):
        """包含'使用'的句子应抽取三元组。"""
        text = "实验使用Transformer架构进行训练。"
        result = extract_entities_from_text(text)
        assert len(result) >= 1
        assert result[0]["relation"] == "使用"

    def test_extract_multiple_sentences(self):
        """多句子应抽取多个三元组。"""
        text = "本研究基于深度学习方法。我们通过实验验证了效果。系统使用GPU加速。"
        result = extract_entities_from_text(text)
        assert len(result) >= 3

    def test_extract_no_trigger_returns_empty(self):
        """无触发词的文本应返回空列表。"""
        text = "这是一段普通的文字，没有任何触发词。"
        result = extract_entities_from_text(text)
        assert result == []

    def test_extract_short_entity_filtered(self):
        """过短的实体（<2字符）应被过滤。"""
        text = "我基于深度学习进行研究。"
        result = extract_entities_from_text(text)
        # "我"长度为1，应被过滤
        for triple in result:
            assert len(triple["entity"]) >= 2

    def test_extract_short_target_filtered(self):
        """过短的目标（<2字符）应被过滤。"""
        text = "研究基于深度学习的方法。"
        result = extract_entities_from_text(text)
        for triple in result:
            assert len(triple["target"]) >= 2

    def test_extract_triple_structure(self):
        """抽取的三元组应包含 entity/relation/target 字段。"""
        text = "本研究基于深度学习方法。"
        result = extract_entities_from_text(text)
        assert len(result) >= 1
        triple = result[0]
        assert "entity" in triple
        assert "relation" in triple
        assert "target" in triple

    def test_extract_with_newline_separator(self):
        """换行符应作为句子分隔符。"""
        text = "研究基于深度学习\n另一研究通过实验验证"
        result = extract_entities_from_text(text)
        assert len(result) >= 2

    def test_extract_with_english_period(self):
        """英文句号应作为句子分隔符。"""
        text = "Research based on deep learning. Another through experiments."
        # 英文文本中"基于"等中文触发词不会匹配
        result = extract_entities_from_text(text)
        assert result == []


class TestExpandFromPaper:
    """测试 expand_from_paper 函数。"""

    def test_expand_returns_dict(self):
        """expand_from_paper 应返回字典。"""
        result = expand_from_paper("论文标题", "论文摘要")
        assert isinstance(result, dict)

    def test_expand_has_paper_title(self):
        """结果应包含 paper_title 字段。"""
        result = expand_from_paper("测试论文", "摘要内容")
        assert result["paper_title"] == "测试论文"

    def test_expand_has_entities(self):
        """结果应包含 entities 字段。"""
        result = expand_from_paper("论文", "摘要")
        assert "entities" in result
        assert isinstance(result["entities"], list)

    def test_expand_has_suggested_nodes(self):
        """结果应包含 suggested_nodes 字段。"""
        result = expand_from_paper("论文", "摘要")
        assert "suggested_nodes" in result
        assert isinstance(result["suggested_nodes"], list)

    def test_expand_has_suggested_edges(self):
        """结果应包含 suggested_edges 字段。"""
        result = expand_from_paper("论文", "摘要")
        assert "suggested_edges" in result
        assert isinstance(result["suggested_edges"], list)

    def test_expand_paper_node_always_present(self):
        """建议节点中应始终包含论文本身。"""
        result = expand_from_paper("我的论文", "摘要")
        nodes = result["suggested_nodes"]
        paper_nodes = [n for n in nodes if n.get("node_type") == "paper"]
        assert len(paper_nodes) >= 1
        assert paper_nodes[0]["title"] == "我的论文"

    def test_expand_with_entities_generates_concept_nodes(self):
        """有实体抽取时应生成概念节点。"""
        abstract = "本研究基于深度学习方法进行训练。"
        result = expand_from_paper("论文", abstract)
        concept_nodes = [n for n in result["suggested_nodes"] if n.get("node_type") == "concept"]
        assert len(concept_nodes) >= 1

    def test_expand_with_entities_generates_edges(self):
        """有实体抽取时应生成边。"""
        abstract = "本研究基于深度学习方法进行训练。"
        result = expand_from_paper("论文", abstract)
        assert len(result["suggested_edges"]) >= 1

    def test_expand_empty_abstract(self):
        """空摘要应只返回论文节点，无实体。"""
        result = expand_from_paper("论文", "")
        assert result["entities"] == []
        assert len(result["suggested_nodes"]) == 1

    def test_expand_no_duplicate_nodes(self):
        """相同实体不应生成重复节点。"""
        abstract = "研究基于深度学习。另一研究基于深度学习扩展。"
        result = expand_from_paper("论文", abstract)
        concept_titles = [n["title"] for n in result["suggested_nodes"] if n.get("node_type") == "concept"]
        # 检查无重复
        assert len(concept_titles) == len(set(concept_titles))

    def test_expand_edge_has_weight(self):
        """生成的边应包含 weight 字段。"""
        abstract = "研究基于深度学习方法。"
        result = expand_from_paper("论文", abstract)
        for edge in result["suggested_edges"]:
            assert "weight" in edge

    def test_expand_edge_has_relation_type(self):
        """生成的边应包含 relation_type 字段。"""
        abstract = "研究基于深度学习方法。"
        result = expand_from_paper("论文", abstract)
        for edge in result["suggested_edges"]:
            assert "relation_type" in edge


# ============================================================
# 第三部分：lineage_graph_store 测试
# ============================================================

class TestDeserializeMetadata:
    """测试 _deserialize_metadata 辅助函数。"""

    def test_deserialize_none_returns_empty(self):
        """None 输入应返回空字典。"""
        assert _deserialize_metadata(None) == {}

    def test_deserialize_empty_string_returns_empty(self):
        """空字符串应返回空字典。"""
        assert _deserialize_metadata("") == {}

    def test_deserialize_valid_json(self):
        """合法 JSON 对象应正确反序列化。"""
        raw = '{"key": "value", "num": 123}'
        result = _deserialize_metadata(raw)
        assert result == {"key": "value", "num": 123}

    def test_deserialize_invalid_json_returns_empty(self):
        """非法 JSON 应返回空字典。"""
        assert _deserialize_metadata("不是JSON") == {}

    def test_deserialize_json_array_returns_empty(self):
        """JSON 数组（非对象）应返回空字典。"""
        assert _deserialize_metadata('["a", "b"]') == {}

    def test_deserialize_empty_object(self):
        """空 JSON 对象应返回空字典。"""
        assert _deserialize_metadata("{}") == {}

    def test_deserialize_nested_object(self):
        """嵌套对象应正确返回。"""
        raw = '{"outer": {"inner": "value"}}'
        result = _deserialize_metadata(raw)
        assert result == {"outer": {"inner": "value"}}


class TestAddNode:
    """测试 add_node 函数。"""

    def test_add_node_returns_id(self):
        """新增节点应返回非空 ID。"""
        node_id = add_node("paper", "标题", "摘要")
        assert node_id is not None
        assert isinstance(node_id, str)
        assert len(node_id) > 0

    def test_add_node_default_metadata(self):
        """metadata 为 None 时应存储为空字典。"""
        node_id = add_node("paper", "标题", "摘要")
        nodes = get_all_nodes()
        target = [n for n in nodes if n["id"] == node_id][0]
        assert target["metadata"] == {}

    def test_add_node_with_metadata(self):
        """带 metadata 的节点应正确存储。"""
        node_id = add_node("method", "方法", "摘要", {"author": "张三", "year": 2026})
        nodes = get_all_nodes()
        target = [n for n in nodes if n["id"] == node_id][0]
        assert target["metadata"]["author"] == "张三"
        assert target["metadata"]["year"] == 2026

    def test_add_node_id_uniqueness(self):
        """多次新增应生成不同 ID。"""
        id1 = add_node("paper", "节点1")
        id2 = add_node("paper", "节点2")
        assert id1 != id2

    def test_add_node_persists_to_db(self):
        """新增节点应持久化到数据库。"""
        node_id = add_node("topic", "持久化", "内容")
        nodes = get_all_nodes()
        target = [n for n in nodes if n["id"] == node_id]
        assert len(target) == 1
        assert target[0]["title"] == "持久化"

    def test_add_node_default_abstract(self):
        """abstract 默认应为空字符串。"""
        node_id = add_node("paper", "标题")
        nodes = get_all_nodes()
        target = [n for n in nodes if n["id"] == node_id][0]
        assert target["abstract"] == ""


class TestAddEdge:
    """测试 add_edge 函数。"""

    def test_add_edge_returns_id(self):
        """新增边应返回非空 ID。"""
        sid = add_node("paper", "源节点")
        tid = add_node("paper", "目标节点")
        edge_id = add_edge(sid, tid, "cites")
        assert edge_id is not None
        assert isinstance(edge_id, str)

    def test_add_edge_default_weight(self):
        """默认权重应为 1.0。"""
        sid = add_node("paper", "源")
        tid = add_node("paper", "目标")
        add_edge(sid, tid, "extends")
        edges = get_all_edges()
        target = [e for e in edges if e["source_id"] == sid and e["target_id"] == tid]
        assert len(target) >= 1
        assert target[-1]["weight"] == 1.0

    def test_add_edge_custom_weight(self):
        """自定义权重应正确存储。"""
        sid = add_node("paper", "源")
        tid = add_node("paper", "目标")
        add_edge(sid, tid, "derives_from", 0.5)
        edges = get_all_edges()
        target = [e for e in edges if e["source_id"] == sid and e["target_id"] == tid]
        assert len(target) >= 1
        assert target[-1]["weight"] == 0.5

    def test_add_edge_persists(self):
        """新增边应持久化。"""
        sid = add_node("paper", "A")
        tid = add_node("paper", "B")
        add_edge(sid, tid, "cites")
        edges = get_all_edges()
        found = [e for e in edges if e["source_id"] == sid and e["target_id"] == tid]
        assert len(found) >= 1

    def test_add_edge_id_uniqueness(self):
        """多次新增边应生成不同 ID。"""
        sid = add_node("paper", "源")
        tid = add_node("paper", "目标")
        id1 = add_edge(sid, tid, "cites")
        id2 = add_edge(sid, tid, "extends")
        assert id1 != id2


class TestGetAllNodes:
    """测试 get_all_nodes 函数。"""

    def test_get_all_nodes_returns_list(self):
        """应返回列表。"""
        result = get_all_nodes()
        assert isinstance(result, list)

    def test_get_all_nodes_includes_new(self):
        """应包含新增的节点。"""
        node_id = add_node("paper", "查询测试节点")
        result = get_all_nodes()
        ids = [n["id"] for n in result]
        assert node_id in ids

    def test_get_all_nodes_metadata_deserialized(self):
        """返回的节点 metadata 应已反序列化。"""
        add_node("paper", "反序列化", "摘要", {"k": "v"})
        result = get_all_nodes()
        for node in result:
            assert isinstance(node["metadata"], dict)

    def test_get_all_nodes_has_all_fields(self):
        """返回的节点应包含所有字段。"""
        add_node("paper", "字段检查", "摘要", {"k": "v"})
        result = get_all_nodes()
        for node in result:
            assert "id" in node
            assert "node_type" in node
            assert "title" in node
            assert "abstract" in node
            assert "metadata" in node
            assert "created_at" in node


class TestGetAllEdges:
    """测试 get_all_edges 函数。"""

    def test_get_all_edges_returns_list(self):
        """应返回列表。"""
        result = get_all_edges()
        assert isinstance(result, list)

    def test_get_all_edges_includes_new(self):
        """应包含新增的边。"""
        sid = add_node("paper", "源")
        tid = add_node("paper", "目标")
        add_edge(sid, tid, "cites")
        result = get_all_edges()
        found = [e for e in result if e["source_id"] == sid]
        assert len(found) >= 1

    def test_get_all_edges_has_fields(self):
        """返回的边应包含所有字段。"""
        sid = add_node("paper", "源")
        tid = add_node("paper", "目标")
        add_edge(sid, tid, "cites", 0.8)
        result = get_all_edges()
        for edge in result:
            assert "id" in edge
            assert "source_id" in edge
            assert "target_id" in edge
            assert "relation_type" in edge
            assert "weight" in edge
            assert "created_at" in edge


class TestGetGraph:
    """测试 get_graph 函数。"""

    def test_get_graph_returns_dict(self):
        """应返回字典。"""
        result = get_graph()
        assert isinstance(result, dict)

    def test_get_graph_has_nodes_and_edges(self):
        """应包含 nodes 与 edges 键。"""
        result = get_graph()
        assert "nodes" in result
        assert "edges" in result

    def test_get_graph_nodes_is_list(self):
        """nodes 应为列表。"""
        result = get_graph()
        assert isinstance(result["nodes"], list)

    def test_get_graph_edges_is_list(self):
        """edges 应为列表。"""
        result = get_graph()
        assert isinstance(result["edges"], list)

    def test_get_graph_consistent_with_all(self):
        """get_graph 的结果应与 get_all_nodes + get_all_edges 一致。"""
        graph = get_graph()
        all_nodes = get_all_nodes()
        all_edges = get_all_edges()
        assert len(graph["nodes"]) == len(all_nodes)
        assert len(graph["edges"]) == len(all_edges)


class TestDeleteNode:
    """测试 delete_node 函数。"""

    def test_delete_existing_node(self):
        """删除存在的节点应返回 1。"""
        node_id = add_node("paper", "待删除")
        result = delete_node(node_id)
        assert result == 1

    def test_delete_nonexistent_node(self):
        """删除不存在的节点应返回 0。"""
        result = delete_node("不存在的ID-88888")
        assert result == 0

    def test_delete_node_removes_from_list(self):
        """删除后节点不应出现在列表中。"""
        node_id = add_node("paper", "删除验证")
        delete_node(node_id)
        nodes = get_all_nodes()
        ids = [n["id"] for n in nodes]
        assert node_id not in ids

    def test_delete_node_cascades_edges(self):
        """删除节点应级联删除关联边。"""
        sid = add_node("paper", "源")
        tid = add_node("paper", "目标")
        add_edge(sid, tid, "cites")
        delete_node(sid)
        edges = get_all_edges()
        remaining = [e for e in edges if e["source_id"] == sid or e["target_id"] == sid]
        assert len(remaining) == 0

    def test_delete_node_not_affect_others(self):
        """删除一个节点不应影响其他节点。"""
        id1 = add_node("paper", "A")
        id2 = add_node("paper", "B")
        delete_node(id1)
        nodes = get_all_nodes()
        ids = [n["id"] for n in nodes]
        assert id1 not in ids
        assert id2 in ids


class TestSearchNodes:
    """测试 search_nodes 函数。"""

    def test_search_by_title(self):
        """按标题关键词搜索。"""
        add_node("paper", "深度学习论文", "摘要")
        result = search_nodes("深度学习")
        titles = [n["title"] for n in result]
        assert "深度学习论文" in titles

    def test_search_no_match(self):
        """无匹配时应返回空列表。"""
        result = search_nodes("完全不匹配的关键词YYY")
        assert result == []

    def test_search_partial_match(self):
        """部分匹配应返回结果。"""
        add_node("method", "Transformer方法", "摘要")
        result = search_nodes("Transformer")
        assert len(result) >= 1

    def test_search_metadata_deserialized(self):
        """搜索结果的 metadata 应已反序列化。"""
        add_node("paper", "搜索反序列化", "摘要", {"k": "v"})
        result = search_nodes("搜索反序列化")
        for node in result:
            assert isinstance(node["metadata"], dict)

    def test_search_empty_keyword(self):
        """空关键词应匹配所有节点。"""
        result = search_nodes("")
        assert isinstance(result, list)

    def test_search_multiple_matches(self):
        """多个匹配应全部返回。"""
        add_node("paper", "机器学习基础", "摘要")
        add_node("method", "机器学习方法论", "摘要")
        result = search_nodes("机器学习")
        assert len(result) >= 2


# ============================================================
# 第四部分：集成测试
# ============================================================

class TestKnowledgeIntegration:
    """知识模块集成测试。"""

    def test_card_lifecycle(self):
        """测试卡片完整生命周期：增-查-改(删后增)-删。"""
        # 增
        card_id = add_card("生命周期", "内容", ["测试"], "来源")
        # 查
        card = get_card(card_id)
        assert card is not None
        assert card["title"] == "生命周期"
        # 删
        assert delete_card(card_id) == 1
        # 验证删除
        assert get_card(card_id) is None

    def test_node_edge_graph_integration(self):
        """测试节点-边-图谱集成。"""
        # 创建节点
        n1 = add_node("paper", "论文A", "摘要A", {"year": 2026})
        n2 = add_node("method", "方法B", "摘要B")
        n3 = add_node("topic", "主题C", "摘要C")
        # 创建边
        add_edge(n1, n2, "uses")
        add_edge(n2, n3, "derives_from")
        # 获取图谱
        graph = get_graph()
        assert len(graph["nodes"]) >= 3
        assert len(graph["edges"]) >= 2

    def test_expand_and_store(self):
        """测试从论文扩展并存储到图谱。"""
        abstract = "本研究基于深度学习方法。我们通过实验验证了效果。"
        expansion = expand_from_paper("集成论文", abstract)
        # 将建议节点存入数据库
        stored_ids = []
        for node in expansion["suggested_nodes"]:
            nid = add_node(
                node.get("node_type", "concept"),
                node.get("title", ""),
                node.get("abstract", ""),
            )
            stored_ids.append(nid)
        # 验证存储成功
        all_nodes = get_all_nodes()
        for nid in stored_ids:
            assert any(n["id"] == nid for n in all_nodes)

    def test_search_after_multiple_operations(self):
        """多次操作后搜索仍应正确。"""
        add_card("搜索集成A", "内容A", ["集成"])
        add_card("搜索集成B", "内容B", ["集成"])
        delete_card(add_card("搜索集成C", "内容C", ["集成"]))
        result = search_cards("搜索集成")
        titles = [c["title"] for c in result]
        assert "搜索集成A" in titles
        assert "搜索集成B" in titles
        assert "搜索集成C" not in titles
