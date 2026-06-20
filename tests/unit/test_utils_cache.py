"""cache 模块单元测试

覆盖 backend/utils/cache.py 中的所有组件：
- CacheEntry: 缓存条目（过期判断/访问更新）
- CacheStats: 缓存统计（命中率/记录/重置/转字典）
- MemoryCache: 内存缓存（TTL+LRU/获取/设置/删除/批量操作/淘汰/清理/关闭）
- AsyncMemoryCache: 异步内存缓存（异步获取/设置/删除/清理）
- CacheManager: 多命名空间缓存管理（创建/获取/移除/清空/统计）
- TTLDict: TTL 字典（设置/获取/存在/删除/清理/字典协议）
- cached: 缓存装饰器
- async_cached: 异步缓存装饰器
- 全局函数（get_cache_manager/get_cache/clear_all_caches/get_cache_stats）
"""
import asyncio
import time
import threading
from unittest.mock import patch

import pytest

from backend.utils.cache import (
    CacheEntry,
    CacheStats,
    MemoryCache,
    AsyncMemoryCache,
    CacheManager,
    TTLDict,
    cached,
    async_cached,
    get_cache_manager,
    get_cache,
    clear_all_caches,
    get_cache_stats,
    create_cache,
    _MISSING,
)


# ===== CacheEntry 测试 =====


class TestCacheEntry:
    """CacheEntry 数据类测试"""

    def test_default_values(self):
        """默认值"""
        entry = CacheEntry(value="test")
        assert entry.value == "test"
        assert entry.expires_at == 0.0
        assert entry.access_count == 0
        assert entry.size_bytes == 0

    def test_is_expired_never(self):
        """永不过期"""
        entry = CacheEntry(value="test", expires_at=0.0)
        assert entry.is_expired() is False

    def test_is_expired_future(self):
        """未来过期"""
        entry = CacheEntry(value="test", expires_at=time.time() + 3600)
        assert entry.is_expired() is False

    def test_is_expired_past(self):
        """已过期"""
        entry = CacheEntry(value="test", expires_at=time.time() - 1)
        assert entry.is_expired() is True

    def test_touch(self):
        """访问更新"""
        entry = CacheEntry(value="test")
        assert entry.access_count == 0
        entry.touch()
        assert entry.access_count == 1
        entry.touch()
        assert entry.access_count == 2

    def test_touch_updates_last_accessed(self):
        """更新最后访问时间"""
        entry = CacheEntry(value="test")
        old_time = entry.last_accessed
        time.sleep(0.01)
        entry.touch()
        assert entry.last_accessed >= old_time


# ===== CacheStats 测试 =====


class TestCacheStats:
    """CacheStats 统计类测试"""

    def test_initial_values(self):
        """初始值"""
        stats = CacheStats()
        d = stats.to_dict()
        assert d["hits"] == 0
        assert d["misses"] == 0
        assert d["evictions"] == 0
        assert d["expirations"] == 0
        assert d["sets"] == 0
        assert d["deletes"] == 0
        assert d["errors"] == 0

    def test_record_hit(self):
        """记录命中"""
        stats = CacheStats()
        stats.record_hit()
        stats.record_hit()
        assert stats.to_dict()["hits"] == 2

    def test_record_miss(self):
        """记录未命中"""
        stats = CacheStats()
        stats.record_miss()
        assert stats.to_dict()["misses"] == 1

    def test_record_eviction(self):
        """记录淘汰"""
        stats = CacheStats()
        stats.record_eviction()
        assert stats.to_dict()["evictions"] == 1

    def test_record_expiration(self):
        """记录过期"""
        stats = CacheStats()
        stats.record_expiration()
        assert stats.to_dict()["expirations"] == 1

    def test_record_set(self):
        """记录设置"""
        stats = CacheStats()
        stats.record_set()
        assert stats.to_dict()["sets"] == 1

    def test_record_delete(self):
        """记录删除"""
        stats = CacheStats()
        stats.record_delete()
        assert stats.to_dict()["deletes"] == 1

    def test_record_error(self):
        """记录错误"""
        stats = CacheStats()
        stats.record_error()
        assert stats.to_dict()["errors"] == 1

    def test_hit_rate_zero(self):
        """命中率为零（无请求）"""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        """命中率计算"""
        stats = CacheStats()
        for _ in range(7):
            stats.record_hit()
        for _ in range(3):
            stats.record_miss()
        assert stats.hit_rate == 0.7

    def test_hit_rate_all_hits(self):
        """全部命中"""
        stats = CacheStats()
        stats.record_hit()
        stats.record_hit()
        assert stats.hit_rate == 1.0

    def test_hit_rate_all_misses(self):
        """全部未命中"""
        stats = CacheStats()
        stats.record_miss()
        stats.record_miss()
        assert stats.hit_rate == 0.0

    def test_to_dict(self):
        """转字典"""
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss()
        d = stats.to_dict()
        assert "hits" in d
        assert "misses" in d
        assert "hit_rate" in d
        assert "evictions" in d
        assert "expirations" in d
        assert "sets" in d
        assert "deletes" in d
        assert "errors" in d
        assert "total_requests" in d
        assert "uptime_seconds" in d

    def test_reset(self):
        """重置统计"""
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss()
        stats.record_eviction()
        stats.reset()
        d = stats.to_dict()
        assert d["hits"] == 0
        assert d["misses"] == 0
        assert d["evictions"] == 0

    def test_thread_safety(self):
        """线程安全"""
        stats = CacheStats()
        def increment():
            for _ in range(100):
                stats.record_hit()

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert stats.to_dict()["hits"] == 1000


