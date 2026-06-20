"""ThesisMiner 监控与可观测性模块

提供系统健康监控、告警管理、安全审计三大能力，用于保障系统稳定运行
与满足合规审计要求。

子模块：
    - health_checker: 健康检查器（数据库/API/LLM/资源/存活/就绪）
    - alert_manager: 告警管理器（规则/去重/聚合/抑制/多渠道通知）
    - audit_logger: 审计日志器（用户操作/API调用/数据变更/合规报告）

设计原则：
    1. 线程安全：所有共享状态均使用锁保护，可在多线程环境使用
    2. 零侵入：模块可独立运行，不强制依赖外部存储
    3. 可降级：psutil 等可选依赖缺失时自动降级为占位实现
    4. 合规优先：审计日志具备防篡改与完整性保护能力
"""
from backend.monitoring.health_checker import HealthChecker, get_health_checker
from backend.monitoring.alert_manager import AlertManager, get_alert_manager
from backend.monitoring.audit_logger import AuditLogger, get_audit_logger

__all__ = [
    # 健康检查
    "HealthChecker",
    "get_health_checker",
    # 告警管理
    "AlertManager",
    "get_alert_manager",
    # 审计日志
    "AuditLogger",
    "get_audit_logger",
]
