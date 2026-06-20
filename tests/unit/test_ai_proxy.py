"""单元测试：统一 AI 调用代理模块

测试 backend/ai/ai_proxy.py 的所有功能，包括：
- call_llm 异步调用（mock OpenAI 客户端）
- 多模型客户端缓存（_clients 字典）
- extra_params 透传（max_tokens / enable_thinking / web_search）
- reasoning_content 思维链提取
- cached_tokens 缓存命中 token 提取
- citations 引用解析
- cached_prefix 三段式缓存前缀
- call_llm_stream 流式调用
- call_llm_json JSON 解析与重试
- call_llm_three_segment 三段式调用
- _parse_json JSON 解析容错
- check_api_configured 配置检查
"""
import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 设置临时数据库
import backend.database as _db
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_ai_test_")
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

# 重置 Settings 单例并配置 API Key
import backend.config as _config
_config._settings_instance = None
os.environ["AI_API_KEY"] = "test-api-key"

from backend.ai import ai_proxy
from backend.ai.ai_proxy import (
    call_llm,
    call_llm_json,
    call_llm_stream,
    call_llm_three_segment,
    check_api_configured,
    get_client,
    _parse_json,
    _clients,
)


def _make_mock_response(
    content: str = "模拟回复",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    cached_tokens: int = 0,
    reasoning_content: str = None,
):
    """构造模拟的 OpenAI 响应对象"""
    message = MagicMock()
    message.content = content
    message.reasoning_content = reasoning_content
    message.reasoning = None

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens
    # prompt_tokens_details
    details = MagicMock()
    details.cached_tokens = cached_tokens
    usage.prompt_tokens_details = details

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_mock_chunk(content: str = "", reasoning: str = ""):
    """构造模拟的流式 chunk"""
    delta = MagicMock()
    delta.content = content
    delta.reasoning_content = reasoning
    delta.reasoning = None

    choice = MagicMock()
    choice.delta = delta

    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


# ===== check_api_configured 测试 =====


class TestCheckApiConfigured:
    """check_api_configured 配置检查测试"""

    def test_check_api_configured_returns_bool(self):
        """check_api_configured 应返回布尔值"""
        result = check_api_configured()
        assert isinstance(result, bool)

    def test_check_api_configured_true_when_key_set(self):
        """API Key 已设置时应返回 True"""
        import backend.config as _cfg
        _cfg._settings_instance = None
        os.environ["AI_API_KEY"] = "test-key"
        assert check_api_configured() is True

    def test_check_api_configured_false_when_empty(self):
        """API Key 为空时应返回 False"""
        import backend.config as _cfg
        _cfg._settings_instance = None
        os.environ["AI_API_KEY"] = ""
        assert check_api_configured() is False
        # 恢复
        os.environ["AI_API_KEY"] = "test-api-key"


# ===== get_client 测试 =====