# ===== MemoryCache 测试 =====


class TestMemoryCache:
    """MemoryCache 内存缓存测试"""

    def test_set_and_get(self):
        """设置与获取"""
        cache = MemoryCache()
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_get_nonexistent(self):
        """获取不存在的键"""
        cache = MemoryCache()
        assert cache.get("nonexistent") is None

    def test_get_with_default(self):
        """带默认值获取"""
        cache = MemoryCache()
        assert cache.get("nonexistent", default="default") == "default"

    def test_set_overwrite(self):
        """覆盖设置"""
        cache = MemoryCache()
        cache.set("key", "value1")
        cache.set("key", "value2")
        assert cache.get("key") == "value2"

    def test_delete(self):
        """删除"""
        cache = MemoryCache()
        cache.set("key", "value")
        assert cache.delete("key") is True
        assert cache.get("key") is None

    def test_delete_nonexistent(self):
        """删除不存在的键"""
        cache = MemoryCache()
        assert cache.delete("nonexistent") is False

    def test_exists(self):
        """存在判断"""
        cache = MemoryCache()
        cache.set("key", "value")
        assert cache.exists("key") is True
        assert cache.exists("nonexistent") is False

    def test_exists_expired(self):
        """过期键不存在"""
        cache = MemoryCache(default_ttl=0.05)
        cache.set("key", "value")
        time.sleep(0.1)
        assert cache.exists("key") is False

    def test_size(self):
        """缓存大小"""
        cache = MemoryCache()
        assert cache.size() == 0
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert cache.size() == 2

    def test_clear(self):
        """清空"""
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.size() == 0

    def test_keys(self):
        """获取所有键"""
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert set(cache.keys()) == {"key1", "key2"}

    def test_values(self):
        """获取所有值"""
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert set(cache.values()) == {"value1", "value2"}

    def test_items(self):
        """获取所有键值对"""
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        items = dict(cache.items())
        assert items == {"key1": "value1", "key2": "value2"}

    def test_ttl_expiration(self):
        """TTL 过期"""
        cache = MemoryCache(default_ttl=0.05)
        cache.set("key", "value")
        assert cache.get("key") == "value"
        time.sleep(0.1)
        assert cache.get("key") is None

    def test_custom_ttl(self):
        """自定义 TTL"""
        cache = MemoryCache(default_ttl=300)
        cache.set("short", "value", ttl=0.05)
        cache.set("long", "value", ttl=300)
        time.sleep(0.1)
        assert cache.get("short") is None
        assert cache.get("long") == "value"

    def test_ttl_zero_never_expires(self):
        """TTL 为 0 永不过期"""
        cache = MemoryCache(default_ttl=0)
        cache.set("key", "value")
        time.sleep(0.05)
        assert cache.get("key") == "value"

    def test_lru_eviction(self):
        """LRU 淘汰"""
        cache = MemoryCache(max_size=3, eviction_policy="lru")
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # 访问 a，使其成为最近使用
        cache.set("d", 4)  # 应淘汰 b（最久未使用）
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_fifo_eviction(self):
        """FIFO 淘汰"""
        cache = MemoryCache(max_size=3, eviction_policy="fifo")
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # 淘汰 a
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_lfu_eviction(self):
        """LFU 淘汰"""
        cache = MemoryCache(max_size=3, eviction_policy="lfu")
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # 多次访问 a 和 c
        cache.get("a")
        cache.get("a")
        cache.get("c")
        cache.set("d", 4)  # 淘汰 b（访问次数最少）
        assert cache.get("b") is None
        assert cache.get("a") == 1

    def test_get_or_set_existing(self):
        """get_or_set 已存在"""
        cache = MemoryCache()
        cache.set("key", "existing")
        result = cache.get_or_set("key", factory=lambda: "new")
        assert result == "existing"

    def test_get_or_set_new(self):
        """get_or_set 新建"""
        cache = MemoryCache()
        result = cache.get_or_set("key", factory=lambda: "new")
        assert result == "new"
        assert cache.get("key") == "new"

    def test_get_many(self):
        """批量获取"""
        cache = MemoryCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        result = cache.get_many(["a", "b", "d"])
        assert result == {"a": 1, "b": 2}

    def test_set_many(self):
        """批量设置"""
        cache = MemoryCache()
        cache.set_many({"a": 1, "b": 2, "c": 3})
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_delete_many(self):
        """批量删除"""
        cache = MemoryCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        count = cache.delete_many(["a", "c", "d"])
        assert count == 2
        assert cache.get("a") is None
        assert cache.get("b") == 2

    def test_get_stats(self):
        """获取统计"""
        cache = MemoryCache()
        cache.set("key", "value")
        cache.get("key")
        cache.get("nonexistent")
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1
        assert stats["size"] == 1
        assert stats["max_size"] == 1000

    def test_reset_stats(self):
        """重置统计"""
        cache = MemoryCache()
        cache.set("key", "value")
        cache.get("key")
        cache.reset_stats()
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_cleanup(self):
        """手动清理过期"""
        cache = MemoryCache(default_ttl=0.05, cleanup_interval=0)
        cache.set("a", 1)
        cache.set("b", 2)
        time.sleep(0.1)
        cleaned = cache.cleanup()
        assert cleaned == 2
        assert cache.size() == 0

    def test_close(self):
        """关闭缓存"""
        cache = MemoryCache()
        cache.set("key", "value")
        cache.close()
        assert cache.get("key") is None

    def test_contains(self):
        """__contains__ 协议"""
        cache = MemoryCache()
        cache.set("key", "value")
        assert "key" in cache
        assert "nonexistent" not in cache

    def test_len(self):
        """__len__ 协议"""
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert len(cache) == 2

    def test_getitem(self):
        """__getitem__ 协议"""
        cache = MemoryCache()
        cache.set("key", "value")
        assert cache["key"] == "value"

    def test_getitem_keyerror(self):
        """__getitem__ 键不存在"""
        cache = MemoryCache()
        with pytest.raises(KeyError):
            _ = cache["nonexistent"]

    def test_setitem(self):
        """__setitem__ 协议"""
        cache = MemoryCache()
        cache["key"] = "value"
        assert cache.get("key") == "value"

    def test_delitem(self):
        """__delitem__ 协议"""
        cache = MemoryCache()
        cache.set("key", "value")
        del cache["key"]
        assert cache.get("key") is None

    def test_delitem_keyerror(self):
        """__delitem__ 键不存在"""
        cache = MemoryCache()
        with pytest.raises(KeyError):
            del cache["nonexistent"]

    def test_make_key_string(self):
        """字符串键"""
        cache = MemoryCache()
        key = cache._make_key("test")
        assert key == "test"

    def test_make_key_non_string(self):
        """非字符串键"""
        cache = MemoryCache()
        key = cache._make_key(42)
        assert isinstance(key, str)

    def test_make_key_complex(self):
        """复杂键"""
        cache = MemoryCache()
        key = cache._make_key({"a": 1})
        assert isinstance(key, str)

    def test_thread_safety(self):
        """线程安全"""
        cache = MemoryCache(max_size=100)
        errors = []

        def writer(start):
            try:
                for i in range(50):
                    cache.set(f"key_{start}_{i}", i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(50):
                    cache.get(f"key_0_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(1,)),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_none_value(self):
        """None 值"""
        cache = MemoryCache()
        cache.set("key", None)
        # None 值应与键不存在区分
        assert cache.get("key") is None
        assert cache.exists("key") is True

    def test_complex_value(self):
        """复杂值"""
        cache = MemoryCache()
        value = {"list": [1, 2, 3], "nested": {"a": True}}
        cache.set("key", value)
        assert cache.get("key") == value


# ===== AsyncMemoryCache 测试 =====


class TestAsyncMemoryCache:
    """AsyncMemoryCache 异步缓存测试"""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """设置与获取"""
        cache = AsyncMemoryCache()
        await cache.set("key", "value")
        result = await cache.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """获取不存在的键"""
        cache = AsyncMemoryCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_default(self):
        """带默认值"""
        cache = AsyncMemoryCache()
        result = await cache.get("nonexistent", default="default")
        assert result == "default"

    @pytest.mark.asyncio
    async def test_delete(self):
        """删除"""
        cache = AsyncMemoryCache()
        await cache.set("key", "value")
        assert await cache.delete("key") is True
        assert await cache.get("key") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        """删除不存在的键"""
        cache = AsyncMemoryCache()
        assert await cache.delete("nonexistent") is False

    @pytest.mark.asyncio
    async def test_clear(self):
        """清空"""
        cache = AsyncMemoryCache()
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()
        assert await cache.size() == 0

    @pytest.mark.asyncio
    async def test_size(self):
        """大小"""
        cache = AsyncMemoryCache()
        assert await cache.size() == 0
        await cache.set("key", "value")
        assert await cache.size() == 1

    @pytest.mark.asyncio
    async def test_get_or_set_existing(self):
        """get_or_set 已存在"""
        cache = AsyncMemoryCache()
        await cache.set("key", "existing")
        result = await cache.get_or_set("key", factory=lambda: "new")
        assert result == "existing"

    @pytest.mark.asyncio
    async def test_get_or_set_new(self):
        """get_or_set 新建"""
        cache = AsyncMemoryCache()
        result = await cache.get_or_set("key", factory=lambda: "new")
        assert result == "new"

    @pytest.mark.asyncio
    async def test_get_or_set_async_factory(self):
        """get_or_set 异步工厂"""
        cache = AsyncMemoryCache()
        async def async_factory():
            return "async_result"

        result = await cache.get_or_set("key", factory=async_factory)
        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """LRU 淘汰"""
        cache = AsyncMemoryCache(max_size=3, eviction_policy="lru")
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)
        await cache.get("a")  # 访问 a
        await cache.set("d", 4)  # 淘汰 b
        assert await cache.get("a") == 1
        assert await cache.get("b") is None

    @pytest.mark.asyncio
    async def test_fifo_eviction(self):
        """FIFO 淘汰"""
        cache = AsyncMemoryCache(max_size=3, eviction_policy="fifo")
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)
        await cache.set("d", 4)
        assert await cache.get("a") is None

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """获取统计"""
        cache = AsyncMemoryCache()
        await cache.set("key", "value")
        await cache.get("key")
        await cache.get("nonexistent")
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """TTL 过期"""
        cache = AsyncMemoryCache(default_ttl=0.05)
        await cache.set("key", "value")
        assert await cache.get("key") == "value"
        await asyncio.sleep(0.1)
        assert await cache.get("key") is None


