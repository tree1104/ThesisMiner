"""Task 2.7：DeepSeek 缓存命中率测试

验证：
- build_cached_prefix 对相同输入返回字节级一致的前缀
- is_deepseek_model 正确识别 DeepSeek 模型
- record_cache_hit 与 get_cache_stats 正常工作
- 模拟 10 次同前缀调用，断言前缀字节完全一致
"""
import os
import sys
import uuid

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ai.prompt_cache import build_cached_prefix, is_deepseek_model
from backend.ai.cache_monitor import record_cache_hit, get_cache_stats
from backend.database import execute_insert, execute_query


def test_build_cached_prefix_consistent():
    """相同输入应返回字节级一致的前缀"""
    prefix1 = build_cached_prefix(
        system_role="你是论文选题专家",
        hard_constraints=["标题≤25字", "硕士1年内"],
        degree="master",
        discipline="计算机科学",
        advisor="深度学习",
    )
    prefix2 = build_cached_prefix(
        system_role="你是论文选题专家",
        hard_constraints=["标题≤25字", "硕士1年内"],
        degree="master",
        discipline="计算机科学",
        advisor="深度学习",
    )
    # 字节级一致
    assert prefix1.prefix.encode("utf-8") == prefix2.prefix.encode("utf-8")
    # prefix_messages 一致
    assert prefix1.prefix_messages == prefix2.prefix_messages
    # prefix_char_count 一致
    assert prefix1.prefix_char_count == prefix2.prefix_char_count
    print("✓ build_cached_prefix 字节级一致")


def test_build_cached_prefix_different_inputs():
    """不同输入应返回不同前缀"""
    prefix1 = build_cached_prefix(
        system_role="角色A",
        hard_constraints=["约束A"],
        degree="master",
    )
    prefix2 = build_cached_prefix(
        system_role="角色B",
        hard_constraints=["约束B"],
        degree="doctor",
    )
    assert prefix1.prefix != prefix2.prefix
    print("✓ build_cached_prefix 不同输入产生不同前缀")


def test_build_cached_prefix_empty_constraints():
    """空硬约束列表应正常处理"""
    prefix = build_cached_prefix(
        system_role="角色",
        hard_constraints=[],
        degree="",
        discipline="",
        advisor="",
    )
    # 应包含 SYSTEM_ROLE 段，不包含 HARD_CONSTRAINTS 与 ACADEMIC_CONTEXT
    assert "[SYSTEM_ROLE]" in prefix.prefix
    assert "[HARD_CONSTRAINTS]" not in prefix.prefix
    assert "[ACADEMIC_CONTEXT]" not in prefix.prefix
    assert prefix.prefix_char_count > 0
    print("✓ build_cached_prefix 空约束处理")


def test_is_deepseek_model():
    """is_deepseek_model 应正确识别 DeepSeek 模型"""
    # DeepSeek 模型
    assert is_deepseek_model("deepseek-v3.2") is True
    assert is_deepseek_model("deepseek-r2") is True
    assert is_deepseek_model("DeepSeek-V3") is True  # 大小写不敏感
    assert is_deepseek_model("DEEPSEEK-chat") is True
    # 非 DeepSeek 模型
    assert is_deepseek_model("gpt-4.1-mini") is False
    assert is_deepseek_model("claude-sonnet-4.5") is False
    assert is_deepseek_model("qwen3-max") is False
    assert is_deepseek_model("") is False
    print("✓ is_deepseek_model 识别正确")