class TestGetClient:
    """get_client 客户端管理测试"""

    def setup_method(self, method):
        """每个测试前清理客户端缓存，避免缓存干扰。"""
        _clients.clear()
        # 确保 API Key 已设置
        import backend.config as _cfg
        _cfg._settings_instance = None
        os.environ["AI_API_KEY"] = "test-api-key"

    def test_get_client_returns_client(self):
        """get_client 应返回客户端对象"""
        with patch("backend.ai.ai_proxy.openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            client = get_client("deepseek-v3.2")
            assert client is not None

    def test_get_client_caches_by_model_id(self):
        """相同 model_id 应返回缓存的同一客户端"""
        with patch("backend.ai.ai_proxy.openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            client1 = get_client("gpt-4.1")
            client2 = get_client("gpt-4.1")
            assert client1 is client2

    def test_get_client_different_models_different_clients(self):
        """不同 model_id 应返回不同客户端"""
        with patch("backend.ai.ai_proxy.openai.AsyncOpenAI") as mock_openai:
            # 使用 side_effect 确保每次调用返回不同的 mock 实例
            mock_openai.side_effect = [MagicMock(), MagicMock()]
            client1 = get_client("deepseek-v3.2")
            client2 = get_client("gpt-4.1")
            assert client1 is not client2

    def test_get_client_none_uses_default_model(self):
        """model_id 为 None 时应使用默认模型"""
        with patch("backend.ai.ai_proxy.openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            client = get_client(None)
            assert client is not None

    def test_get_client_unknown_model_falls_back(self):
        """未知模型应回退到默认配置"""
        with patch("backend.ai.ai_proxy.openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            client = get_client("unknown-model-xyz")
            assert client is not None


# ===== call_llm 测试 =====


class TestCallLlm:
    """call_llm 异步调用测试"""

    @pytest.mark.asyncio
    async def test_call_llm_returns_dict(self):
        """call_llm 应返回字典"""
        mock_response = _make_mock_response(content="测试回复")
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm("系统提示", "用户提示", model="deepseek-v3.2")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_call_llm_content_extraction(self):
        """call_llm 应正确提取 content"""
        mock_response = _make_mock_response(content="提取的内容")
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm("sys", "user", model="deepseek-v3.2")
        assert result["content"] == "提取的内容"

    @pytest.mark.asyncio
    async def test_call_llm_token_extraction(self):
        """call_llm 应正确提取 token 用量"""
        mock_response = _make_mock_response(
            prompt_tokens=200, completion_tokens=100
        )
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm("sys", "user", model="deepseek-v3.2")
        assert result["prompt_tokens"] == 200
        assert result["completion_tokens"] == 100
        assert result["total_tokens"] == 300

    @pytest.mark.asyncio
    async def test_call_llm_cached_tokens_extraction(self):
        """call_llm 应正确提取 cached_tokens"""
        mock_response = _make_mock_response(cached_tokens=80)
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm("sys", "user", model="deepseek-v3.2")
        assert result["cached_tokens"] == 80

    @pytest.mark.asyncio
    async def test_call_llm_reasoning_content_extraction(self):
        """call_llm 应提取 reasoning_content 思维链"""
        mock_response = _make_mock_response(reasoning_content="思维过程")
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm("sys", "user", model="deepseek-r2")
        assert result.get("reasoning_content") == "思维过程"

    @pytest.mark.asyncio
    async def test_call_llm_no_reasoning_when_absent(self):
        """无思维链时不应包含 reasoning_content 键"""
        mock_response = _make_mock_response(reasoning_content=None)
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm("sys", "user", model="deepseek-v3.2")
        assert "reasoning_content" not in result

    @pytest.mark.asyncio
    async def test_call_llm_citations_extraction(self):
        """call_llm 应从 content 中解析引用"""
        content_with_url = "参考 https://example.com/paper 了解更多"
        mock_response = _make_mock_response(content=content_with_url)
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm("sys", "user", model="deepseek-v3.2")
        assert "citations" in result
        assert isinstance(result["citations"], list)

    @pytest.mark.asyncio
    async def test_call_llm_model_in_result(self):
        """call_llm 结果应包含使用的模型名"""
        mock_response = _make_mock_response()
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm("sys", "user", model="gpt-4.1")
        assert result["model"] == "gpt-4.1"

    @pytest.mark.asyncio
    async def test_call_llm_cost_in_result(self):
        """call_llm 结果应包含费用"""
        mock_response = _make_mock_response(prompt_tokens=1000, completion_tokens=500)
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm("sys", "user", model="deepseek-v3.2")
        assert "cost" in result
        assert result["cost"] >= 0

    @pytest.mark.asyncio
    async def test_call_llm_raises_when_api_not_configured(self):
        """API Key 未配置时应抛出 ValueError"""
        import backend.config as _cfg
        _cfg._settings_instance = None
        os.environ["AI_API_KEY"] = ""
        try:
            with pytest.raises(ValueError, match="AI API Key 未配置"):
                await call_llm("sys", "user", model="deepseek-v3.2")
        finally:
            os.environ["AI_API_KEY"] = "test-api-key"
            _cfg._settings_instance = None

    @pytest.mark.asyncio
    async def test_call_llm_uses_step_model_when_no_model(self):
        """未指定 model 时应按 purpose 路由"""
        mock_response = _make_mock_response()
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm("sys", "user", purpose="reasoner")
        assert result["model"] is not None

    @pytest.mark.asyncio
    async def test_call_llm_prefix_hash_injection(self):
        """提供 prefix_hash 时应注入缓存控制"""
        mock_response = _make_mock_response(cached_tokens=50)
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm(
                "sys", "user", model="deepseek-v3.2",
                prefix_hash="abc123def456",
            )
        assert result["prefix_hash"] == "abc123def456"
        assert result["cache_hit"] is True

    @pytest.mark.asyncio
    async def test_call_llm_prefix_hash_no_cache_hit(self):
        """prefix_hash 但 cached_tokens=0 时 cache_hit 应为 False"""
        mock_response = _make_mock_response(cached_tokens=0)
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm(
                "sys", "user", model="deepseek-v3.2",
                prefix_hash="abc123",
            )
        assert result["cache_hit"] is False

    @pytest.mark.asyncio
    async def test_call_llm_extra_params_max_tokens(self):
        """extra_params.max_tokens 应透传到请求"""
        mock_response = _make_mock_response()
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            await call_llm(
                "sys", "user", model="deepseek-v3.2",
                extra_params={"max_tokens": 2048},
            )
        # 验证 create 被调用且包含 max_tokens
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("max_tokens") == 2048

    @pytest.mark.asyncio
    async def test_call_llm_extra_params_web_search(self):
        """extra_params.web_search 应在模型支持时启用"""
        mock_response = _make_mock_response()
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            await call_llm(
                "sys", "user", model="deepseek-v3.2",
                extra_params={"web_search": True},
            )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "extra_body" in call_kwargs

    @pytest.mark.asyncio
    async def test_call_llm_response_format(self):
        """response_format 应透传到请求"""
        mock_response = _make_mock_response()
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            await call_llm(
                "sys", "user", model="deepseek-v3.2",
                response_format={"type": "json_object"},
            )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_call_llm_cached_prefix_deepseek(self):
        """DeepSeek 模型 + cached_prefix 应启用三段式缓存"""
        mock_response = _make_mock_response()
        cached_prefix = {
            "prefix": "[SYSTEM_ROLE]\n你是助手\n",
            "prefix_messages": [{"role": "system", "content": "你是助手"}],
            "dynamic_messages": [{"role": "user", "content": "动态查询"}],
        }
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm(
                "sys", "user", model="deepseek-v3.2",
                cached_prefix=cached_prefix,
            )
        assert "prefix_char_count" in result
        assert result["prefix_char_count"] > 0

    @pytest.mark.asyncio
    async def test_call_llm_cached_prefix_non_deepseek_ignored(self):
        """非 DeepSeek 模型应忽略 cached_prefix"""
        mock_response = _make_mock_response()
        cached_prefix = {
            "prefix": "[SYSTEM_ROLE]\n你是助手\n",
            "prefix_messages": [{"role": "system", "content": "你是助手"}],
        }
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm(
                "sys", "user", model="gpt-4.1",
                cached_prefix=cached_prefix,
            )
        # 非 DeepSeek 不应包含 prefix_char_count
        assert "prefix_char_count" not in result

    @pytest.mark.asyncio
    async def test_call_llm_temperature_override(self):
        """显式 temperature 应覆盖模型默认"""
        mock_response = _make_mock_response()
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            await call_llm("sys", "user", model="deepseek-v3.2", temperature=0.1)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.1


# ===== call_llm_stream 测试 =====


class TestCallLlmStream:
    """call_llm_stream 流式调用测试"""

    @pytest.mark.asyncio
    async def test_stream_yields_content_chunks(self):
        """流式应 yield content 类型片段"""
        async def mock_stream():
            yield _make_mock_chunk(content="片段1")
            yield _make_mock_chunk(content="片段2")

        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_get.return_value = mock_client
            chunks = []
            async for chunk in call_llm_stream("sys", "user", model="deepseek-v3.2"):
                chunks.append(chunk)
        content_chunks = [c for c in chunks if c["type"] == "content"]
        assert len(content_chunks) == 2

    @pytest.mark.asyncio
    async def test_stream_yields_reasoning_chunks(self):
        """流式应 yield reasoning 类型片段"""
        async def mock_stream():
            yield _make_mock_chunk(reasoning="思考过程")
            yield _make_mock_chunk(content="回复")

        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_get.return_value = mock_client
            chunks = []
            async for chunk in call_llm_stream("sys", "user", model="deepseek-r2"):
                chunks.append(chunk)
        reasoning_chunks = [c for c in chunks if c["type"] == "reasoning"]
        assert len(reasoning_chunks) == 1

    @pytest.mark.asyncio
    async def test_stream_empty_response(self):
        """空流式响应应不 yield 任何片段"""
        async def mock_stream():
            return
            yield  # 使其成为 async generator

        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_get.return_value = mock_client
            chunks = []
            async for chunk in call_llm_stream("sys", "user", model="deepseek-v3.2"):
                chunks.append(chunk)
        assert chunks == []

    @pytest.mark.asyncio
    async def test_stream_raises_when_not_configured(self):
        """API 未配置时应抛出 ValueError"""
        import backend.config as _cfg
        _cfg._settings_instance = None
        os.environ["AI_API_KEY"] = ""
        try:
            with pytest.raises(ValueError, match="AI API Key 未配置"):
                async for _ in call_llm_stream("sys", "user", model="deepseek-v3.2"):
                    pass
        finally:
            os.environ["AI_API_KEY"] = "test-api-key"
            _cfg._settings_instance = None

    @pytest.mark.asyncio
    async def test_stream_with_prefix_hash(self):
        """流式调用支持 prefix_hash 注入"""
        async def mock_stream():
            yield _make_mock_chunk(content="缓存流式")

        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_get.return_value = mock_client
            chunks = []
            async for chunk in call_llm_stream(
                "sys", "user", model="deepseek-v3.2",
                prefix_hash="test-hash",
            ):
                chunks.append(chunk)
        assert len(chunks) == 1


# ===== call_llm_json 测试 =====


class TestCallLlmJson:
    """call_llm_json JSON 解析调用测试"""

    @pytest.mark.asyncio
    async def test_json_returns_parsed_dict(self):
        """应返回解析后的 JSON 字典"""
        json_content = json.dumps({"key": "value"}, ensure_ascii=False)
        mock_response = _make_mock_response(content=json_content)
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm_json("sys", "user", model="deepseek-v3.2")
        assert result["content"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_json_with_code_block(self):
        """应解析 ```json 代码块"""
        json_content = '```json\n{"name": "test"}\n```'
        mock_response = _make_mock_response(content=json_content)
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm_json("sys", "user", model="deepseek-v3.2")
        assert result["content"] == {"name": "test"}

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_error(self):
        """解析失败应返回 error 兜底"""
        mock_response = _make_mock_response(content="这不是JSON")
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm_json("sys", "user", model="deepseek-v3.2")
        assert "error" in result
        assert result["error"] == "JSON 解析失败"


# ===== call_llm_three_segment 测试 =====


class TestCallLlmThreeSegment:
    """call_llm_three_segment 三段式调用测试"""

    @pytest.mark.asyncio
    async def test_three_segment_returns_dict(self):
        """三段式调用应返回字典"""
        mock_response = _make_mock_response(content="三段式回复")
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm_three_segment(
                base="基础段",
                profile="画像段",
                query="查询段",
                model="deepseek-v3.2",
            )
        assert isinstance(result, dict)
        assert result["content"] == "三段式回复"

    @pytest.mark.asyncio
    async def test_three_segment_includes_prefix_hash(self):
        """三段式调用结果应包含 prefix_hash"""
        mock_response = _make_mock_response()
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm_three_segment(
                base="base", profile="profile", query="query",
                model="deepseek-v3.2",
            )
        assert "prefix_hash" in result

    @pytest.mark.asyncio
    async def test_three_segment_with_dst_state(self):
        """三段式调用支持 DST 状态"""
        mock_response = _make_mock_response(content="带DST回复")
        with patch.object(ai_proxy, "get_client") as mock_get, patch("backend.ai.ai_proxy.check_api_configured", return_value=True):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client
            result = await call_llm_three_segment(
                base="base", profile="profile", query="query",
                dst_state={"selected_topic": "测试论题"},
                model="deepseek-v3.2",
            )
        assert result["content"] == "带DST回复"


# ===== _parse_json 测试 =====


class TestParseJson:
    """_parse_json JSON 解析容错测试"""

    def test_parse_json_valid(self):
        """有效 JSON 应解析成功"""
        result = _parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_code_block(self):
        """代码块包裹的 JSON 应解析成功"""
        result = _parse_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_json_substring(self):
        """从文本中提取 JSON 子串应成功"""
        result = _parse_json('前缀文字 {"key": "value"} 后缀文字')
        assert result == {"key": "value"}

    def test_parse_json_invalid_returns_none(self):
        """无效 JSON 应返回 None"""
        result = _parse_json("这不是JSON")
        assert result is None

    def test_parse_json_empty_string(self):
        """空字符串应返回 None"""
        result = _parse_json("")
        assert result is None

    def test_parse_json_none_input(self):
        """None 输入应返回 None"""
        result = _parse_json(None)
        assert result is None

    def test_parse_json_non_string_input(self):
        """非字符串输入应返回 None"""
        result = _parse_json(123)
        assert result is None

    def test_parse_json_with_trailing_comma(self):
        """带尾随逗号的 JSON 应通过 json5 解析"""
        result = _parse_json('{"key": "value",}')
        assert result == {"key": "value"}

    def test_parse_json_nested(self):
        """嵌套 JSON 应正确解析"""
        result = _parse_json('{"outer": {"inner": "value"}}')
        assert result == {"outer": {"inner": "value"}}

    def test_parse_json_array_value(self):
        """JSON 数组值应正确解析"""
        result = _parse_json('{"list": [1, 2, 3]}')
        assert result["list"] == [1, 2, 3]
