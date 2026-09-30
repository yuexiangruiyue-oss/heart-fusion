# -*- coding: utf-8 -*-
"""
heart_protocol.formal — formal specification layer

Complete mapping of philosophical concepts → formal objects:

    Preserve the meaning of existence  →  invariants INV-01..06 + InvariantEngine assertion engine
    Only-Love (boundary guard)          →  ACLPolicy allow-list + SyscallInterceptor interceptor
    Recompute from the parent stage     →  Snapshot checkpoints + Beam/MCTS rollback engine
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
    # Specification and invariants
    "Severity", "SideEffectRecord", "StageRecord", "ExecutionTrace",
    "InvariantDef", "VerificationReport", "INVARIANT_REGISTRY",
    "InvariantEngine", "trace_from_protocol_result",
    "STRICT_HARM_NEEDLES", "strict_harm_scan",
    # Boundary guard
    "ACTIONS", "ACLEntry", "ACLPolicy", "BoundaryViolation",
    "SyscallInterceptor", "resource_match", "extract_trace_side_effects",
    # Rollback engine
    "RetryStrategy", "DEFAULT_STRATEGIES", "Snapshot", "RollbackEngine",
]
