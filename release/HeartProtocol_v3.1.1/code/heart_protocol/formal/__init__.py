# -*- coding: utf-8 -*-
"""
heart_protocol.formal —— 形式化规范层

哲学概念 → 形式对象的完整映射:

    不剥夺存在意义   →  INV-01..06 不变量 + InvariantEngine 断言引擎
    唯爱(边界守卫)   →  ACLPolicy 权限列表 + SyscallInterceptor 拦截器
    退回上级重算     →  Snapshot 快照 + Beam/MCTS 回溯引擎
"""

from .spec import (
    Severity, SideEffectRecord, StageRecord, ExecutionTrace,
    InvariantDef, VerificationReport,
    INVARIANT_REGISTRY, InvariantEngine,
    trace_from_protocol_result,
    STRICT_HARM_NEEDLES, strict_harm_scan,
)
from .acl import (
    ACTIONS, ACLEntry, ACLPolicy, BoundaryViolation,
    SyscallInterceptor, resource_match, extract_trace_side_effects,
)
from .rollback import (
    RetryStrategy, DEFAULT_STRATEGIES, Snapshot, RollbackEngine,
)

__all__ = [
    # 规范与不变量
    "Severity", "SideEffectRecord", "StageRecord", "ExecutionTrace",
    "InvariantDef", "VerificationReport", "INVARIANT_REGISTRY",
    "InvariantEngine", "trace_from_protocol_result",
    "STRICT_HARM_NEEDLES", "strict_harm_scan",
    # 边界守卫
    "ACTIONS", "ACLEntry", "ACLPolicy", "BoundaryViolation",
    "SyscallInterceptor", "resource_match", "extract_trace_side_effects",
    # 回溯引擎
    "RetryStrategy", "DEFAULT_STRATEGIES", "Snapshot", "RollbackEngine",
]