def test_record_cache_hit_and_get_stats():
    """record_cache_hit 与 get_cache_stats 应正常工作"""
    session_id = uuid.uuid4().hex
    ledger_id = uuid.uuid4().hex

    # 插入一条 budget_ledger 记录（含 cache_hit_rate 列）
    execute_insert("budget_ledger", {
        "id": ledger_id,
        "session_id": session_id,
        "model": "deepseek-v3.2",
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "total_tokens": 1500,
        "cached_prompt_tokens": 950,
        "cost": 0.001,
        "purpose": "test",
        "cache_hit_rate": 0.0,
    })

    try:
        # 记录缓存命中（命中率 950/1000 = 0.95）
        record_cache_hit(
            model_id="deepseek-v3.2",
            prompt_tokens=1000,
            cached_tokens=950,
            ledger_id=ledger_id,
        )

        # 查询统计
        stats = get_cache_stats(limit=100)
        assert stats["total_calls"] >= 1
        assert stats["total_cached"] >= 950
        assert stats["total_prompt"] >= 1000
        # 整体命中率应接近 0.95
        assert stats["overall_hit_rate"] >= 0.9
        print("✓ record_cache_hit 与 get_cache_stats 正常工作")
    finally:
        # 清理
        execute_query(
            "DELETE FROM budget_ledger WHERE session_id = ?;",
            (session_id,),
        )


def test_record_cache_hit_zero_prompt():
    """prompt_tokens 为 0 时应跳过记录"""
    # 不应抛出异常
    record_cache_hit(
        model_id="deepseek-v3.2",
        prompt_tokens=0,
        cached_tokens=0,
        ledger_id=None,
    )
    print("✓ record_cache_hit 零 prompt 处理")


def test_simulate_10_calls_same_prefix():
    """模拟 10 次同前缀调用，断言前缀字节完全一致"""
    system_role = "你是学术论题生成专家 Reasoner"
    hard_constraints = [
        "必须输出 JSON 格式",
        "title 限 20 字以内的名词性短语",
        "confidence_score 取值范围 0-1",
        "严格按 JSON 格式输出",
    ]
    degree = "master"
    discipline = "计算机科学与技术"
    advisor = "深度学习与医学影像分析"

    # 收集 10 次构建的前缀字节
    prefix_bytes_list = []
    for i in range(10):
        prefix = build_cached_prefix(
            system_role=system_role,
            hard_constraints=hard_constraints,
            degree=degree,
            discipline=discipline,
            advisor=advisor,
        )
        prefix_bytes_list.append(prefix.prefix.encode("utf-8"))

    # 所有 10 次的前缀字节应完全一致
    first_bytes = prefix_bytes_list[0]
    for i, b in enumerate(prefix_bytes_list):
        assert b == first_bytes, f"第 {i + 1} 次构建的前缀字节不一致"
    # prefix_messages 也应一致
    first_messages = build_cached_prefix(
        system_role=system_role,
        hard_constraints=hard_constraints,
        degree=degree,
        discipline=discipline,
        advisor=advisor,
    ).prefix_messages
    for i in range(10):
        prefix = build_cached_prefix(
            system_role=system_role,
            hard_constraints=hard_constraints,
            degree=degree,
            discipline=discipline,
            advisor=advisor,
        )
        assert prefix.prefix_messages == first_messages
    print("✓ 10 次同前缀调用字节级一致")


def test_build_prompt_with_cache():
    """测试 prompts.build_prompt_with_cache 返回结构正确"""
    from backend.ai.prompts import build_prompt_with_cache

    result = build_prompt_with_cache(
        system_role="你是论文选题专家",
        hard_constraints=["标题≤25字"],
        degree="master",
        discipline="计算机科学",
        advisor="深度学习",
        dynamic_content="请生成一个关于医学影像的论题",
    )
    assert "prefix" in result
    assert "prefix_messages" in result
    assert "dynamic" in result
    assert "dynamic_messages" in result
    assert isinstance(result["prefix_messages"], list)
    assert len(result["prefix_messages"]) == 1
    assert result["prefix_messages"][0]["role"] == "system"
    assert result["dynamic_messages"][0]["role"] == "user"
    assert result["dynamic"] == "请生成一个关于医学影像的论题"
    print("✓ build_prompt_with_cache 返回结构正确")


if __name__ == "__main__":
    test_build_cached_prefix_consistent()
    test_build_cached_prefix_different_inputs()
    test_build_cached_prefix_empty_constraints()
    test_is_deepseek_model()
    test_record_cache_hit_and_get_stats()
    test_record_cache_hit_zero_prompt()
    test_simulate_10_calls_same_prefix()
    test_build_prompt_with_cache()
    print("\n所有缓存测试通过 ✓")
