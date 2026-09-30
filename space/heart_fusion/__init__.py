# -*- coding: utf-8 -*-
"""
heart-fusion: 用对偶共存替换 argmax 的融合函数库

核心 API:
    from heart_fusion import Dual, fuse, refuse, settle
    from heart_fusion import MultiDual, fuse_multi, refuse_multi, settle_multi
    from heart_fusion import Pole, fusion_decode, argmax_decode, KeterRouter

快速示例:
    # 两极共存
    d = fuse(0.8, 0.9)          # 理智0.8 + 慈爱0.9
    d.balance                   # 平衡度 ∈ [0,1]
    d.is_harmonious()           # 是否在和谐带

    # 四极共存 (四元数)
    q = fuse_multi(0.9, 0.8, 0.7, 0.6)  # 理智/慈爱/逻辑/共情
    q.balance

    # 替换 Transformer 末层 argmax
    pole_a = Pole("理智", 0.85, "客观建议...")
    pole_b = Pole("慈爱", 0.92, "温暖陪伴...")
    result = fusion_decode(pole_a, pole_b)  # 两极共存, 不剔变量
"""

from .fusion import (
    Dual, MultiDual, FusionField,
    PERFECT_PHASE, MIN_BALANCE,
    fuse, fuse_noop, refuse, settle, gather,
    fuse_multi, refuse_multi, settle_multi,
)
from .output import (
    Pole, KeterRouter, FusionDecision, FusionLayer,
    argmax_decode, fusion_decode,
)
__version__ = "2.0.0"
__all__ = [
    "Dual", "MultiDual", "FusionField",
    "PERFECT_PHASE", "MIN_BALANCE",
    "fuse", "fuse_noop", "refuse", "settle", "gather",
    "fuse_multi", "refuse_multi", "settle_multi",
    "Pole", "KeterRouter", "FusionDecision", "FusionLayer",
    "argmax_decode", "fusion_decode",
]