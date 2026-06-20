"""优化模块

提供系统级性能优化能力，覆盖：
    - 多级缓存管理（内存/磁盘/分布式模拟）与多种淘汰算法
    - 数据库查询优化（SQL 分析、索引推荐、查询重写、N+1 消除）
    - 系统资源管理（CPU/内存/磁盘/网络监控、连接池、线程池、限流）

子模块：
    - cache_optimizer: 缓存优化器（LRU/LFU/FIFO/ARC、预热、穿透/雪崩防护）
    - query_optimizer: 查询优化器（SQL 分析、索引推荐、慢查询检测）
    - resource_manager: 资源管理器（资源监控、池管理、配额、限流）

公共导出：
    - CacheOptimizer: 缓存优化器
    - QueryOptimizer: 查询优化器
    - ResourceManager: 资源管理器
"""
from backend.optimization.cache_optimizer import (
    CacheOptimizer,
    CachePolicy,
    CacheLevel,
    CacheStats,
)
from backend.optimization.query_optimizer import (
    QueryOptimizer,
    QueryAnalysis,
    IndexRecommendation,
    QueryPlan,
)
from backend.optimization.resource_manager import (
    ResourceManager,
    ResourceSnapshot,
    ResourceQuota,
    PoolStats,
)

__all__ = [
    "CacheOptimizer",
    "CachePolicy",
    "CacheLevel",
    "CacheStats",
    "QueryOptimizer",
    "QueryAnalysis",
    "IndexRecommendation",
    "QueryPlan",
    "ResourceManager",
    "ResourceSnapshot",
    "ResourceQuota",
    "PoolStats",
]

__version__ = "8.0.0"
