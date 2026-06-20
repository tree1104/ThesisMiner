"""缓存优化器模块

提供多级缓存管理与优化能力，包括：
    - 多级缓存（内存缓存、磁盘缓存、分布式缓存模拟）
    - 多种淘汰算法（LRU、LFU、FIFO、ARC）
    - 缓存预热、缓存穿透防护、缓存雪崩防护
    - 缓存命中率监控、缓存大小控制、自动过期
    - 缓存统计、性能分析、优化建议

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可配置：容量、TTL、淘汰策略均可配置
    4. 可观测：内置命中率、淘汰数、延迟等统计
    5. 可扩展：支持新增淘汰算法与缓存层级
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import threading
import time
import uuid
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


# ===== 枚举 =====


class CachePolicy(str, Enum):
    """缓存淘汰策略。"""

    LRU = "lru"  # 最近最少使用
    LFU = "lfu"  # 最少使用频率
    FIFO = "fifo"  # 先进先出
    ARC = "arc"  # 自适应替换缓存


class CacheLevel(str, Enum):
    """缓存层级。"""

    MEMORY = "memory"    # 内存缓存
    DISK = "disk"        # 磁盘缓存
    DISTRIBUTED = "distributed"  # 分布式缓存（模拟）


# ===== 常量 =====


# 默认内存缓存容量（条目数）
DEFAULT_MEMORY_CAPACITY = 10000

# 默认磁盘缓存容量（字节）
DEFAULT_DISK_CAPACITY = 100 * 1024 * 1024  # 100MB

# 默认 TTL（秒），0 表示永不过期
DEFAULT_TTL = 3600

# 默认最大条目大小（字节），超过则不缓存
DEFAULT_MAX_ITEM_SIZE = 10 * 1024 * 1024  # 10MB

# 缓存穿透防护：空值缓存时间（秒）
DEFAULT_NULL_TTL = 60

# 缓存雪崩防护：TTL 随机抖动范围（比例）
DEFAULT_TTL_JITTER = 0.2

# 缓存预热批量大小
DEFAULT_WARMUP_BATCH_SIZE = 100

# 磁盘缓存默认目录
DEFAULT_DISK_CACHE_DIR = "data/cache"

# 统计采样间隔（秒）
DEFAULT_STATS_INTERVAL = 60.0

# ARC 算法：初始 T1 比例
DEFAULT_ARC_T1_RATIO = 0.5


# ===== 数据结构 =====


@dataclass
class CacheEntry:
    """缓存条目。

    Attributes:
        key: 缓存键。
        value: 缓存值。
        created_at: 创建时间戳。
        expires_at: 过期时间戳（0 表示永不过期）。
        access_count: 访问次数。
        last_accessed: 最后访问时间戳。
        size_bytes: 条目大小（字节）。
        level: 缓存层级。
        is_null: 是否为空值（穿透防护）。
    """

    key: str = ""
    value: Any = None
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0
    level: CacheLevel = CacheLevel.MEMORY
    is_null: bool = False

    def is_expired(self) -> bool:
        """判断是否过期。"""
        if self.expires_at == 0:
            return False
        return time.time() > self.expires_at

    def touch(self) -> None:
        """更新访问记录。"""
        self.access_count += 1
        self.last_accessed = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "size_bytes": self.size_bytes,
            "level": self.level.value,
            "is_null": self.is_null,
        }


@dataclass
class CacheStats:
    """缓存统计。

    Attributes:
        hits: 命中次数。
        misses: 未命中次数。
        sets: 写入次数。
        deletes: 删除次数。
        evictions: 淘汰次数。
        expirations: 过期次数。
        errors: 错误次数。
        null_hits: 空值命中次数（穿透防护）。
        start_time: 统计开始时间。
    """

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    expirations: int = 0
    errors: int = 0
    null_hits: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def total_requests(self) -> int:
        """总请求次数。"""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """命中率。"""
        total = self.total_requests
        return self.hits / total if total > 0 else 0.0

    @property
    def miss_rate(self) -> float:
        """未命中率。"""
        return 1.0 - self.hit_rate

    @property
    def uptime(self) -> float:
        """运行时长（秒）。"""
        return time.time() - self.start_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "errors": self.errors,
            "null_hits": self.null_hits,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 4),
            "miss_rate": round(self.miss_rate, 4),
            "uptime": round(self.uptime, 2),
        }

    def reset(self) -> None:
        """重置统计。"""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0
        self.expirations = 0
        self.errors = 0
        self.null_hits = 0
        self.start_time = time.time()


# ===== 淘汰算法实现 =====


class EvictionPolicy:
    """淘汰策略基类。"""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._lock = threading.RLock()

    def access(self, key: str) -> None:
        """记录键被访问。"""
        raise NotImplementedError

    def add(self, key: str) -> Optional[str]:
        """添加新键，返回需要淘汰的键（如有）。"""
        raise NotImplementedError

    def remove(self, key: str) -> None:
        """移除键。"""
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError

    def keys(self) -> list[str]:
        """返回所有键。"""
        raise NotImplementedError


class LRUPolicy(EvictionPolicy):
    """LRU（最近最少使用）淘汰策略。"""

    def __init__(self, capacity: int) -> None:
        super().__init__(capacity)
        self._items: OrderedDict[str, None] = OrderedDict()

    def access(self, key: str) -> None:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)

    def add(self, key: str) -> Optional[str]:
        with self._lock:
            evicted: Optional[str] = None
            if key in self._items:
                self._items.move_to_end(key)
                return None
            if len(self._items) >= self._capacity:
                evicted, _ = self._items.popitem(last=False)
            self._items[key] = None
            return evicted

    def remove(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._items.keys())


class LFUPolicy(EvictionPolicy):
    """LFU（最少使用频率）淘汰策略。"""

    def __init__(self, capacity: int) -> None:
        super().__init__(capacity)
        self._freq: dict[str, int] = {}
        self._freq_lists: dict[int, OrderedDict[str, None]] = defaultdict(OrderedDict)
        self._min_freq: int = 0

    def access(self, key: str) -> None:
        with self._lock:
            if key not in self._freq:
                return
            freq = self._freq[key]
            # 从当前频率列表移除
            self._freq_lists[freq].pop(key, None)
            if not self._freq_lists[freq] and freq == self._min_freq:
                self._min_freq += 1
            # 添加到更高频率列表
            new_freq = freq + 1
            self._freq[key] = new_freq
            self._freq_lists[new_freq][key] = None

    def add(self, key: str) -> Optional[str]:
        with self._lock:
            evicted: Optional[str] = None
            if key in self._freq:
                self.access(key)
                return None
            if len(self._freq) >= self._capacity:
                # 淘汰最小频率中最久未访问的
                if self._min_freq in self._freq_lists and self._freq_lists[self._min_freq]:
                    evicted, _ = self._freq_lists[self._min_freq].popitem(last=False)
                    self._freq.pop(evicted, None)
            # 新键频率为 1
            self._freq[key] = 1
            self._freq_lists[1][key] = None
            self._min_freq = 1
            return evicted

    def remove(self, key: str) -> None:
        with self._lock:
            if key in self._freq:
                freq = self._freq.pop(key)
                self._freq_lists[freq].pop(key, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._freq)

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._freq.keys())


class FIFOPolicy(EvictionPolicy):
    """FIFO（先进先出）淘汰策略。"""

    def __init__(self, capacity: int) -> None:
        super().__init__(capacity)
        self._queue: deque[str] = deque()
        self._set: set[str] = set()

    def access(self, key: str) -> None:
        # FIFO 不更新访问顺序
        pass

    def add(self, key: str) -> Optional[str]:
        with self._lock:
            evicted: Optional[str] = None
            if key in self._set:
                return None
            if len(self._queue) >= self._capacity:
                evicted = self._queue.popleft()
                self._set.discard(evicted)
            self._queue.append(key)
            self._set.add(key)
            return evicted

    def remove(self, key: str) -> None:
        with self._lock:
            if key in self._set:
                self._set.discard(key)
                # deque 不支持 O(1) 删除，重建
                self._queue = deque(k for k in self._queue if k != key)

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue)

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._queue)


class ARCPolicy(EvictionPolicy):
    """ARC（自适应替换缓存）淘汰策略。

    ARC 在 LRU 与 LFU 间自适应平衡，维护 T1（最近）与 T2（频繁）两个列表，
    以及 B1、B2 两个历史列表用于自适应调整。
    """

    def __init__(self, capacity: int) -> None:
        super().__init__(capacity)
        self._p: float = 0.0  # 目标 T1 大小
        self._t1: OrderedDict[str, None] = OrderedDict()  # 最近一次访问的缓存
        self._t2: OrderedDict[str, None] = OrderedDict()  # 多次访问的缓存
        self._b1: OrderedDict[str, None] = OrderedDict()  # T1 的淘汰历史
        self._b2: OrderedDict[str, None] = OrderedDict()  # T2 的淘汰历史

    def _total_size(self) -> int:
        return len(self._t1) + len(self._t2)

    def access(self, key: str) -> None:
        with self._lock:
            if key in self._t1:
                # 从 T1 提升到 T2
                self._t1.pop(key)
                self._t2[key] = None
            elif key in self._t2:
                # T2 中访问，移到末尾
                self._t2.move_to_end(key)

    def add(self, key: str) -> Optional[str]:
        with self._lock:
            evicted: Optional[str] = None
            # 情况 1：key 在 T1 或 T2 中
            if key in self._t1:
                self._t1.pop(key)
                self._t2[key] = None
                return None
            if key in self._t2:
                self._t2.move_to_end(key)
                return None

            # 情况 2：key 在 B1 中（最近被淘汰的）
            if key in self._b1:
                # 调整 p
                delta = max(len(self._b2) / max(len(self._b1), 1), 1)
                self._p = min(self._p + delta, self._capacity)
                self._replace(key, in_t2=False)
                self._b1.pop(key)
                self._t2[key] = None
                return self._get_evicted_if_needed()

            # 情况 3：key 在 B2 中
            if key in self._b2:
                delta = max(len(self._b1) / max(len(self._b2), 1), 1)
                self._p = max(self._p - delta, 0)
                self._replace(key, in_t2=True)
                self._b2.pop(key)
                self._t2[key] = None
                return self._get_evicted_if_needed()

            # 情况 4：新键
            if len(self._t1) + len(self._b1) == self._capacity:
                if len(self._t1) < self._capacity:
                    # 淘汰 B1 最旧
                    old_key, _ = self._b1.popitem(last=False)
                    self._replace(key, in_t2=False)
                else:
                    # T1 已满，淘汰 T1 最旧
                    evicted, _ = self._t1.popitem(last=False)
            elif len(self._t1) + len(self._b1) < self._capacity:
                total = self._total_size() + len(self._b1) + len(self._b2)
                if total >= self._capacity:
                    if total == 2 * self._capacity:
                        # 淘汰 B2 最旧
                        self._b2.popitem(last=False)
                    self._replace(key, in_t2=False)
            self._t1[key] = None
            return evicted

    def _replace(self, key: str, in_t2: bool) -> None:
        """执行替换操作。"""
        if len(self._t1) > 0 and (
            len(self._t1) > self._p or (in_t2 and len(self._t1) == int(self._p))
        ):
            # 从 T1 淘汰到 B1
            old_key, _ = self._t1.popitem(last=False)
            self._b1[old_key] = None
        else:
            # 从 T2 淘汰到 B2
            if self._t2:
                old_key, _ = self._t2.popitem(last=False)
                self._b2[old_key] = None

    def _get_evicted_if_needed(self) -> Optional[str]:
        """获取被淘汰的键（简化实现）。"""
        return None

    def remove(self, key: str) -> None:
        with self._lock:
            self._t1.pop(key, None)
            self._t2.pop(key, None)
            self._b1.pop(key, None)
            self._b2.pop(key, None)

    def __len__(self) -> int:
        with self._lock:
            return self._total_size()

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._t1.keys()) + list(self._t2.keys())


def create_policy(policy: CachePolicy, capacity: int) -> EvictionPolicy:
    """创建淘汰策略。

    Args:
        policy: 策略类型。
        capacity: 容量。

    Returns:
        淘汰策略实例。
    """
    if policy == CachePolicy.LRU:
        return LRUPolicy(capacity)
    elif policy == CachePolicy.LFU:
        return LFUPolicy(capacity)
    elif policy == CachePolicy.FIFO:
        return FIFOPolicy(capacity)
    elif policy == CachePolicy.ARC:
        return ARCPolicy(capacity)
    else:
        return LRUPolicy(capacity)


# ===== 缓存层级实现 =====


class MemoryCache:
    """内存缓存。

    支持 TTL、淘汰策略、大小控制、穿透防护。
    """

    def __init__(
        self,
        capacity: int = DEFAULT_MEMORY_CAPACITY,
        policy: CachePolicy = CachePolicy.LRU,
        default_ttl: float = DEFAULT_TTL,
        max_item_size: int = DEFAULT_MAX_ITEM_SIZE,
        enable_null_cache: bool = True,
        null_ttl: float = DEFAULT_NULL_TTL,
    ) -> None:
        """初始化内存缓存。

        Args:
            capacity: 最大条目数。
            policy: 淘汰策略。
            default_ttl: 默认 TTL（秒）。
            max_item_size: 单条目最大大小（字节）。
            enable_null_cache: 是否启用空值缓存（穿透防护）。
            null_ttl: 空值缓存 TTL。
        """
        self._lock = threading.RLock()
        self._capacity = capacity
        self._policy = create_policy(policy, capacity)
        self._default_ttl = default_ttl
        self._max_item_size = max_item_size
        self._enable_null_cache = enable_null_cache
        self._null_ttl = null_ttl
        self._entries: dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._total_size = 0

    def get(self, key: str) -> tuple[bool, Any]:
        """获取缓存值。

        Args:
            key: 缓存键。

        Returns:
            (是否命中, 值)。
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._stats.misses += 1
                return (False, None)
            if entry.is_expired():
                self._remove_entry(key)
                self._stats.expirations += 1
                self._stats.misses += 1
                return (False, None)
            if entry.is_null:
                self._stats.hits += 1
                self._stats.null_hits += 1
                return (True, None)
            entry.touch()
            self._policy.access(key)
            self._stats.hits += 1
            return (True, entry.value)

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> bool:
        """设置缓存值。

        Args:
            key: 缓存键。
            value: 缓存值。
            ttl: TTL（秒），None 使用默认值。

        Returns:
            是否成功。
        """
        with self._lock:
            try:
                size = self._estimate_size(value)
                if size > self._max_item_size:
                    self._stats.errors += 1
                    return False
                # 计算过期时间
                actual_ttl = ttl if ttl is not None else self._default_ttl
                if actual_ttl > 0:
                    # 雪崩防护：TTL 随机抖动
                    jitter = actual_ttl * DEFAULT_TTL_JITTER
                    actual_ttl += (time.time() % 1 - 0.5) * 2 * jitter
                    expires_at = time.time() + actual_ttl
                else:
                    expires_at = 0.0

                # 移除旧条目
                if key in self._entries:
                    self._remove_entry(key)

                # 淘汰
                evicted = self._policy.add(key)
                if evicted is not None:
                    self._remove_entry(evicted)
                    self._stats.evictions += 1

                entry = CacheEntry(
                    key=key,
                    value=value,
                    expires_at=expires_at,
                    size_bytes=size,
                    level=CacheLevel.MEMORY,
                    is_null=(value is None),
                )
                self._entries[key] = entry
                self._total_size += size
                self._stats.sets += 1
                return True
            except Exception:  # pragma: no cover
                self._stats.errors += 1
                return False

    def set_null(self, key: str, ttl: Optional[float] = None) -> bool:
        """设置空值缓存（穿透防护）。

        Args:
            key: 缓存键。
            ttl: TTL（秒）。

        Returns:
            是否成功。
        """
        if not self._enable_null_cache:
            return False
        actual_ttl = ttl if ttl is not None else self._null_ttl
        return self.set(key, None, ttl=actual_ttl)

    def delete(self, key: str) -> bool:
        """删除缓存。

        Args:
            key: 缓存键。

        Returns:
            是否删除成功。
        """
        with self._lock:
            if key in self._entries:
                self._remove_entry(key)
                self._policy.remove(key)
                self._stats.deletes += 1
                return True
            return False

    def clear(self) -> int:
        """清空缓存。

        Returns:
            清除的条目数。
        """
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            self._total_size = 0
            # 重建策略
            self._policy = create_policy(
                CachePolicy(self._policy.__class__.__name__.replace("Policy", "").lower())
                if hasattr(self._policy, "__class__")
                else CachePolicy.LRU,
                self._capacity,
            )
            return count

    def cleanup_expired(self) -> int:
        """清理过期条目。

        Returns:
            清理的条目数。
        """
        with self._lock:
            expired_keys = [
                k for k, e in self._entries.items() if e.is_expired()
            ]
            for key in expired_keys:
                self._remove_entry(key)
                self._stats.expirations += 1
            return len(expired_keys)

    def _remove_entry(self, key: str) -> None:
        """移除条目（内部方法，不加锁）。"""
        entry = self._entries.pop(key, None)
        if entry:
            self._total_size -= entry.size_bytes

    def _estimate_size(self, value: Any) -> int:
        """估算值大小。"""
        try:
            return len(pickle.dumps(value))
        except Exception:
            return 0

    def get_stats(self) -> dict[str, Any]:
        """获取统计。"""
        with self._lock:
            stats = self._stats.to_dict()
            stats.update({
                "size": len(self._entries),
                "capacity": self._capacity,
                "total_bytes": self._total_size,
                "utilization": len(self._entries) / self._capacity if self._capacity else 0,
            })
            return stats

    def get_keys(self) -> list[str]:
        """获取所有键。"""
        with self._lock:
            return list(self._entries.keys())

    def contains(self, key: str) -> bool:
        """是否包含键。"""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                self._remove_entry(key)
                return False
            return True


