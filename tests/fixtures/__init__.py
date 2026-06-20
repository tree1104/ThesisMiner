"""测试夹具数据包

提供各类型样本数据供集成测试、E2E 测试与压测使用：
- sample_theses: 50+ 论题标题 / 摘要 / 大纲 / 完整报告样本
- sample_papers: 30+ 学术论文样本（跨学科，2024-2026）
- sample_responses: AI 回复样本（含引用、推理、流式分片、错误响应）
- sample_lineage: 50+ 节点的学脉图谱样本
- sample_conversations: 多轮对话历史样本
- sample_budgets: 预算账本与缓存命中率样本
"""
from tests.fixtures.sample_theses import (
    SAMPLE_THESIS_TITLES,
    SAMPLE_THESIS_ABSTRACTS,
    SAMPLE_THESIS_OUTLINES,
    SAMPLE_FULL_REPORTS,
    get_thesis_by_discipline,
)
from tests.fixtures.sample_papers import (
    SAMPLE_PAPERS,
    PAPERS_BY_DISCIPLINE,
    PAPERS_BY_YEAR,
    get_papers_for_query,
)
from tests.fixtures.sample_responses import (
    SAMPLE_AI_RESPONSES,
    SAMPLE_REASONING_CONTENT,
    SAMPLE_STREAMING_CHUNKS,
    SAMPLE_ERROR_RESPONSES,
    get_response_with_citations,
)
from tests.fixtures.sample_lineage import (
    SAMPLE_LINEAGE_NODES,
    SAMPLE_LINEAGE_EDGES,
    SAMPLE_LINEAGE_METADATA,
    build_lineage_graph,
)
from tests.fixtures.sample_conversations import (
    SAMPLE_CONVERSATIONS,
    SAMPLE_MULTI_TURN_DIALOGUES,
    SAMPLE_AGENT_MESSAGES,
    build_conversation_history,
)
from tests.fixtures.sample_budgets import (
    SAMPLE_BUDGET_LEDGER,
    BUDGET_BY_MODEL,
    BUDGET_BY_SESSION,
    CACHE_HIT_RATE_SCENARIOS,
    MODEL_PRICING,
    BUDGET_THRESHOLDS,
    BUDGET_ALERTS,
    get_ledger_by_session,
    get_ledger_by_model,
    get_deepseek_records,
    get_high_cache_hit_records,
    calculate_session_cost,
    calculate_avg_cache_hit_rate,
    calculate_overall_cache_hit_rate,
    get_budget_summary,
    get_cost_comparison,
    check_budget_alert,
    build_ledger_entry,
    generate_batch_ledger_entries,
)

__all__ = [
    # 论题样本
    "SAMPLE_THESIS_TITLES",
    "SAMPLE_THESIS_ABSTRACTS",
    "SAMPLE_THESIS_OUTLINES",
    "SAMPLE_FULL_REPORTS",
    "get_thesis_by_discipline",
    # 论文样本
    "SAMPLE_PAPERS",
    "PAPERS_BY_DISCIPLINE",
    "PAPERS_BY_YEAR",
    "get_papers_for_query",
    # AI 回复样本
    "SAMPLE_AI_RESPONSES",
    "SAMPLE_REASONING_CONTENT",
    "SAMPLE_STREAMING_CHUNKS",
    "SAMPLE_ERROR_RESPONSES",
    "get_response_with_citations",
    # 学脉图谱样本
    "SAMPLE_LINEAGE_NODES",
    "SAMPLE_LINEAGE_EDGES",
    "SAMPLE_LINEAGE_METADATA",
    "build_lineage_graph",
    # 对话样本
    "SAMPLE_CONVERSATIONS",
    "SAMPLE_MULTI_TURN_DIALOGUES",
    "SAMPLE_AGENT_MESSAGES",
    "build_conversation_history",
    # 预算与缓存样本
    "SAMPLE_BUDGET_LEDGER",
    "BUDGET_BY_MODEL",
    "BUDGET_BY_SESSION",
    "CACHE_HIT_RATE_SCENARIOS",
    "MODEL_PRICING",
    "BUDGET_THRESHOLDS",
    "BUDGET_ALERTS",
    "get_ledger_by_session",
    "get_ledger_by_model",
    "get_deepseek_records",
    "get_high_cache_hit_records",
    "calculate_session_cost",
    "calculate_avg_cache_hit_rate",
    "calculate_overall_cache_hit_rate",
    "get_budget_summary",
    "get_cost_comparison",
    "check_budget_alert",
    "build_ledger_entry",
    "generate_batch_ledger_entries",
]
