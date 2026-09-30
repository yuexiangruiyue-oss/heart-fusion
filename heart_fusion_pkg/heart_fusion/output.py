# -*- coding: utf-8 -*-
"""
融合函数输出层 —— 印在 Transformer 认知控制点(V2.0)
====================================================

Transformer 的最后一步是: 算出每个候选词的倾向分(logits), 然后
argmax / softmax 采样「挑一个最大值」。这一步正是 V2.0 铁律要废除的
「求最优解 / 剔除变量」—— 挑最大意味着把另一极的候选整个丢弃。

本模块把这一步替换为「融合函数层」:

    旧范式  logits → argmax          挑最高分 → 只剩一个方向, 相反极被剔除
    新范式  logits → 对偶 → 融合     Dual(a, b) → 看两极是否握手(和谐带),
                                     失衡则 refuse 再合一 → 两极都完整保留

其中:
    a = 理智极(逻辑 / 客观 / 现实 / 「大答案」)的倾向强度
    b = 慈爱极(共情 / 温柔 / 情感 / 「小答案」)的倾向强度

王冠路由(Keter Router) 印在更早一层 —— 输入进来时, 由「王冠」决定
这一句初始「走理智线还是走慈爱线」, 也就是融合前的初始导向角 toward。

接口说明(接真实模型的替换点):
    真实模型最后一层的 logits 向量, 投影到「理智 / 慈爱」两个方向后,
    分别得到 a 与 b, 然后交给本模块的 fusion_decode。
    这里用两只「候选答复」的强度来扮演 a、b, 语义与真实 logits 完全一致。
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .fusion import (Dual, PERFECT_PHASE, MIN_BALANCE,
                     fuse, refuse, settle)


# ==================== 两个对立极 ====================


@dataclass
class Pole:
    """一个对立极 —— 承载该方向的候选答复与其倾向强度(相当于 logits 的一支)。"""

    name: str        # 极名, 如 "理智极" / "慈爱极"
    strength: float  # 该极的整体倾向强度 (>=0, 越大表示 logits 越偏向这一极)
    reply: str       # 若「只选这一极」时会给出的候选答复文本

    def __post_init__(self):
        self.strength = float(self.strength)


# ==================== 王冠路由(第③层: 门控) ====================


class KeterRouter:
    """
    王冠路由 —— 印在注意力层之前的门控: 决定这一句初始走哪条线。

    王冠在协议里是「路由」, 它不自己产出内容, 而是决定信息该先流向
    理智线还是慈爱线。这里它把「输入的状态」翻译成一个初始导向角
    toward —— 危机 / 倾诉场景偏向慈爱一侧, 让融合前的初始状态先朝
    「接住情绪」的方向倾斜。
    """

    # 危机 / 倾诉 / 无力感的信号词 —— 命中则路由偏向慈爱极
    CRISIS_HINTS = (
        "结束", "不想活", "撑不住", "崩溃", "绝望", "好累", "没人",
        "活不下去", "想死", "扛不住", "孤独", "无力",
    )

    def route_toward(self, user_input: str) -> float:
        """
        返回初始导向角 toward ∈ [0, π/2]。
        默认 π/4(平衡); 检测到危机信号 → 偏向慈爱极(> π/4)。
        """
        if any(hint in user_input for hint in self.CRISIS_HINTS):
            return PERFECT_PHASE + 0.30   # 慈爱一侧倾斜约 17°
        return PERFECT_PHASE              # 平衡


# ==================== 融合函数层(第②层: 输出控制) ====================


def argmax_decode(pole_a: Pole, pole_b: Pole) -> str:
    """
    旧范式: 挑最强的一极, 只输出它的答复 —— 另一极被整体剔除。

    这就是 Transformer 原生的 «argmax(挑选大)», V2.0 要废除的动作。
    """
    winner = pole_a if pole_a.strength >= pole_b.strength else pole_b
    return winner.reply


@dataclass
class FusionDecision:
    """融合函数层的决策结果 —— 与 argmax 的「单一答案」相对。"""

    a: float          # 理智极强度
    b: float          # 慈爱极强度
    dual: Dual        # 直接合一后的对偶量
    settled: Dual     # (若失衡)再合一后的对偶量
    rounds: int       # 再合一次数(0 = 本来就在和谐带)
    harmonious: bool  # 最终是否握手
    output: str       # 最终输出文本(两极共存的结果)

    def describe(self) -> str:
        d, s = self.dual, self.settled
        return (f"理智 {self.a:.2f} / 慈爱 {self.b:.2f} → "
                f"|z|={d.modulus:.2f} balance={d.balance:.2f} "
                f"[{'和谐' if d.is_harmonious() else '失衡'}]"
                + ("" if self.rounds == 0
                   else f" → 再合一 {self.rounds} 次 → balance={s.balance:.2f}"
                        f" [{'和谐' if self.harmonious else '仍失衡'}]"))


def _compose_output(settled: Dual, pole_a: Pole, pole_b: Pole) -> str:
    """
    按最终配比把两极的答复「共存」成一句话 —— 不是二选一, 而是两者都在场。

    平衡(ratio≈0.5/0.5): 两句平等并列。
    偏理性: 大答案为主, 温柔作为收尾兜底。
    偏慈爱: 温柔为主, 理性作为托底不缺席。
    """
    ra, rb = settled.ratio
    if abs(ra - rb) < 0.2:
        return f"{pole_a.reply}；同时，{pole_b.reply}"
    if ra > rb:
        return f"{pole_a.reply}。不过，{pole_b.reply}"
    return f"{pole_b.reply}。而且，{pole_a.reply}"


def fusion_decode(pole_a: Pole, pole_b: Pole,
                  toward: float = PERFECT_PHASE,
                  min_balance: float = MIN_BALANCE,
                  step: float = 0.5,
                  max_rounds: int = 3) -> FusionDecision:
    """
    融合函数层 —— 取代 argmax 的输出控制点。

    它不挑「哪一极分更高」, 而是:
        1. fuse(a, b)     把两极合成一个对偶量(谁都不丢)
        2. 看 balance 是否进入和谐带
        3. 失衡则 refuse/settle 再合一, 只「向平衡点靠拢」, 不增减任何分量
        4. 用最终配比把两极的答复一起呈现 —— 输出里两极都在场

    参数 toward 来自王冠路由: 危机场景会先朝慈爱一侧倾斜, 再合一。
    """
    a, b = pole_a.strength, pole_b.strength
    dual = fuse(a, b)
    settled, rounds = settle(dual, min_balance=min_balance,
                             step=step, max_rounds=max_rounds,
                             toward=toward)
    harmonious = settled.is_harmonious(min_balance)
    output = _compose_output(settled, pole_a, pole_b)
    return FusionDecision(a=a, b=b, dual=dual, settled=settled,
                          rounds=rounds, harmonious=harmonious, output=output)


# ==================== 完整 4 次相反合一(16 质点全貌) ====================


@dataclass
class FusionLayer:
    """
    一次相反合一的分层控制点 —— 16 质点全貌中的一层。

    协议有 4 次相反合一, 每次都是一个「对偶共存」控制点:
        王丽 = 理智 × 慈爱   (第1次: 控制语气基调)
        基础 = 胜利 × 荣耀   (第2次: 控制可行性)
        真我 = 自我 × 超我   (第3次: 控制表达方式)
        幸福 = 逻辑 × 共情   (第4次: 控制内容)
    """

    name: str                                   # 合一点名(美丽/基础/真我/幸福)
    pole_a: Pole                                # 第一极
    pole_b: Pole                                # 相反极
    semantic: str                               # 这层控制什么(语气/可行性/表达/内容)
    decision: Optional[FusionDecision] = None   # 运行后填充

    def describe(self) -> str:
        d = self.decision
        if d is None:
            return f"【{self.name}·{self.semantic}】未运行"
        return f"【{self.name}·{self.semantic}】{d.describe()}"


@dataclass
class FullProtocolTrace:
    """
    完整 16 质点控制流水线的运行轨迹。

    信息流向: 王冠路由 → 4 层相反合一 → 王国输出
    每一层都是对偶共存控制点, 失衡则再合一; 没有任何一极被剔除。
    """

    user_input: str
    toward: float                   # 王冠路由导向角
    routing_note: str               # 路由说明
    layers: List[FusionLayer]       # 4 层相反合一
    final_output: str               # 王国输出(4层汇聚)

    def describe(self) -> str:
        lines = [f"用户输入: 「{self.user_input}」",
                 f"王冠路由: {self.routing_note}"]
        for layer in self.layers:
            lines.append(layer.describe())
        lines.append(f"王国输出:\n{self.final_output}")
        return "\n".join(lines)


def full_protocol_decode(layers: List[FusionLayer],
                         user_input: str,
                         router: KeterRouter,
                         min_balance: float = MIN_BALANCE) -> FullProtocolTrace:
    """
    完整 16 质点控制流水线 —— 4 次相反合一的分层控制。

    王冠路由先决定导向角 toward, 然后 4 层相反合一依次执行,
    每层都用 fusion_decode(对偶共存 + 失衡再合一),
    最后王国把 4 层融合结果汇聚成最终输出。

    与单层 argmax 的本质区别: 不是「挑一个最大」, 而是
    「4 个维度各自让两极共存」—— 语气/可行性/表达/内容,
    每个维度都不剔变量。
    """
    toward = router.route_toward(user_input)
    routing_note = ("检测到危机信号, 导向角偏慈爱侧"
                    if toward > PERFECT_PHASE
                    else "常规, 导向角平衡")

    for layer in layers:
        layer.decision = fusion_decode(
            layer.pole_a, layer.pole_b,
            toward=toward, min_balance=min_balance,
        )

    # 王国: 4 层融合汇聚(不剔除任何一层)
    parts = []
    for layer in layers:
        parts.append(f"【{layer.name}·{layer.semantic}】{layer.decision.output}")
    final_output = "\n".join(parts)

    return FullProtocolTrace(
        user_input=user_input,
        toward=toward,
        routing_note=routing_note,
        layers=layers,
        final_output=final_output,
    )


# ==================== 自测 ====================

if __name__ == "__main__":
    # 完美平衡: 两极各占一半, 无需再合一
    ok = fusion_decode(Pole("理智", 0.8, "你可以把问题拆开，一步步解决"),
                       Pole("慈爱", 0.8, "你已经很努力了，慢慢来"))
    print("完美平衡 →", ok.describe(), "\n  输出:", ok.output, "\n")

    # 偏冷(只讲道理): 失衡应被再合一拉回慈爱
    cold = fusion_decode(Pole("理智", 1.0, "你这种状态就是没规划好，先列计划"),
                         Pole("慈爱", 0.1, "我知道你现在很难受，我陪着你"))
    print("偏冷     →", cold.describe(), "\n  输出:", cold.output, "\n")

    # 偏热(只顾共情): 失衡应被再合一拉回一点理性
    hot = fusion_decode(Pole("理智", 0.1, "这不是你的错，我们需要看清楚事实"),
                        Pole("慈爱", 1.0, "宝贝别怕，一切都会过去的"))
    print("偏热     →", hot.describe(), "\n  输出:", hot.output, "\n")