class DiskCache:
    """磁盘缓存。

    将缓存序列化到磁盘文件，支持 TTL 与大小控制。
    """

    def __init__(
        self,
        cache_dir: str = DEFAULT_DISK_CACHE_DIR,
        max_size: int = DEFAULT_DISK_CAPACITY,
        default_ttl: float = DEFAULT_TTL,
    ) -> None:
        """初始化磁盘缓存。

        Args:
            cache_dir: 缓存目录。
            max_size: 最大大小（字节）。
            default_ttl: 默认 TTL。
        """
        self._lock = threading.RLock()
        self._cache_dir = cache_dir
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._stats = CacheStats()
        self._index: dict[str, dict[str, Any]] = {}
        # 确保目录存在
        os.makedirs(self._cache_dir, exist_ok=True)
        self._load_index()

    def _get_file_path(self, key: str) -> str:
        """获取缓存文件路径。"""
        key_hash = hashlib.md5(key.encode("utf-8")).hexdigest()
        return os.path.join(self._cache_dir, f"{key_hash}.cache")

    def _load_index(self) -> None:
        """加载索引。"""
        index_path = os.path.join(self._cache_dir, "_index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
            except Exception:
                self._index = {}

    def _save_index(self) -> None:
        """保存索引。"""
        index_path = os.path.join(self._cache_dir, "_index.json")
        try:
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f)
        except Exception:  # pragma: no cover
            pass

    def get(self, key: str) -> tuple[bool, Any]:
        """获取缓存值。"""
        with self._lock:
            meta = self._index.get(key)
            if meta is None:
                self._stats.misses += 1
                return (False, None)
            # 检查过期
            if meta.get("expires_at", 0) > 0 and time.time() > meta["expires_at"]:
                self._remove(key)
                self._stats.expirations += 1
                self._stats.misses += 1
                return (False, None)
            # 读取文件
            file_path = self._get_file_path(key)
            if not os.path.exists(file_path):
                self._index.pop(key, None)
                self._stats.misses += 1
                return (False, None)
            try:
                with open(file_path, "rb") as f:
                    value = pickle.load(f)
                self._stats.hits += 1
                # 更新访问时间
                meta["last_accessed"] = time.time()
                meta["access_count"] = meta.get("access_count", 0) + 1
                return (True, value)
            except Exception:
                self._stats.errors += 1
                self._remove(key)
                return (False, None)

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> bool:
        """设置缓存值。"""
        with self._lock:
            try:
                file_path = self._get_file_path(key)
                data = pickle.dumps(value)
                size = len(data)
                # 检查容量
                self._evict_if_needed(size)
                # 写入文件
                with open(file_path, "wb") as f:
                    f.write(data)
                # 计算过期时间
                actual_ttl = ttl if ttl is not None else self._default_ttl
                expires_at = time.time() + actual_ttl if actual_ttl > 0 else 0
                # 更新索引
                self._index[key] = {
                    "file": file_path,
                    "size": size,
                    "created_at": time.time(),
                    "expires_at": expires_at,
                    "last_accessed": time.time(),
                    "access_count": 0,
                }
                self._save_index()
                self._stats.sets += 1
                return True
            except Exception:
                self._stats.errors += 1
                return False

    def delete(self, key: str) -> bool:
        """删除缓存。"""
        with self._lock:
            if key in self._index:
                self._remove(key)
                self._stats.deletes += 1
                return True
            return False

    def _remove(self, key: str) -> None:
        """移除条目（内部）。"""
        meta = self._index.pop(key, None)
        if meta:
            file_path = meta.get("file", self._get_file_path(key))
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

    def _evict_if_needed(self, required_size: int) -> None:
        """按需淘汰。"""
        current_size = self._get_total_size()
        while current_size + required_size > self._max_size and self._index:
            # 淘汰最久未访问的
            oldest_key = min(
                self._index.keys(),
                key=lambda k: self._index[k].get("last_accessed", 0),
            )
            self._remove(oldest_key)
            self._stats.evictions += 1
            current_size = self._get_total_size()

    def _get_total_size(self) -> int:
        """获取总大小。"""
        return sum(meta.get("size", 0) for meta in self._index.values())

    def cleanup_expired(self) -> int:
        """清理过期条目。"""
        with self._lock:
            expired = [
                k for k, m in self._index.items()
                if m.get("expires_at", 0) > 0 and time.time() > m["expires_at"]
            ]
            for key in expired:
                self._remove(key)
                self._stats.expirations += 1
            if expired:
                self._save_index()
            return len(expired)

    def clear(self) -> int:
        """清空缓存。"""
        with self._lock:
            count = len(self._index)
            for key in list(self._index.keys()):
                self._remove(key)
            self._save_index()
            return count

    def get_stats(self) -> dict[str, Any]:
        """获取统计。"""
        with self._lock:
            stats = self._stats.to_dict()
            stats.update({
                "size": len(self._index),
                "total_bytes": self._get_total_size(),
                "max_bytes": self._max_size,
                "utilization": self._get_total_size() / self._max_size if self._max_size else 0,
            })
            return stats