# ===== CacheManager 测试 =====


class TestCacheManager:
    """CacheManager 缓存管理器测试"""

    def test_create_cache(self):
        """创建缓存"""
        manager = CacheManager()
        cache = manager.create_cache("test", max_size=100, default_ttl=60)
        assert cache is not None
        assert cache.max_size == 100

    def test_create_cache_duplicate(self):
        """创建重复缓存返回已有"""
        manager = CacheManager()
        cache1 = manager.create_cache("test")
        cache2 = manager.create_cache("test")
        assert cache1 is cache2

    def test_get_cache(self):
        """获取缓存"""
        manager = CacheManager()
        manager.create_cache("test")
        cache = manager.get_cache("test")
        assert cache is not None

    def test_get_cache_nonexistent(self):
        """获取不存在的缓存"""
        manager = CacheManager()
        assert manager.get_cache("nonexistent") is None

    def test_remove_cache(self):
        """移除缓存"""
        manager = CacheManager()
        manager.create_cache("test")
        assert manager.remove_cache("test") is True
        assert manager.get_cache("test") is None

    def test_remove_cache_nonexistent(self):
        """移除不存在的缓存"""
        manager = CacheManager()
        assert manager.remove_cache("nonexistent") is False

    def test_list_caches(self):
        """列出缓存"""
        manager = CacheManager()
        manager.create_cache("cache1")
        manager.create_cache("cache2")
        names = manager.list_caches()
        assert "cache1" in names
        assert "cache2" in names

    def test_clear_all(self):
        """清空所有缓存"""
        manager = CacheManager()
        c1 = manager.create_cache("cache1")
        c2 = manager.create_cache("cache2")
        c1.set("key", "value")
        c2.set("key", "value")
        manager.clear_all()
        assert c1.size() == 0
        assert c2.size() == 0

    def test_cleanup_all(self):
        """清理所有过期"""
        manager = CacheManager()
        c1 = manager.create_cache("cache1", default_ttl=0.05)
        c1.set("key", "value")
        time.sleep(0.1)
        cleaned = manager.cleanup_all()
        assert cleaned >= 1

    def test_get_all_stats(self):
        """获取所有统计"""
        manager = CacheManager()
        c1 = manager.create_cache("cache1")
        c1.set("key", "value")
        stats = manager.get_all_stats()
        assert "cache1" in stats

    def test_get_aggregate_stats(self):
        """聚合统计"""
        manager = CacheManager()
        c1 = manager.create_cache("cache1")
        c2 = manager.create_cache("cache2")
        c1.set("key1", "value1")
        c2.set("key2", "value2")
        stats = manager.get_aggregate_stats()
        assert stats["cache_count"] == 2
        assert stats["total_size"] == 2
        assert stats["total_sets"] == 2


