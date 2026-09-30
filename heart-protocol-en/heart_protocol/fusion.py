# -*- coding: utf-8 -*-
"""
Fusion Function — Dual Coexistence Foundation for Opposite Unification (Heart Protocol V2.0)
==========================================================================================

Protocol V2.0 Iron Laws (the constitution of this module):

    No Loss Function. No Gradient Descent.
    No Reward / Penalty mechanisms. The system does not seek optima.
    The system never discards any input variable.

This module is the **new computational foundation** that replaces the
"scoring / threshold / optimization / variable pruning" paradigm.

Core Proposition
----------------
"Opposite unification" is NOT "optimization." Optimization must seek an
extremum in one direction, and therefore inevitably **discards** some
components (otherwise "optimal" is meaningless). Opposite unification
demands that two contrary quantities **both stay**, synthesizing a new
whole that loses neither side.

Mathematical Vehicle = Dual Coexistence: write two opposite poles as complex number  z = a + i*b

    - Real part a carries the first pole (e.g. reason / logic / reality / objective big answer)
    - Imaginary part b carries the opposite pole (e.g. compassion / empathy / dream / human small answer)
    - a, b are never lost, never collapsed into a single scalar
    - Derived "readings" (read-only, never overwrite a/b):
        modulus  — overall magnitude (how large the unified whole is)
        phase    — balance angle (relative ratio of two poles, pi/4 = perfect balance)
        balance  — balance degree [0,1] (1 = perfect balance, 0 = fully biased to one pole)

How the Four Constraints Are Satisfied
--------------------------------------
    - No loss    : We never define "an objective to minimize/maximize"
    - No gradient: Phase adjustment is a discrete "re-unification" step, never gradient descent
    - No reward  : No score/reward/penalty accumulation, only the constraint "is it harmonious"
    - No optimum : No argmax/max/top-k, only the single constraint "converge into the harmony band"
    - No pruning : Fusion results retain all components; every input is traceable

Two Key Operators
-----------------
    fuse(a, b)          — Opposite unification: two opposite poles synthesize a dual (neither lost)
    refuse(dual, step)  — Re-unification: when phase drifts outside the harmony band,
                          gently step toward the balance point and re-fuse
                          (preserving overall magnitude, only adjusting the ratio)
"""

import math
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

# 完美平衡角 = π/4 = 45°(两个相反极各占一半)
PERFECT_PHASE = math.pi / 4.0

# 默认和谐带(相对于平衡度): balance >= MIN_BALANCE 视为"相反已合一"
# 即两极少允许偏离平衡点一半 —— 既保留"有意义的情感倾斜",又不允许
# 任何一极把另一极排挤掉。
MIN_BALANCE = 0.5


@dataclass(frozen=True)
class Dual:
    """
    对偶共存量 —— 两个相反极的完整共存(复数  z = a + i·b)

    a、b 是两极的强度,两者都原样保留。派生属性(magnitude/phase/balance)
    只是"读数",它们不修改、也不丢弃 a 与 b —— 因而天然满足「不剔变量」。
    """

    a: float   # 第一极(实部)
    b: float   # 相反极(虚部)

    @property
    def modulus(self) -> float:
        """整体强度 = |z| = √(a² + b²)。两相合一的"整体有多大"。"""
        return math.hypot(self.a, self.b)

    @property
    def magnitude(self) -> float:
        """modulus 的别名(语义化)。"""
        return self.modulus

    @property
    def phase(self) -> float:
        """平衡角 θ = atan2(b, a) ∈ [0, π/2]。

        π/4(45°) 表示两极各占一半; 趋近 0 表示几乎只剩第一极(无情感),
        趋近 π/2 表示几乎只剩相反极(无理性)。
        """
        if self.a == 0 and self.b == 0:
            return PERFECT_PHASE          # 空对偶视为"尚未分化",记作完美平衡
        return math.atan2(self.b, self.a)

    @property
    def balance(self) -> float:
        """平衡度 ∈ [0, 1] —— 1 表示完美平衡, 0 表示完全偏向某一极。"""
        return 1.0 - abs(self.phase - PERFECT_PHASE) / PERFECT_PHASE

    @property
    def ratio(self) -> Tuple[float, float]:
        """两极的比例(归一化): 两个分量的相对配比, 均不丢失。"""
        m = self.modulus
        if m == 0:
            return (0.5, 0.5)
        return (self.a / m, self.b / m)

    def is_harmonious(self, min_balance: float = MIN_BALANCE) -> bool:
        """相反是否已和谐合一 —— 平衡度进入和谐带(唯一判定,非打分)。"""
        return self.balance >= min_balance

    def to_dict(self) -> dict:
        return {
            "a": self.a, "b": self.b,
            "modulus": self.modulus,
            "phase": round(self.phase, 6),
            "balance": round(self.balance, 6),
            "harmonious": self.is_harmonious(),
        }