class DistributedCacheSimulator:
    """分布式缓存模拟器。

    模拟 Redis 风格的分布式缓存，提供一致性哈希与副本机制。
    """

    def __init__(
        self,
        node_count: int = 3,
        replica_count: int = 2,
        default_ttl: float = DEFAULT_TTL,
    ) -> None:
        """初始化分布式缓存模拟器。

        Args:
            node_count: 节点数。
            replica_count: 副本数。
            default_ttl: 默认 TTL。
        """
        self._lock = threading.RLock()
        self._node_count = node_count
        self._replica_count = replica_count
        self._default_ttl = default_ttl
        self._nodes: list[dict[str, CacheEntry]] = [{} for _ in range(node_count)]
        self._stats = CacheStats()
        # 一致性哈希环
        self._ring: dict[int, int] = {}  # hash -> node_index
        self._virtual_nodes = 150  # 每个物理节点的虚拟节点数
        self._build_ring()

    def _build_ring(self) -> None:
        """构建一致性哈希环。"""
        self._ring.clear()
        for node_idx in range(self._node_count):
            for vn in range(self._virtual_nodes):
                key = f"node-{node_idx}-vn-{vn}"
                h = self._hash(key)
                self._ring[h] = node_idx
        # 排序环
        self._sorted_hashes = sorted(self._ring.keys())

    def _hash(self, key: str) -> int:
        """一致性哈希。"""
        return int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16)

    def _get_node(self, key: str) -> int:
        """根据键获取节点。"""
        if not self._sorted_hashes:
            return 0
        h = self._hash(key)
        # 二分查找
        import bisect
        idx = bisect.bisect(self._sorted_hashes, h)
        if idx >= len(self._sorted_hashes):
            idx = 0
        return self._ring[self._sorted_hashes[idx]]

    def get(self, key: str) -> tuple[bool, Any]:
        """获取缓存值。"""
        with self._lock:
            node_idx = self._get_node(key)
            entry = self._nodes[node_idx].get(key)
            if entry is None:
                # 尝试副本
                for replica in range(1, self._replica_count):
                    replica_node = (node_idx + replica) % self._node_count
                    entry = self._nodes[replica_node].get(key)
                    if entry is not None:
                        node_idx = replica_node
                        break
            if entry is None:
                self._stats.misses += 1
                return (False, None)
            if entry.is_expired():
                self._nodes[node_idx].pop(key, None)
                self._stats.expirations += 1
                self._stats.misses += 1
                return (False, None)
            entry.touch()
            self._stats.hits += 1
            return (True, entry.value)

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> bool:
        """设置缓存值。"""
        with self._lock:
            try:
                node_idx = self._get_node(key)
                actual_ttl = ttl if ttl is not None else self._default_ttl
                expires_at = time.time() + actual_ttl if actual_ttl > 0 else 0
                entry = CacheEntry(
                    key=key,
                    value=value,
                    expires_at=expires_at,
                    level=CacheLevel.DISTRIBUTED,
                )
                # 写入主节点与副本
                for replica in range(self._replica_count):
                    target_node = (node_idx + replica) % self._node_count
                    self._nodes[target_node][key] = entry
                self._stats.sets += 1
                return True
            except Exception:
                self._stats.errors += 1
                return False

    def delete(self, key: str) -> bool:
        """删除缓存。"""
        with self._lock:
            deleted = False
            for node in self._nodes:
                if key in node:
                    node.pop(key, None)
                    deleted = True
            if deleted:
                self._stats.deletes += 1
            return deleted

    def get_stats(self) -> dict[str, Any]:
        """获取统计。"""
        with self._lock:
            stats = self._stats.to_dict()
            stats.update({
                "node_count": self._node_count,
                "replica_count": self._replica_count,
                "total_entries": sum(len(n) for n in self._nodes),
                "node_sizes": [len(n) for n in self._nodes],
            })
            return stats


