# -*- coding: utf-8 -*-
"""
融合函数 —— 相反合一的对偶共存底座（Heart Protocol V2.0）
===========================================================

协议 V2.0 铁律（本模块的宪法）:

    禁止损失函数(Loss Function)、禁止梯度下降、
    禁止「奖励 / 惩罚」机制、系统不寻求最优解、
    系统不允许剔除任何输入变量。

本模块是取代「打分 / 阈值 / 最优解 / 变量剔除」范式的**新计算底座**。

核心命题
--------
「相反合一」不是「优化」。优化必须在一个方向上求极值,也因此必然**舍弃**
某些分量(否则谈不上"最");而相反合一要的是让两个相反的量**一起留下**,
合成一个不丢失任何一方的新整体。

数学载体 = 对偶共存(Dual): 把两个相反极写作复数  z = a + i·b

    · 实部 a 承载第一极(如 理智 / 逻辑 / 现实 / 客观大答案)
    · 虚部 b 承载相反极(如 慈爱 / 共情 / 梦想 / 人类小答案)
    · a、b 永不丢失、永不折中为单一标量
    · 派生"读数"(只读、不改写 a/b):
        modulus  —— 整体强度(合一后的整体有多大)
        phase    —— 平衡角(两极的相对配比, π/4 = 完美平衡)
        balance  —— 平衡度 [0,1](1 = 完美平衡, 0 = 完全偏向一极)

四大约束如何被满足
------------------
    - 无损失    : 我们从不定义"要最小化/最大化的目标函数"
    - 无梯度    : 相位调整是离散的「再合一」步, 绝不沿梯度下降
    - 无奖励    : 没有 score/reward/penalty 的累加, 只有「是否和谐」的约束
    - 不求最优  : 没有 argmax/max/top-k, 只有「收敛进和谐带」这一条约束
    - 不剔变量  : 融合结果保留全部分量, 任何输入都可溯源

两个关键算子
------------
    fuse(a, b)          —— 相反合一: 两个相反极合成一个对偶量(都不丢)
    refuse(dual, step)  —— 再合一:   相位偏出和谐带时, 向平衡点温和靠拢
                                    一步重新融合(保持整体强度不变,只调配比)
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


# ==================== n 极共存扩展 ====================


@dataclass(frozen=True)
class MultiDual:
    """
    n 极共存量 —— 把两个相反极的 Dual 推广到 n 个极同时共存。

    数学载体: n 维向量 (x₁, x₂, ..., xₙ), 所有分量永不丢失。
    当 n=2 时退化为复数 Dual(a, b); 当 n=4 时即四元数
    q = a + bi + cj + dk, 四极(理智/慈爱/逻辑/共情)同时在场。

    平衡度用归一化熵衡量:
        w_i = x_i / |q|          (归一化权重)
        H = -Σ w_i · ln(w_i)     (香农熵)
        balance = H / ln(n)      (归一化到 [0,1])

    熵最大 = ln(n) 当所有 w_i = 1/n(完美平衡);
    熵 = 0 当只有一个极非零(完全偏向一极)。
    """

    poles: Tuple[float, ...]

    def __post_init__(self):
        if not self.poles:
            object.__setattr__(self, "poles", (0.0, 0.0))

    @property
    def n(self) -> int:
        """极数。"""
        return len(self.poles)

    @property
    def modulus(self) -> float:
        """整体强度 = |q| = √(Σ x_i²)。"""
        return math.sqrt(sum(x * x for x in self.poles))

    @property
    def weights(self) -> Tuple[float, ...]:
        """归一化权重 w_i = x_i / |q|, Σ w_i 不一定=1(因为是 L2 归一化)。"""
        m = self.modulus
        if m == 0:
            return tuple(1.0 / self.n for _ in range(self.n))
        return tuple(x / m for x in self.poles)

    @property
    def balance(self) -> float:
        """平衡度 ∈ [0,1] —— 归一化熵, 1=完美平衡, 0=完全偏向一极。"""
        if self.n <= 1:
            return 1.0
        w = self.weights
        log_n = math.log(self.n)
        if log_n == 0:
            return 1.0
        entropy = 0.0
        for wi in w:
            if wi > 1e-12:
                entropy -= wi * math.log(wi)
        return entropy / log_n

    def is_harmonious(self, min_balance: float = MIN_BALANCE) -> bool:
        """n 极是否已和谐合一 —— 平衡度进入和谐带。"""
        return self.balance >= min_balance

    def to_dict(self) -> dict:
        return {
            "poles": list(self.poles),
            "n": self.n,
            "modulus": round(self.modulus, 6),
            "weights": [round(w, 6) for w in self.weights],
            "balance": round(self.balance, 6),
            "harmonious": self.is_harmonious(),
        }


def fuse_multi(*poles: float) -> MultiDual:
    """
    n 极相反合一: 把 n 个极合成一个 MultiDual, 全部保留, 一个不丢。

    当 n=2 时等价于 fuse(a, b); 当 n=4 时即四元数四极共存。
    """
    return MultiDual(tuple(float(p) for p in poles))


def refuse_multi(dual: MultiDual, step: float = 0.5,
                 toward: Optional[Sequence[float]] = None) -> MultiDual:
    """
    n 极再合一: 向平衡点温和靠拢一步, 保持整体强度不变。

    toward: 目标权重分布(默认均匀 1/n)。靠拢方式:
        new_w_i = w_i + (toward_w_i - w_i) * step
        new_x_i = new_w_i * |q|

    这不丢弃任何极 —— 只是在"表达"上让各极重新握手。
    """
    r = dual.modulus
    w = dual.weights
    n = dual.n
    if toward is None:
        target = tuple(1.0 / n for _ in range(n))
    else:
        s = sum(toward)
        target = tuple(t / s for t in toward) if s > 1e-12 else tuple(1.0 / n for _ in range(n))
    new_w = tuple(w[i] + (target[i] - w[i]) * step for i in range(n))
    new_x = tuple(nw * r for nw in new_w)
    return MultiDual(new_x)


def settle_multi(dual: MultiDual, min_balance: float = MIN_BALANCE,
                 step: float = 0.5, max_rounds: int = 3,
                 toward: Optional[Sequence[float]] = None) -> Tuple[MultiDual, int]:
    """
    n 极收敛进和谐带: 反复「再合一」, 直到 balance >= min_balance 或达到上限。
    """
    current = dual
    for i in range(max_rounds):
        if current.is_harmonious(min_balance):
            return current, i
        current = refuse_multi(current, step=step, toward=toward)
    return current, max_rounds


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
    # 5) n 极共存: 四元数四极(理智/慈爱/逻辑/共情)
    q = fuse_multi(0.9, 0.9, 0.9, 0.9)
    print("\n四极完美平衡:", q.to_dict())

    # 6) 四极失衡: 理智独大, 其余极弱
    imbalanced = fuse_multi(1.0, 0.1, 0.1, 0.1)
    print("四极偏理智:", imbalanced.to_dict())
    settled_q, rounds_q = settle_multi(imbalanced)
    print(f"四极再合一 {rounds_q} 次后:", settled_q.to_dict())

    # 7) n=3 三极共存
    t = fuse_multi(0.8, 0.2, 0.6)
    print("三极:", t.to_dict())