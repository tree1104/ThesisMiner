"""缓存工具

提供内存缓存、TTL 管理、LRU 淘汰、缓存统计等能力。
支持同步与异步访问，线程安全。

核心组件：
    - CacheEntry: 缓存条目（值 + 过期时间 + 命中次数）
    - MemoryCache: 内存缓存（TTL + LRU 淘汰）
    - AsyncMemoryCache: 异步内存缓存
    - CacheStats: 缓存统计
    - cached: 缓存装饰器
    - CacheManager: 多缓存命名空间管理

设计原则：
    1. 线程安全：所有操作使用锁保护
    2. 可观测：内置命中率、淘汰数等统计
    3. 可配置：TTL、最大容量、淘汰策略均可配置
    4. 零依赖：仅使用 Python 标准库
"""
import asyncio
import functools
import hashlib
import json
import threading
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class CacheEntry:
    """缓存条目

    封装缓存值及其元数据（创建时间、过期时间、命中次数）。
    """
    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0  # 0 表示永不过期
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """判断是否过期。"""
        if self.expires_at == 0:
            return False
        return time.time() > self.expires_at

    def touch(self) -> None:
        """更新访问记录。"""
        self.access_count += 1
        self.last_accessed = time.time()


class CacheStats:
    """缓存统计

    记录命中、未命中、淘汰、过期等计数器。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0
        self._sets = 0
        self._deletes = 0
        self._errors = 0
        self._start_time = time.time()

    def record_hit(self) -> None:
        with self._lock:
            self._hits += 1

    def record_miss(self) -> None:
        with self._lock:
            self._misses += 1

    def record_eviction(self) -> None:
        with self._lock:
            self._evictions += 1

    def record_expiration(self) -> None:
        with self._lock:
            self._expirations += 1

    def record_set(self) -> None:
        with self._lock:
            self._sets += 1

    def record_delete(self) -> None:
        with self._lock:
            self._deletes += 1

    def record_error(self) -> None:
        with self._lock:
            self._errors += 1

    @property
    def hit_rate(self) -> float:
        """命中率。"""
        with self._lock:
            total = self._hits + self._misses
            return self._hits / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        """转换为字典。"""
        with self._lock:
            total = self._hits + self._misses
            uptime = time.time() - self._start_time
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
                "evictions": self._evictions,
                "expirations": self._expirations,
                "sets": self._sets,
                "deletes": self._deletes,
                "errors": self._errors,
                "total_requests": total,
                "uptime_seconds": uptime,
            }

    def reset(self) -> None:
        """重置统计。"""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._expirations = 0
            self._sets = 0
            self._deletes = 0
            self._errors = 0
            self._start_time = time.time()


class MemoryCache:
    """内存缓存

    支持 TTL（生存时间）与 LRU（最近最少使用）淘汰策略。
    线程安全，适用于多线程环境。

    使用示例：
        cache = MemoryCache(max_size=1000, default_ttl=300)
        cache.set("key", "value", ttl=60)
        value = cache.get("key")  # 返回 "value" 或 None
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,
        eviction_policy: str = "lru",
        cleanup_interval: float = 60.0,
    ):
        """初始化内存缓存。

        Args:
            max_size: 最大缓存条目数。
            default_ttl: 默认 TTL（秒），0 表示永不过期。
            eviction_policy: 淘汰策略（lru / fifo / lfu）。
            cleanup_interval: 过期清理间隔（秒）。
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.eviction_policy = eviction_policy
        self.cleanup_interval = cleanup_interval

        self._data: OrderedDict = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._last_cleanup = time.time()
        self._closed = False

    def _make_key(self, key: Any) -> str:
        """生成缓存键字符串。"""
        if isinstance(key, str):
            return key
        try:
            return json.dumps(key, sort_keys=True, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(key)

    def _estimate_size(self, value: Any) -> int:
        """估算值的字节大小。"""
        try:
            import sys
            return sys.getsizeof(value)
        except Exception:
            return 0

    def _evict(self) -> None:
        """执行淘汰（在锁内调用）。"""
        while len(self._data) >= self.max_size and self._data:
            if self.eviction_policy == "lru":
                # 移除最近最少访问的（OrderedDict 第一个）
                key, _ = self._data.popitem(last=False)
            elif self.eviction_policy == "lfu":
                # 移除访问次数最少的
                if not self._data:
                    break
                lfu_key = min(self._data.keys(), key=lambda k: self._data[k].access_count)
                self._data.pop(lfu_key)
            else:  # fifo
                key, _ = self._data.popitem(last=False)
            self._stats.record_eviction()

    def _cleanup_expired(self) -> None:
        """清理过期条目（在锁内调用）。"""
        now = time.time()
        if now - self._last_cleanup < self.cleanup_interval:
            return
        self._last_cleanup = now
        expired_keys = [k for k, v in self._data.items() if v.is_expired()]
        for key in expired_keys:
            self._data.pop(key, None)
            self._stats.record_expiration()

    def get(self, key: Any, default: Any = None) -> Any:
        """获取缓存值。

        Args:
            key: 缓存键。
            default: 键不存在或过期时的默认值。

        Returns:
            缓存值，不存在返回 default。
        """
        if self._closed:
            return default

        cache_key = self._make_key(key)
        with self._lock:
            self._cleanup_expired()
            if cache_key not in self._data:
                self._stats.record_miss()
                return default

            entry = self._data[cache_key]
            if entry.is_expired():
                self._data.pop(cache_key, None)
                self._stats.record_expiration()
                self._stats.record_miss()
                return default

            entry.touch()
            if self.eviction_policy == "lru":
                # 移到末尾（最近使用）
                self._data.move_to_end(cache_key)
            self._stats.record_hit()
            return entry.value

    def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        """设置缓存值。

        Args:
            key: 缓存键。
            value: 缓存值。
            ttl: 生存时间（秒），None 使用默认 TTL，0 表示永不过期。
        """
        if self._closed:
            return

        cache_key = self._make_key(key)
        effective_ttl = self.default_ttl if ttl is None else ttl
        expires_at = time.time() + effective_ttl if effective_ttl > 0 else 0.0

        entry = CacheEntry(
            value=value,
            expires_at=expires_at,
            size_bytes=self._estimate_size(value),
        )

        with self._lock:
            if cache_key in self._data:
                # 更新现有条目
                self._data[cache_key] = entry
                if self.eviction_policy == "lru":
                    self._data.move_to_end(cache_key)
            else:
                # 新增条目，可能需要淘汰
                if len(self._data) >= self.max_size:
                    self._evict()
                self._data[cache_key] = entry
            self._stats.record_set()

    def delete(self, key: Any) -> bool:
        """删除缓存键。

        Returns:
            键存在并删除返回 True，不存在返回 False。
        """
        cache_key = self._make_key(key)
        with self._lock:
            if cache_key in self._data:
                self._data.pop(cache_key, None)
                self._stats.record_delete()
                return True
            return False

    def exists(self, key: Any) -> bool:
        """判断键是否存在（且未过期）。"""
        cache_key = self._make_key(key)
        with self._lock:
            if cache_key not in self._data:
                return False
            entry = self._data[cache_key]
            if entry.is_expired():
                self._data.pop(cache_key, None)
                self._stats.record_expiration()
                return False
            return True

    def get_or_set(self, key: Any, factory: Callable, ttl: Optional[float] = None) -> Any:
        """获取或设置缓存值。

        若键不存在，调用 factory 生成值并缓存。

        Args:
            key: 缓存键。
            factory: 值工厂函数。
            ttl: 生存时间。

        Returns:
            缓存值或工厂生成的值。
        """
        value = self.get(key, default=_MISSING)
        if value is not _MISSING:
            return value
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def get_many(self, keys: list) -> dict:
        """批量获取缓存值。

        Args:
            keys: 键列表。

        Returns:
            {key: value} 字典（仅包含存在的键）。
        """
        result = {}
        for key in keys:
            value = self.get(key, default=_MISSING)
            if value is not _MISSING:
                result[key] = value
        return result

    def set_many(self, items: dict, ttl: Optional[float] = None) -> None:
        """批量设置缓存值。"""
        for key, value in items.items():
            self.set(key, value, ttl=ttl)

    def delete_many(self, keys: list) -> int:
        """批量删除缓存键。

        Returns:
            实际删除的键数。
        """
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        return count

    def clear(self) -> None:
        """清空所有缓存。"""
        with self._lock:
            count = len(self._data)
            self._data.clear()
            for _ in range(count):
                self._stats.record_delete()

    def size(self) -> int:
        """返回当前缓存条目数。"""
        with self._lock:
            return len(self._data)

    def keys(self) -> list:
        """返回所有缓存键。"""
        with self._lock:
            return list(self._data.keys())

    def values(self) -> list:
        """返回所有缓存值。"""
        with self._lock:
            return [entry.value for entry in self._data.values()]

    def items(self) -> list:
        """返回所有缓存键值对。"""
        with self._lock:
            return [(k, v.value) for k, v in self._data.items()]

    def get_stats(self) -> dict:
        """获取缓存统计。"""
        with self._lock:
            stats = self._stats.to_dict()
            stats["size"] = len(self._data)
            stats["max_size"] = self.max_size
            stats["eviction_policy"] = self.eviction_policy
            # 计算总字节大小
            total_bytes = sum(e.size_bytes for e in self._data.values())
            stats["total_bytes"] = total_bytes
            return stats

    def reset_stats(self) -> None:
        """重置统计。"""
        self._stats.reset()

    def cleanup(self) -> int:
        """手动清理过期条目。

        Returns:
            清理的条目数。
        """
        with self._lock:
            before = len(self._data)
            self._cleanup_expired()
            after = len(self._data)
            return before - after

    def close(self) -> None:
        """关闭缓存，释放资源。"""
        self._closed = True
        self.clear()

    def __contains__(self, key: Any) -> bool:
        return self.exists(key)

    def __len__(self) -> int:
        return self.size()

    def __getitem__(self, key: Any) -> Any:
        value = self.get(key, default=_MISSING)
        if value is _MISSING:
            raise KeyError(key)
        return value

    def __setitem__(self, key: Any, value: Any) -> None:
        self.set(key, value)

    def __delitem__(self, key: Any) -> None:
        if not self.delete(key):
            raise KeyError(key)


# 缺失标记（用于区分 None 值与键不存在）
_MISSING = object()


class AsyncMemoryCache:
    """异步内存缓存

    与 MemoryCache 功能相同，但使用 asyncio.Lock 适用于异步环境。
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,
        eviction_policy: str = "lru",
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.eviction_policy = eviction_policy
        self._data: OrderedDict = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = CacheStats()

    async def get(self, key: Any, default: Any = None) -> Any:
        cache_key = self._make_key(key)
        async with self._lock:
            if cache_key not in self._data:
                self._stats.record_miss()
                return default
            entry = self._data[cache_key]
            if entry.is_expired():
                self._data.pop(cache_key, None)
                self._stats.record_expiration()
                self._stats.record_miss()
                return default
            entry.touch()
            if self.eviction_policy == "lru":
                self._data.move_to_end(cache_key)
            self._stats.record_hit()
            return entry.value

    async def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        cache_key = self._make_key(key)
        effective_ttl = self.default_ttl if ttl is None else ttl
        expires_at = time.time() + effective_ttl if effective_ttl > 0 else 0.0
        entry = CacheEntry(value=value, expires_at=expires_at)
        async with self._lock:
            if len(self._data) >= self.max_size and cache_key not in self._data:
                self._evict()
            self._data[cache_key] = entry
            if self.eviction_policy == "lru":
                self._data.move_to_end(cache_key)
            self._stats.record_set()

    async def get_or_set(self, key: Any, factory: Callable, ttl: Optional[float] = None) -> Any:
        value = await self.get(key, default=_MISSING)
        if value is not _MISSING:
            return value
        value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
        await self.set(key, value, ttl=ttl)
        return value

    async def delete(self, key: Any) -> bool:
        cache_key = self._make_key(key)
        async with self._lock:
            if cache_key in self._data:
                self._data.pop(cache_key, None)
                self._stats.record_delete()
                return True
            return False

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()

    async def size(self) -> int:
        async with self._lock:
            return len(self._data)

    def _make_key(self, key: Any) -> str:
        if isinstance(key, str):
            return key
        try:
            return json.dumps(key, sort_keys=True, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(key)

    def _evict(self) -> None:
        while len(self._data) >= self.max_size and self._data:
            if self.eviction_policy == "lru":
                self._data.popitem(last=False)
            elif self.eviction_policy == "lfu":
                if not self._data:
                    break
                lfu_key = min(self._data.keys(), key=lambda k: self._data[k].access_count)
                self._data.pop(lfu_key)
            else:
                self._data.popitem(last=False)
            self._stats.record_eviction()

    def get_stats(self) -> dict:
        stats = self._stats.to_dict()
        stats["size"] = len(self._data)
        stats["max_size"] = self.max_size
        return stats


class CacheManager:
    """缓存管理器

    管理多个命名缓存命名空间，每个命名空间独立配置 TTL 与容量。
    提供统一的统计与清理接口。

    使用示例：
        manager = CacheManager()
        manager.create_cache("proposals", max_size=500, default_ttl=600)
        manager.get_cache("proposals").set("key", "value")
    """

    def __init__(self):
        self._caches: dict[str, MemoryCache] = {}
        self._lock = threading.Lock()

    def create_cache(
        self,
        name: str,
        max_size: int = 1000,
        default_ttl: float = 300.0,
        eviction_policy: str = "lru",
    ) -> MemoryCache:
        """创建命名缓存。

        Args:
            name: 缓存命名空间名称。
            max_size: 最大条目数。
            default_ttl: 默认 TTL。
            eviction_policy: 淘汰策略。

        Returns:
            MemoryCache 实例。
        """
        with self._lock:
            if name in self._caches:
                return self._caches[name]
            cache = MemoryCache(
                max_size=max_size,
                default_ttl=default_ttl,
                eviction_policy=eviction_policy,
            )
            self._caches[name] = cache
            return cache

    def get_cache(self, name: str) -> Optional[MemoryCache]:
        """获取命名缓存。"""
        with self._lock:
            return self._caches.get(name)

    def remove_cache(self, name: str) -> bool:
        """移除命名缓存。"""
        with self._lock:
            if name in self._caches:
                self._caches[name].close()
                del self._caches[name]
                return True
            return False

    def list_caches(self) -> list:
        """列出所有缓存命名空间。"""
        with self._lock:
            return list(self._caches.keys())

    def clear_all(self) -> None:
        """清空所有缓存。"""
        with self._lock:
            for cache in self._caches.values():
                cache.clear()

    def cleanup_all(self) -> int:
        """清理所有缓存的过期条目。

        Returns:
            总清理条目数。
        """
        with self._lock:
            return sum(cache.cleanup() for cache in self._caches.values())

    def get_all_stats(self) -> dict:
        """获取所有缓存的统计。"""
        with self._lock:
            return {name: cache.get_stats() for name, cache in self._caches.items()}

    def get_aggregate_stats(self) -> dict:
        """获取聚合统计。"""
        with self._lock:
            total_hits = 0
            total_misses = 0
            total_size = 0
            total_evictions = 0
            for cache in self._caches.values():
                stats = cache.get_stats()
                total_hits += stats["hits"]
                total_misses += stats["misses"]
                total_size += stats["size"]
                total_evictions += stats["evictions"]
            total_requests = total_hits + total_misses
            return {
                "cache_count": len(self._caches),
                "total_hits": total_hits,
                "total_misses": total_misses,
                "total_hit_rate": total_hits / total_requests if total_requests > 0 else 0.0,
                "total_size": total_size,
                "total_evictions": total_evictions,
                "caches": {name: cache.get_stats() for name, cache in self._caches.items()},
            }


# 全局缓存管理器实例
_global_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器。"""
    return _global_manager


def get_cache(name: str, **kwargs) -> MemoryCache:
    """获取或创建命名缓存。"""
    cache = _global_manager.get_cache(name)
    if cache is None:
        cache = _global_manager.create_cache(name, **kwargs)
    return cache


def cached(
    cache_name: str = "default",
    ttl: Optional[float] = None,
    key_func: Optional[Callable] = None,
    max_size: int = 1000,
):
    """缓存装饰器

    缓存函数返回值，基于参数生成缓存键。

    Args:
        cache_name: 缓存命名空间。
        ttl: 生存时间（秒）。
        key_func: 自定义缓存键生成函数。
        max_size: 缓存最大容量。

    使用示例：
        @cached(ttl=300)
        def expensive_computation(x, y):
            return x + y
    """

    def decorator(func: Callable) -> Callable:
        cache = get_cache(cache_name, max_size=max_size)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = _generate_cache_key(func.__name__, args, kwargs)

            value = cache.get(key, default=_MISSING)
            if value is not _MISSING:
                return value

            value = func(*args, **kwargs)
            cache.set(key, value, ttl=ttl)
            return value

        wrapper._cache = cache
        wrapper._cache_name = cache_name
        return wrapper

    return decorator


def async_cached(
    cache_name: str = "default_async",
    ttl: Optional[float] = None,
    key_func: Optional[Callable] = None,
    max_size: int = 1000,
):
    """异步缓存装饰器"""

    def decorator(func: Callable) -> Callable:
        cache = get_cache(cache_name, max_size=max_size)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = _generate_cache_key(func.__name__, args, kwargs)

            value = cache.get(key, default=_MISSING)
            if value is not _MISSING:
                return value

            value = await func(*args, **kwargs)
            cache.set(key, value, ttl=ttl)
            return value

        wrapper._cache = cache
        wrapper._cache_name = cache_name
        return wrapper

    return decorator


def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """生成函数缓存键。"""
    try:
        key_data = json.dumps(
            {"func": func_name, "args": args, "kwargs": kwargs},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
    except (TypeError, ValueError):
        key_data = f"{func_name}:{args}:{kwargs}"
    return hashlib.sha256(key_data.encode("utf-8")).hexdigest()[:32]


# ===== TTL 缓存变体 =====


class TTLDict:
    """TTL 字典

    简化的 TTL 字典，行为类似 dict 但每个键有生存时间。
    适用于简单场景，无需完整缓存的统计与淘汰功能。
    """

    def __init__(self, default_ttl: float = 300.0):
        self.default_ttl = default_ttl
        self._data: dict = {}
        self._expiry: dict = {}
        self._lock = threading.RLock()

    def __setitem__(self, key: Any, value: Any) -> None:
        self.set(key, value)

    def __getitem__(self, key: Any) -> Any:
        value = self.get(key, default=_MISSING)
        if value is _MISSING:
            raise KeyError(key)
        return value

    def __contains__(self, key: Any) -> bool:
        return self.exists(key)

    def __delitem__(self, key: Any) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._expiry.pop(key, None)
            else:
                raise KeyError(key)

    def __len__(self) -> int:
        with self._lock:
            self._cleanup()
            return len(self._data)

    def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        """设置值。"""
        effective_ttl = self.default_ttl if ttl is None else ttl
        with self._lock:
            self._data[key] = value
            if effective_ttl > 0:
                self._expiry[key] = time.time() + effective_ttl
            else:
                self._expiry.pop(key, None)

    def get(self, key: Any, default: Any = None) -> Any:
        """获取值。"""
        with self._lock:
            self._cleanup()
            if key in self._data:
                return self._data[key]
            return default

    def exists(self, key: Any) -> bool:
        """判断键是否存在。"""
        with self._lock:
            self._cleanup()
            return key in self._data

    def delete(self, key: Any) -> bool:
        """删除键。"""
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._expiry.pop(key, None)
                return True
            return False

    def clear(self) -> None:
        """清空。"""
        with self._lock:
            self._data.clear()
            self._expiry.clear()

    def keys(self) -> list:
        with self._lock:
            self._cleanup()
            return list(self._data.keys())

    def values(self) -> list:
        with self._lock:
            self._cleanup()
            return list(self._data.values())

    def items(self) -> list:
        with self._lock:
            self._cleanup()
            return list(self._data.items())

    def _cleanup(self) -> None:
        """清理过期键（在锁内调用）。"""
        now = time.time()
        expired = [k for k, exp in self._expiry.items() if now > exp]
        for key in expired:
            self._data.pop(key, None)
            self._expiry.pop(key, None)


# ===== 便捷函数 =====


def create_cache(max_size: int = 1000, default_ttl: float = 300.0) -> MemoryCache:
    """创建内存缓存的便捷函数。"""
    return MemoryCache(max_size=max_size, default_ttl=default_ttl)


def clear_all_caches() -> None:
    """清空全局所有缓存。"""
    _global_manager.clear_all()


def get_cache_stats() -> dict:
    """获取全局缓存聚合统计。"""
    return _global_manager.get_aggregate_stats()