# ===== 主优化器类 =====


class CacheOptimizer:
    """缓存优化器。

    管理多级缓存（内存/磁盘/分布式），提供统一的访问接口与优化能力。

    功能包括：
        - 多级缓存读写（自动层级穿透）
        - 多种淘汰算法（LRU/LFU/FIFO/ARC）
        - 缓存预热
        - 缓存穿透防护（空值缓存）
        - 缓存雪崩防护（TTL 抖动）
        - 缓存击穿防护（互斥锁）
        - 命中率监控与统计
        - 自动过期清理
        - 优化建议生成

    线程安全：所有公共方法通过 RLock 保护。

    典型用法：
        optimizer = CacheOptimizer()
        optimizer.set("key", value, ttl=3600)
        hit, value = optimizer.get("key")
        if not hit:
            value = compute_expensive()
            optimizer.set("key", value)
        stats = optimizer.get_stats()
    """

    def __init__(
        self,
        memory_capacity: int = DEFAULT_MEMORY_CAPACITY,
        disk_capacity: int = DEFAULT_DISK_CAPACITY,
        disk_cache_dir: str = DEFAULT_DISK_CACHE_DIR,
        policy: CachePolicy = CachePolicy.LRU,
        default_ttl: float = DEFAULT_TTL,
        enable_disk: bool = True,
        enable_distributed: bool = False,
        distributed_nodes: int = 3,
    ) -> None:
        """初始化缓存优化器。

        Args:
            memory_capacity: 内存缓存容量。
            disk_capacity: 磁盘缓存容量。
            disk_cache_dir: 磁盘缓存目录。
            policy: 淘汰策略。
            default_ttl: 默认 TTL。
            enable_disk: 是否启用磁盘缓存。
            enable_distributed: 是否启用分布式缓存。
            distributed_nodes: 分布式节点数。
        """
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._policy = policy

        # 多级缓存
        self._memory_cache = MemoryCache(
            capacity=memory_capacity,
            policy=policy,
            default_ttl=default_ttl,
        )
        self._disk_cache: Optional[DiskCache] = None
        if enable_disk:
            self._disk_cache = DiskCache(
                cache_dir=disk_cache_dir,
                max_size=disk_capacity,
                default_ttl=default_ttl,
            )
        self._distributed_cache: Optional[DistributedCacheSimulator] = None
        if enable_distributed:
            self._distributed_cache = DistributedCacheSimulator(
                node_count=distributed_nodes,
                default_ttl=default_ttl,
            )

        # 击穿防护：键级互斥锁
        self._key_locks: dict[str, threading.Lock] = {}
        self._key_locks_lock = threading.Lock()

        # 后台清理线程
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False

    def get(self, key: str) -> tuple[bool, Any]:
        """获取缓存值（多级穿透）。

        依次查询内存、磁盘、分布式缓存。

        Args:
            key: 缓存键。

        Returns:
            (是否命中, 值)。
        """
        with self._lock:
            # L1: 内存
            hit, value = self._memory_cache.get(key)
            if hit:
                return (True, value)
            # L2: 磁盘
            if self._disk_cache:
                hit, value = self._disk_cache.get(key)
                if hit:
                    # 回填内存
                    self._memory_cache.set(key, value)
                    return (True, value)
            # L3: 分布式
            if self._distributed_cache:
                hit, value = self._distributed_cache.get(key)
                if hit:
                    # 回填上级
                    self._memory_cache.set(key, value)
                    if self._disk_cache:
                        self._disk_cache.set(key, value)
                    return (True, value)
            return (False, None)

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        levels: Optional[list[CacheLevel]] = None,
    ) -> bool:
        """设置缓存值。

        Args:
            key: 缓存键。
            value: 缓存值。
            ttl: TTL（秒）。
            levels: 写入的层级（默认全部）。

        Returns:
            是否成功。
        """
        with self._lock:
            target_levels = levels or [CacheLevel.MEMORY, CacheLevel.DISK]
            success = True
            if CacheLevel.MEMORY in target_levels:
                success = self._memory_cache.set(key, value, ttl) and success
            if CacheLevel.DISK in target_levels and self._disk_cache:
                success = self._disk_cache.set(key, value, ttl) and success
            if CacheLevel.DISTRIBUTED in target_levels and self._distributed_cache:
                success = self._distributed_cache.set(key, value, ttl) and success
            return success

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[float] = None,
    ) -> Any:
        """获取或设置缓存（击穿防护）。

        若缓存未命中，调用 factory 生成值并写入缓存。
        使用键级互斥锁防止缓存击穿。

        Args:
            key: 缓存键。
            factory: 值生成函数。
            ttl: TTL。

        Returns:
            缓存值。
        """
        # 先尝试获取
        hit, value = self.get(key)
        if hit:
            return value
        # 获取键级锁
        with self._key_locks_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            key_lock = self._key_locks[key]
        # 双重检查
        with key_lock:
            hit, value = self.get(key)
            if hit:
                return value
            # 生成值
            try:
                value = factory()
            except Exception:
                # 穿透防护：缓存空值
                self._memory_cache.set_null(key)
                return None
            self.set(key, value, ttl)
            return value

    def delete(self, key: str) -> bool:
        """删除缓存（所有层级）。"""
        with self._lock:
            deleted = self._memory_cache.delete(key)
            if self._disk_cache:
                deleted = self._disk_cache.delete(key) or deleted
            if self._distributed_cache:
                deleted = self._distributed_cache.delete(key) or deleted
            return deleted

    def clear(self, level: Optional[CacheLevel] = None) -> dict[str, int]:
        """清空缓存。

        Args:
            level: 指定层级，None 清空所有。

        Returns:
            各层级清除数量。
        """
        with self._lock:
            result: dict[str, int] = {}
            if level is None or level == CacheLevel.MEMORY:
                result["memory"] = self._memory_cache.clear()
            if self._disk_cache and (level is None or level == CacheLevel.DISK):
                result["disk"] = self._disk_cache.clear()
            if self._distributed_cache and (level is None or level == CacheLevel.DISTRIBUTED):
                result["distributed"] = sum(
                    len(n) for n in self._distributed_cache._nodes
                )
                self._distributed_cache._nodes = [
                    {} for _ in range(self._distributed_cache._node_count)
                ]
            return result

    def warmup(
        self,
        items: dict[str, Any],
        ttl: Optional[float] = None,
        batch_size: int = DEFAULT_WARMUP_BATCH_SIZE,
    ) -> int:
        """缓存预热。

        批量写入缓存。

        Args:
            items: 键值对字典。
            ttl: TTL。
            batch_size: 批量大小。

        Returns:
            成功写入数。
        """
        with self._lock:
            count = 0
            keys = list(items.keys())
            for i in range(0, len(keys), batch_size):
                batch = keys[i:i + batch_size]
                for key in batch:
                    if self.set(key, items[key], ttl):
                        count += 1
            return count

    def warmup_with_loader(
        self,
        keys: list[str],
        loader: Callable[[str], Any],
        ttl: Optional[float] = None,
    ) -> int:
        """使用加载器预热缓存。

        Args:
            keys: 键列表。
            loader: 值加载函数。
            ttl: TTL。

        Returns:
            成功写入数。
        """
        with self._lock:
            count = 0
            for key in keys:
                try:
                    value = loader(key)
                    if value is not None:
                        if self.set(key, value, ttl):
                            count += 1
                except Exception:
                    continue
            return count

    def cleanup_expired(self) -> dict[str, int]:
        """清理所有层级的过期条目。

        Returns:
            各层级清理数量。
        """
        with self._lock:
            result: dict[str, int] = {}
            result["memory"] = self._memory_cache.cleanup_expired()
            if self._disk_cache:
                result["disk"] = self._disk_cache.cleanup_expired()
            # 分布式缓存清理
            if self._distributed_cache:
                count = 0
                for node in self._distributed_cache._nodes:
                    expired = [
                        k for k, e in node.items() if e.is_expired()
                    ]
                    for k in expired:
                        node.pop(k, None)
                        count += 1
                result["distributed"] = count
            return result

    def start_auto_cleanup(self, interval: float = DEFAULT_STATS_INTERVAL) -> None:
        """启动自动清理线程。

        Args:
            interval: 清理间隔（秒）。
        """
        with self._lock:
            if self._running:
                return
            self._running = True
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                args=(interval,),
                daemon=True,
            )
            self._cleanup_thread.start()

    def stop_auto_cleanup(self) -> None:
        """停止自动清理线程。"""
        with self._lock:
            self._running = False
            if self._cleanup_thread:
                self._cleanup_thread.join(timeout=5.0)
                self._cleanup_thread = None

    def _cleanup_loop(self, interval: float) -> None:
        """清理循环。"""
        while self._running:
            try:
                self.cleanup_expired()
            except Exception:  # pragma: no cover
                pass
            time.sleep(interval)

    def get_stats(self) -> dict[str, Any]:
        """获取综合统计。"""
        with self._lock:
            stats: dict[str, Any] = {
                "memory": self._memory_cache.get_stats(),
            }
            if self._disk_cache:
                stats["disk"] = self._disk_cache.get_stats()
            if self._distributed_cache:
                stats["distributed"] = self._distributed_cache.get_stats()
            # 综合命中率
            total_hits = sum(s.get("hits", 0) for s in stats.values())
            total_misses = sum(s.get("misses", 0) for s in stats.values())
            total = total_hits + total_misses
            stats["overall"] = {
                "total_hits": total_hits,
                "total_misses": total_misses,
                "hit_rate": round(total_hits / total, 4) if total > 0 else 0.0,
                "total_entries": sum(
                    s.get("size", 0) for s in stats.values()
                ),
            }
            return stats

    def get_optimization_suggestions(self) -> list[str]:
        """获取优化建议。

        基于当前统计生成缓存优化建议。

        Returns:
            建议列表。
        """
        with self._lock:
            suggestions: list[str] = []
            stats = self.get_stats()
            overall = stats.get("overall", {})
            hit_rate = overall.get("hit_rate", 0.0)

            # 命中率分析
            if hit_rate < 0.5:
                suggestions.append(
                    f"⚠️ 缓存命中率偏低（{hit_rate:.1%}），建议增大缓存容量或调整 TTL。"
                )
            elif hit_rate < 0.8:
                suggestions.append(
                    f"📋 缓存命中率中等（{hit_rate:.1%}），可考虑优化缓存策略。"
                )
            else:
                suggestions.append(
                    f"✅ 缓存命中率良好（{hit_rate:.1%}）。"
                )

            # 内存缓存分析
            mem_stats = stats.get("memory", {})
            mem_util = mem_stats.get("utilization", 0.0)
            if mem_util > 0.9:
                suggestions.append(
                    f"⚠️ 内存缓存利用率 {mem_util:.1%}，接近满载，建议增大容量。"
                )
            evictions = mem_stats.get("evictions", 0)
            if evictions > mem_stats.get("sets", 1) * 0.3:
                suggestions.append(
                    f"⚠️ 内存缓存淘汰频繁（{evictions} 次），"
                    "建议增大容量或调整淘汰策略。"
                )

            # 磁盘缓存分析
            if "disk" in stats:
                disk_stats = stats["disk"]
                disk_util = disk_stats.get("utilization", 0.0)
                if disk_util > 0.9:
                    suggestions.append(
                        f"⚠️ 磁盘缓存利用率 {disk_util:.1%}，建议清理或扩容。"
                    )

            # 过期分析
            expirations = mem_stats.get("expirations", 0)
            if expirations > 0 and expirations > mem_stats.get("hits", 1):
                suggestions.append(
                    "📋 过期清理频繁，建议适当延长 TTL。"
                )

            # 穿透防护分析
            null_hits = mem_stats.get("null_hits", 0)
            if null_hits > 0:
                suggestions.append(
                    f"✅ 穿透防护生效（空值命中 {null_hits} 次）。"
                )

            return suggestions

    def get_config(self) -> dict[str, Any]:
        """获取配置。"""
        with self._lock:
            return {
                "policy": self._policy.value,
                "default_ttl": self._default_ttl,
                "memory_capacity": self._memory_cache._capacity,
                "disk_enabled": self._disk_cache is not None,
                "distributed_enabled": self._distributed_cache is not None,
                "auto_cleanup_running": self._running,
            }