def fuse(a: float, b: float) -> Dual:
    """
    相反合一: 把两个相反极合成一个对偶共存量。

    与「优化」的本质区别: 优化返回一个标量(在 a、b 之间取一个最优值,
    a、b 的信息在其间蒸发); fuse 返回一个**同时承载 a 与 b** 的对偶量,
    两者可无损读出 —— 没有任何输入变量被剔除。
    """
    return Dual(float(a), float(b))


def fuse_noop(first, second) -> Dual:
    """fuse 的语义别名,便于在协议代码里显式表达"相反合一"。"""
    return fuse(first, second)


def refuse(dual: Dual, step: float = 0.5, toward: float = PERFECT_PHASE) -> Dual:
    """
    再合一(re-fuse): 相位偏出和谐带时, 向平衡点温和靠拢一步后重新融合。

    这是替代「退回上级重算 + 换策略选最优」的新算子:
        · 保持整体强度 |z| 不变(整体没有变小)
        · 只把相位朝 toward(默认完美平衡角)挪动 step 比例
        · 不丢弃 a、b 任何一方 —— 只是在"表达"上让两极重新握手

    参数:
        dual  : 当前对偶量
        step  : 靠拢比例 ∈ (0, 1], 越接近 1 越果断地回到平衡
        toward: 目标平衡角(默认 π/4; 危机/情感场景可设为更偏共情的一侧)
    """
    r = dual.modulus
    new_phase = dual.phase + (toward - dual.phase) * step
    return Dual(r * math.cos(new_phase), r * math.sin(new_phase))


def settle(dual: Dual, min_balance: float = MIN_BALANCE,
           step: float = 0.5, max_rounds: int = 3,
           toward: float = PERFECT_PHASE) -> Tuple[Dual, int]:
    """
    收敛进和谐带: 反复「再合一」, 直到 balance >= min_balance 或达到上限。

    返回 (最终对偶量, 再合一次数)。整个过程无奖励、无最优解 ——
    唯一的停止条件是"相反已握手", 唯一的动作是"向平衡点靠拢"。
    """
    current = dual
    for i in range(max_rounds):
        if current.is_harmonious(min_balance):
            return current, i
        current = refuse(current, step=step, toward=toward)
    return current, max_rounds


@dataclass
class FusionField:
    """
    一个节点完成融合后的完整结果 —— 同时保留:

        sources : 该节点接收到的**全部**上游变量(原始值, 一个都不丢)
        dual    : 相反合一后派生的对偶量(当节点是"相反合一点"时)

    这保证「不剔除任何输入变量」: 即使后续只展示 dual 的结论,
    sources 里依旧完整保留每个上游分量的原始值, 可溯源、可复核。
    """

    key: str = ""                               # 节点名(质点关键词)
    sources: Tuple[float, ...] = field(default_factory=tuple)
    dual: Optional[Dual] = None

    @property
    def energy(self) -> float:
        """该节点的整体强度 = 有对偶取对偶模, 否则取全部分量的平方和开方。"""
        if self.dual is not None:
            return self.dual.modulus
        return math.sqrt(sum(v * v for v in self.sources)) if self.sources else 0.0

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "sources": list(self.sources),
            "dual": self.dual.to_dict() if self.dual else None,
        }


def gather(seed: float, *values: float) -> FusionField:
    """
    多路汇聚(不剔除): 把来自多条支流的信息并置进一个字段。

    与层级网络里的"过滤 + 阈值淘汰"相反, gather 把收到的每个值都保留下来,
    同时用 fuse(seed, 其余之和)派生一个对偶量作为"整体读数"。
    """
    rest = sum(values)
    return FusionField(
        sources=tuple([seed] + list(values)),
        dual=fuse(seed, rest),
    )


# ==================== 自测 ====================

if __name__ == "__main__":
    # 1) 相反合一: 理智 0.8 / 慈爱 0.8 → 完美平衡
    d = fuse(0.8, 0.8)
    print("完美平衡:", d.to_dict())

    # 2) 过于偏向理性(慈爱很弱) → 失衡, 需要再合一
    cold = fuse(1.0, 0.1)
    print("偏冷   :", cold.to_dict())
    warm, rounds = settle(cold)
    print(f"再合一 {rounds} 次后:", warm.to_dict())

    # 3) 不剔变量: 原始两极始终可读出
    z = fuse(3.0, 4.0)
    print(f"z = {z.a} + i·{z.b}; modulus={z.modulus} (勾股 3-4-5)")

    # 4) 多路汇聚不剔除
    g = gather(0.5, 0.6, 0.7, 0.8)
    print("汇聚字段:", g.to_dict())