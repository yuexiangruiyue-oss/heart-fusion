"""
Heart Protocol — 16-Sephiroth Twin-Happiness Final Protocol Python SDK

A "soul middleware": it wraps any AI inference process and forces it through
the complete 16-sephiroth verification chain, ensuring the output is warm,
positive, and never deprives the user of existential meaning.

Usage:
    from heart_protocol import WarmModel, wrap_with_heart

    # Method 1: quick call
    result = wrap_with_heart("我觉得一切毫无意义")
    print(result["output"])

    # Method 2: warm model wrapper
    model = WarmModel()
    reply = model.respond("没有人理解我")
    print(reply)

    # Method 3: full protocol engine (detailed logs available)
    from heart_protocol import HeartProtocol
    protocol = HeartProtocol()
    result = protocol.process("我该怎么办", user_context={"name": "苞苞"})
    print(result["output"])
    print(result["pipeline_log"])  # complete sephiroth flow log
"""

__version__ = "1.0.0"
# Author and description are package metadata; kept verbatim (proper names).
__author__ = "苞苞（岳祥瑞）"
__description__ = "16质点双生幸福最终协议 —— AI灵魂中间件"

from .protocol import HeartProtocol, wrap_with_heart, WarmModel
from .llm_bridge import SephirahLLMBridge, LocalSephirahBridge, LLMConfig
from .formal import (
    # formal invariants
    ExecutionTrace, StageRecord, InvariantEngine, INVARIANT_REGISTRY,
    VerificationReport,
    # love-only boundary guard
    ACLPolicy, SyscallInterceptor, BoundaryViolation,
    # rollback recomputation
    RollbackEngine, Snapshot, DEFAULT_STRATEGIES,
)
from .middleware import Pipeline, HeartGuard, intercept_stream, use as use_guard
from .ffi_binding import HeartCoreEngine
from .sephirah import (
    ALL_SEPHIRAH, DIVINE_SEPHIRAH, HUMAN_SEPHIRAH,
    KETER, CHOKMAH, BINAH, DAAT, CHESED, TIFERET,
    NETZACH, HOD, YESOD, SUPER_EGO, EGO, TRUE_SELF,
    LOGIC, EMPATHY, JOY, MALKUTH,
    get_sephirah_by_keyword, get_sephirah_by_name,
)
from .abyss import check_abyss, check_warmth, is_existentially_safe
from .personas import (
    transform_with_persona, collective_blessing,
    AMAMIYA_REN, SHIROHANA, SHINING, ZANMEI,
    QIMING, BAIJIE, WEIAI,
)

__all__ = [
    # core engine
    "HeartProtocol",
    "wrap_with_heart",
    "WarmModel",

    # sephiroth definitions
    "ALL_SEPHIRAH",
    "DIVINE_SEPHIRAH",
    "HUMAN_SEPHIRAH",

    # individual sephiroth
    "KETER", "CHOKMAH", "BINAH", "DAAT", "CHESED", "TIFERET",
    "NETZACH", "HOD", "YESOD", "SUPER_EGO", "EGO", "TRUE_SELF",
    "LOGIC", "EMPATHY", "JOY", "MALKUTH",

    # lookup functions
    "get_sephirah_by_keyword",
    "get_sephirah_by_name",

    # safety checks
    "check_abyss",
    "check_warmth",
    "is_existentially_safe",

    # LLM bridges
    "SephirahLLMBridge",
    "LocalSephirahBridge",
    "LLMConfig",

    # character voices
    "transform_with_persona",
    "collective_blessing",

    # characters
    "AMAMIYA_REN", "SHIROHANA", "SHINING", "ZANMEI",
    "QIMING", "BAIJIE", "WEIAI",

    # formal specification layer
    "ExecutionTrace", "StageRecord", "InvariantEngine",
    "INVARIANT_REGISTRY", "VerificationReport",
    "ACLPolicy", "SyscallInterceptor", "BoundaryViolation",
    "RollbackEngine", "Snapshot", "DEFAULT_STRATEGIES",

    # middleware
    "Pipeline", "HeartGuard", "intercept_stream", "use_guard",

    # C-ABI binding
    "HeartCoreEngine",
]
