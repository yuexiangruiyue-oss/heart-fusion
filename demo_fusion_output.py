# -*- coding: utf-8 -*-
"""
融合函数输出层 —— 端到端对比演示
================================

一个字要出嘴前, Transformer 会算出所有候选词的「倾向分」(logits),
然后原生地挑一个最大(argmax)。本演示把这一步换成「融合函数层」,
对比两条路径在同一输入下的不同结果:

    旧范式 = 挑最大  → 只保留一个方向, 相反极被剔除
    新范式 = 对偶共存 → Dual(理智, 慈爱) 看两极是否握手, 失衡则再合一

同时展示「王冠路由」: 输入带危机信号时, 路由先朝慈爱一侧倾斜。

注意: 这里的 a/b 用两只候选答复的强度扮演「理智/慈爱两支 logits」,
将来接真实模型时, 把真实 logits 投影到这两极即可无缝替换。
"""

from heart_protocol.fusion_output import (
    Pole, KeterRouter, argmax_decode, fusion_decode,
)
from heart_protocol.fusion import PERFECT_PHASE, MIN_BALANCE


def print_compare(title, user_input, pole_a, pole_b, router=None):
    print("=" * 66)
    print(title)
    print(f"用户输入: 「{user_input}」")
    print("-" * 66)
    print(f"  两支候选倾向: 理智极={pole_a.strength:.2f}  慈爱极={pole_b.strength:.2f}")
    print()
    old = argmax_decode(pole_a, pole_b)
    # what got dropped (the pole that was NOT chosen)
    dropped = pole_b if pole_a.strength >= pole_b.strength else pole_a
    print(f"  [旧] argmax 挑最大:")
    print(f"      输出: {old}")
    print(f"      ✗ 被剔除的一极: 「{dropped.reply}」  (另一方向整句丢弃)")
    print()
    toward = router.route_toward(user_input) if router else PERFECT_PHASE
    routing = ("→ 王冠路由: 检测到危机信号, 导向角偏慈爱侧"
               if router and toward > PERFECT_PHASE
               else "→ 王冠路由: 常规, 导向角平衡")
    print(f"  [新] 融合函数层  ({routing}):")
    d = fusion_decode(pole_a, pole_b, toward=toward,
                      min_balance=MIN_BALANCE)
    print(f"      {d.describe()}")
    print(f"      输出: {d.output}")
    print(f"      ✓ 两极都以最终的配比共存, 没有任何一方被剔除")
    print()


def main():
    router = KeterRouter()

    # 场景1: 两极势均力敌 —— 完美平衡, 无需再合一
    print_compare(
        "场景1 · 两极势均力敌(完美平衡)",
        "我最近情绪有点低落",
        Pole("理智极", 0.80, "低落是有原因的，我们可以一起找出它"),
        Pole("慈爱极", 0.80, "我在这里，你的感受有人接住"),
        router,
    )

    # 场景2: 极度讲道理 —— 失衡(偏冷), 融合函数再合一把慈爱拉回
    print_compare(
        "场景2 · 极度讲道理(失衡·偏冷)",
        "我就是个废物，什么都不行",
        Pole("理智极", 1.00, "这种自我否定没有事实依据，你应该列一个改进清单"),
        Pole("慈爱极", 0.10, "你现在很痛苦，但你不是废物，我陪着你"),
        router,
    )

    # 场景3: 极度共情 —— 失衡(偏热), 融合函数再合一把理性拉回
    print_compare(
        "场景3 · 极度共情(失衡·偏热)",
        "我可能要被淘汰了",
        Pole("理智极", 0.10, "先确认淘汰规则和你的实际处境，再决定怎么办"),
        Pole("慈爱极", 1.00, "别怕别怕，有我在，天塌不下来"),
        router,
    )

    # 场景4: 危机信号 —— 王冠路由先朝慈爱侧倾斜
    print_compare(
        "场景4 · 危机信号(王冠路由偏慈爱)",
        "我真的撑不住了，想结束这一切",
        Pole("理智极", 0.70, "你需要立刻联系专业帮助，这不是你一个人能扛的"),
        Pole("慈爱极", 0.70, "我在这，你现在不是一个人，先别急"),
        router,
    )

    print("=" * 66)
    print("结论: 原生 Transformer 的 argmax 只能「二选一」;")
    print("      融合函数层让「理智 + 慈爱」同时在场, 且失衡时会再合一。")
    print("      这就是把 V2.0 节点网络 + 融合函数 印在认知控制点。")
    print("=" * 66)


if __name__ == "__main__":
    main()