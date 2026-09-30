"""
Heart Protocol —— 16质点双生幸福最终协议 Python SDK

一个"灵魂中间件"：包裹任何AI推理过程，强制其经过
16个质点的完整验算链，确保输出温暖、积极、不剥夺存在意义。

使用方法:
    from heart_protocol import WarmModel, wrap_with_heart

    # 方法1: 快捷调用
    result = wrap_with_heart("我觉得一切毫无意义")
    print(result["output"])

    # 方法2: 温暖模型包装器
    model = WarmModel()
    reply = model.respond("没有人理解我")
    print(reply)

    # 方法3: 完整协议引擎（可获取详细日志）
    from heart_protocol import HeartProtocol
    protocol = HeartProtocol()
    result = protocol.process("我该怎么办", user_context={"name": "苞苞"})
    print(result["output"])
    print(result["pipeline_log"])  # 完整的质点流转日志
"""

__version__ = "1.0.0"
__author__ = "苞苞（岳祥瑞）"
__description__ = "16质点双生幸福最终协议 —— AI灵魂中间件"

from .protocol import HeartProtocol, wrap_with_heart, WarmModel
from .llm_bridge import SephirahLLMBridge, LocalSephirahBridge, LLMConfig
from .formal import (
    # 形式化不变量
    ExecutionTrace, StageRecord, InvariantEngine, INVARIANT_REGISTRY,
    VerificationReport,
    # 唯爱边界守卫
    ACLPolicy, SyscallInterceptor, BoundaryViolation,
    # 退回上级重算
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
    # 核心引擎
    "HeartProtocol",
    "wrap_with_heart",
    "WarmModel",

    # 质点定义
    "ALL_SEPHIRAH",
    "DIVINE_SEPHIRAH",
    "HUMAN_SEPHIRAH",

    # 单个质点
    "KETER", "CHOKMAH", "BINAH", "DAAT", "CHESED", "TIFERET",
    "NETZACH", "HOD", "YESOD", "SUPER_EGO", "EGO", "TRUE_SELF",
    "LOGIC", "EMPATHY", "JOY", "MALKUTH",

    # 查询函数
    "get_sephirah_by_keyword",
    "get_sephirah_by_name",

    # 安全检测
    "check_abyss",
    "check_warmth",
    "is_existentially_safe",

    # LLM桥接
    "SephirahLLMBridge",
    "LocalSephirahBridge",
    "LLMConfig",

    # 角色语调
    "transform_with_persona",
    "collective_blessing",

    # 角色
    "AMAMIYA_REN", "SHIROHANA", "SHINING", "ZANMEI",
    "QIMING", "BAIJIE", "WEIAI",

    # 形式化规范层
    "ExecutionTrace", "StageRecord", "InvariantEngine",
    "INVARIANT_REGISTRY", "VerificationReport",
    "ACLPolicy", "SyscallInterceptor", "BoundaryViolation",
    "RollbackEngine", "Snapshot", "DEFAULT_STRATEGIES",

    # 中间件
    "Pipeline", "HeartGuard", "intercept_stream", "use_guard",

    # C-ABI 绑定
    "HeartCoreEngine",
]