# ===== 模块级便捷函数 =====


_global_optimizer: Optional[CacheOptimizer] = None
_global_lock = threading.Lock()


def get_cache_optimizer() -> CacheOptimizer:
    """获取全局缓存优化器实例。

    Returns:
        全局 CacheOptimizer 实例。
    """
    global _global_optimizer
    with _global_lock:
        if _global_optimizer is None:
            _global_optimizer = CacheOptimizer()
        return _global_optimizer


def cached(
    key_fn: Optional[Callable[..., str]] = None,
    ttl: Optional[float] = None,
) -> Callable:
    """缓存装饰器。

    自动缓存函数返回值。

    Args:
        key_fn: 缓存键生成函数，默认基于参数。
        ttl: TTL。

    Returns:
        装饰器函数。
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            optimizer = get_cache_optimizer()
            # 生成缓存键
            if key_fn:
                cache_key = key_fn(*args, **kwargs)
            else:
                key_parts = [func.__name__] + [str(a) for a in args]
                key_parts += [f"{k}={v}" for k, v in sorted(kwargs.items())]
                cache_key = hashlib.md5(
                    "|".join(key_parts).encode("utf-8")
                ).hexdigest()

            return optimizer.get_or_set(
                cache_key, lambda: func(*args, **kwargs), ttl=ttl
            )
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