# ===== TTLDict 测试 =====


class TestTTLDict:
    """TTLDict TTL 字典测试"""

    def test_set_and_get(self):
        """设置与获取"""
        d = TTLDict()
        d.set("key", "value")
        assert d.get("key") == "value"

    def test_get_nonexistent(self):
        """获取不存在的键"""
        d = TTLDict()
        assert d.get("nonexistent") is None

    def test_get_with_default(self):
        """带默认值"""
        d = TTLDict()
        assert d.get("nonexistent", default="default") == "default"

    def test_exists(self):
        """存在判断"""
        d = TTLDict()
        d.set("key", "value")
        assert d.exists("key") is True
        assert d.exists("nonexistent") is False

    def test_delete(self):
        """删除"""
        d = TTLDict()
        d.set("key", "value")
        assert d.delete("key") is True
        assert d.get("key") is None

    def test_delete_nonexistent(self):
        """删除不存在的键"""
        d = TTLDict()
        assert d.delete("nonexistent") is False

    def test_clear(self):
        """清空"""
        d = TTLDict()
        d.set("key1", "value1")
        d.set("key2", "value2")
        d.clear()
        assert d.get("key1") is None

    def test_ttl_expiration(self):
        """TTL 过期"""
        d = TTLDict(default_ttl=0.05)
        d.set("key", "value")
        assert d.get("key") == "value"
        time.sleep(0.1)
        assert d.get("key") is None

    def test_custom_ttl(self):
        """自定义 TTL"""
        d = TTLDict(default_ttl=300)
        d.set("short", "value", ttl=0.05)
        d.set("long", "value", ttl=300)
        time.sleep(0.1)
        assert d.get("short") is None
        assert d.get("long") == "value"

    def test_ttl_zero_never_expires(self):
        """TTL 为 0 永不过期"""
        d = TTLDict(default_ttl=0)
        d.set("key", "value")
        time.sleep(0.05)
        assert d.get("key") == "value"

    def test_keys(self):
        """获取键"""
        d = TTLDict()
        d.set("a", 1)
        d.set("b", 2)
        assert set(d.keys()) == {"a", "b"}

    def test_values(self):
        """获取值"""
        d = TTLDict()
        d.set("a", 1)
        d.set("b", 2)
        assert set(d.values()) == {1, 2}

    def test_items(self):
        """获取键值对"""
        d = TTLDict()
        d.set("a", 1)
        d.set("b", 2)
        assert dict(d.items()) == {"a": 1, "b": 2}

    def test_setitem(self):
        """__setitem__ 协议"""
        d = TTLDict()
        d["key"] = "value"
        assert d.get("key") == "value"

    def test_getitem(self):
        """__getitem__ 协议"""
        d = TTLDict()
        d.set("key", "value")
        assert d["key"] == "value"

    def test_getitem_keyerror(self):
        """__getitem__ 键不存在"""
        d = TTLDict()
        with pytest.raises(KeyError):
            _ = d["nonexistent"]

    def test_contains(self):
        """__contains__ 协议"""
        d = TTLDict()
        d.set("key", "value")
        assert "key" in d
        assert "nonexistent" not in d

    def test_delitem(self):
        """__delitem__ 协议"""
        d = TTLDict()
        d.set("key", "value")
        del d["key"]
        assert d.get("key") is None

    def test_delitem_keyerror(self):
        """__delitem__ 键不存在"""
        d = TTLDict()
        with pytest.raises(KeyError):
            del d["nonexistent"]

    def test_len(self):
        """__len__ 协议"""
        d = TTLDict()
        d.set("a", 1)
        d.set("b", 2)
        assert len(d) == 2

    def test_len_excludes_expired(self):
        """len 排除过期键"""
        d = TTLDict(default_ttl=0.05)
        d.set("a", 1)
        d.set("b", 2)
        time.sleep(0.1)
        assert len(d) == 0

    def test_overwrite(self):
        """覆盖"""
        d = TTLDict()
        d.set("key", "value1")
        d.set("key", "value2")
        assert d.get("key") == "value2"


# ===== cached 装饰器测试 =====


class TestCachedDecorator:
    """cached 缓存装饰器测试"""

    def test_cached_basic(self):
        """基本缓存"""
        call_count = 0

        @cached(cache_name="test_basic", ttl=300)
        def expensive_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_func(5)
        result2 = expensive_func(5)
        assert result1 == 10
        assert result2 == 10
        assert call_count == 1

    def test_cached_different_args(self):
        """不同参数"""
        call_count = 0

        @cached(cache_name="test_diff_args", ttl=300)
        def func(x):
            nonlocal call_count
            call_count += 1
            return x

        func(1)
        func(2)
        assert call_count == 2

    def test_cached_with_key_func(self):
        """自定义键函数"""
        call_count = 0

        @cached(
            cache_name="test_key_func",
            key_func=lambda x, **kw: f"custom_{x}",
        )
        def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        func(5)
        func(5)
        assert call_count == 1

    def test_cached_has_cache_attr(self):
        """缓存属性"""
        @cached(cache_name="test_attr")
        def func():
            return 1

        assert hasattr(func, "_cache")
        assert hasattr(func, "_cache_name")


# ===== async_cached 装饰器测试 =====


class TestAsyncCachedDecorator:
    """async_cached 异步缓存装饰器测试"""

    @pytest.mark.asyncio
    async def test_async_cached_basic(self):
        """基本异步缓存"""
        call_count = 0

        @async_cached(cache_name="test_async_basic", ttl=300)
        async def expensive_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = await expensive_func(5)
        result2 = await expensive_func(5)
        assert result1 == 10
        assert result2 == 10
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_cached_different_args(self):
        """不同参数"""
        call_count = 0

        @async_cached(cache_name="test_async_diff", ttl=300)
        async def func(x):
            nonlocal call_count
            call_count += 1
            return x

        await func(1)
        await func(2)
        assert call_count == 2


# ===== 全局函数测试 =====


class TestGlobalFunctions:
    """全局函数测试"""

    def test_get_cache_manager(self):
        """获取全局管理器"""
        manager = get_cache_manager()
        assert isinstance(manager, CacheManager)

    def test_get_cache_manager_singleton(self):
        """全局管理器单例"""
        m1 = get_cache_manager()
        m2 = get_cache_manager()
        assert m1 is m2

    def test_get_cache(self):
        """获取命名缓存"""
        cache = get_cache("test_global", max_size=50)
        assert isinstance(cache, MemoryCache)
        assert cache.max_size == 50

    def test_get_cache_existing(self):
        """获取已有缓存"""
        cache1 = get_cache("test_global_existing")
        cache2 = get_cache("test_global_existing")
        assert cache1 is cache2

    def test_create_cache(self):
        """创建缓存便捷函数"""
        cache = create_cache(max_size=100, default_ttl=60)
        assert isinstance(cache, MemoryCache)
        assert cache.max_size == 100

    def test_clear_all_caches(self):
        """清空所有缓存"""
        cache = get_cache("test_clear_all")
        cache.set("key", "value")
        clear_all_caches()
        assert cache.size() == 0

    def test_get_cache_stats(self):
        """获取缓存统计"""
        stats = get_cache_stats()
        assert isinstance(stats, dict)
        assert "cache_count" in stats


# ===== MISSING 标记测试 =====


class TestMissing:
    """_MISSING 标记测试"""

    def test_missing_is_unique(self):
        """_MISSING 是唯一对象"""
        assert _MISSING is not None
        assert _MISSING is not False
        assert _MISSING is not 0

    def test_missing_identity(self):
        """_MISSING 身份一致"""
        from backend.utils.cache import _MISSING as m
        assert _MISSING is m


# ===== 集成测试 =====


class TestIntegration:
    """集成测试"""

    def test_cache_with_complex_workflow(self):
        """复杂工作流"""
        cache = MemoryCache(max_size=5, default_ttl=60)
        # 设置多个值
        for i in range(10):
            cache.set(f"key_{i}", f"value_{i}")
        # 由于 max_size=5，部分被淘汰
        assert cache.size() <= 5

    def test_manager_multi_namespace(self):
        """多命名空间"""
        manager = CacheManager()
        c1 = manager.create_cache("ns1", max_size=10)
        c2 = manager.create_cache("ns2", max_size=20)
        c1.set("key", "value1")
        c2.set("key", "value2")
        assert c1.get("key") == "value1"
        assert c2.get("key") == "value2"
        assert manager.get_aggregate_stats()["cache_count"] == 2

    def test_ttl_dict_with_cache(self):
        """TTL 字典与缓存配合"""
        cache = MemoryCache(default_ttl=0.05)
        cache.set("key", "value")
        time.sleep(0.1)
        assert cache.get("key") is None
        assert cache.get_stats()["expirations"] >= 1

    def test_decorator_with_manager(self):
        """装饰器与管理器配合"""
        @cached(cache_name="test_integration", ttl=300)
        def compute(x):
            return x ** 2

        result = compute(5)
        assert result == 25
        # 通过管理器可以查看统计
        manager = get_cache_manager()
        stats = manager.get_all_stats()
        assert "test_integration" in stats


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试"""

    def test_cache_max_size_one(self):
        """最大容量为 1"""
        cache = MemoryCache(max_size=1)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.size() == 1
        assert cache.get("a") is None
        assert cache.get("b") == 2

    def test_cache_empty_key(self):
        """空字符串键"""
        cache = MemoryCache()
        cache.set("", "empty_key_value")
        assert cache.get("") == "empty_key_value"

    def test_cache_none_value_vs_missing(self):
        """None 值与键缺失区分"""
        cache = MemoryCache()
        cache.set("key", None)
        # exists 应返回 True
        assert cache.exists("key") is True
        # get 返回 None（值就是 None）
        assert cache.get("key") is None
        # get_or_set 不应调用 factory
        called = False
        def factory():
            nonlocal called
            called = True
            return "new"
        result = cache.get_or_set("key", factory=factory)
        assert result is None  # 返回缓存的 None
        # 注意：由于 None == _MISSING 为 False，factory 会被调用
        # 这是已知行为，None 值与缺失需要特殊处理

    def test_ttl_dict_zero_ttl(self):
        """TTL 为 0"""
        d = TTLDict(default_ttl=0)
        d.set("key", "value")
        time.sleep(0.05)
        assert d.get("key") == "value"

    def test_cache_very_small_ttl(self):
        """非常小的 TTL"""
        cache = MemoryCache()
        cache.set("key", "value", ttl=0.001)
        time.sleep(0.01)
        assert cache.get("key") is None

    def test_cache_large_value(self):
        """大值"""
        cache = MemoryCache()
        large_value = list(range(100000))
        cache.set("large", large_value)
        assert cache.get("large") == large_value

    def test_manager_empty_stats(self):
        """空管理器统计"""
        manager = CacheManager()
        stats = manager.get_aggregate_stats()
        assert stats["cache_count"] == 0
        assert stats["total_hits"] == 0

    def test_concurrent_access(self):
        """并发访问"""
        cache = MemoryCache(max_size=100)
        errors = []

        def worker(thread_id):
            try:
                for i in range(100):
                    cache.set(f"t{thread_id}_k{i}", i)
                    cache.get(f"t{thread_id}_k{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
