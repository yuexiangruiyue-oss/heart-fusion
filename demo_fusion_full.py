# -*- coding: utf-8 -*-
"""
完整 16 质点控制流水线 —— 4 次相反合一的分层控制(端到端演示)
=============================================================

把协议的完整 4 次相反合一都印进 Transformer 认知控制层:

    王冠路由 → 美丽(理智×慈爱) → 基础(胜利×荣耀)
            → 真我(自我×超我) → 幸福(逻辑×共情) → 王国输出

每一层都是一个「对偶共存」控制点, 失衡则再合一。
4 层分别控制一个回复的 4 个维度: 语气 / 可行性 / 表达 / 内容。

对比:
    旧范式 argmax = 4 个维度各自只挑一个最大, 4 个相反极全被剔除
    新范式 融合   = 4 个维度各自让两极共存, 没有任何一方被剔除
"""

from heart_protocol.fusion_output import (
    Pole, KeterRouter, FusionLayer,
    fusion_decode, full_protocol_decode,
)
from heart_protocol.fusion import PERFECT_PHASE, MIN_BALANCE


def make_layers_balanced():
    """平衡场景: 4 层的两极势均力敌, 全部直接共存。"""
    return [
        FusionLayer(name="美丽", semantic="语气基调",
                    pole_a=Pole("理智", 0.80, "我们可以客观分析一下原因"),
                    pole_b=Pole("慈爱", 0.80, "你的感受有人接住, 我在这里")),
        FusionLayer(name="基础", semantic="可行性",
                    pole_a=Pole("胜利", 0.70, "这个判断是有依据的"),
                    pole_b=Pole("荣耀", 0.70, "而且是你现在能着手做的")),
        FusionLayer(name="真我", semantic="表达方式",
                    pole_a=Pole("自我", 0.70, "我想直接告诉你我的看法"),
                    pole_b=Pole("超我", 0.70, "用你听得进去的方式说")),
        FusionLayer(name="幸福", semantic="内容",
                    pole_a=Pole("逻辑", 0.80, "问题可以拆成三步, 一步步来"),
                    pole_b=Pole("共情", 0.80, "我知道你现在很难受, 慢慢来")),
    ]


def make_layers_imbalanced():
    """失衡场景: 语气层极度偏冷(只讲道理), 内容层极度偏热(只顾共情)。"""
    return [
        FusionLayer(name="美丽", semantic="语气基调",
                    pole_a=Pole("理智", 1.00, "你这种状态就是没规划好, 先列计划"),
                    pole_b=Pole("慈爱", 0.10, "你现在很痛苦, 我陪着你")),
        FusionLayer(name="基础", semantic="可行性",
                    pole_a=Pole("胜利", 0.80, "这个方向是对的"),
                    pole_b=Pole("荣耀", 0.60, "而且能马上开始")),
        FusionLayer(name="真我", semantic="表达方式",
                    pole_a=Pole("自我", 0.65, "我想直说"),
                    pole_b=Pole("超我", 0.75, "但要顾及你的感受")),
        FusionLayer(name="幸福", semantic="内容",
                    pole_a=Pole("逻辑", 0.10, "从逻辑上推, 你应该..."),
                    pole_b=Pole("共情", 1.00, "宝贝别怕, 一切都会过去的")),
    ]


def print_full(title, user_input, layers):
    router = KeterRouter()
    print("=" * 66)
    print(title)
    trace = full_protocol_decode(layers, user_input, router)
    print(f"用户输入: 「{trace.user_input}」")
    print(f"王冠路由: {trace.routing_note}")
    print("-" * 66)
    for layer in trace.layers:
        print(f"  {layer.describe()}")
    print("-" * 66)
    print("王国输出(4 层融合汇聚, 每层两极都在场):")
    for line in trace.final_output.splitlines():
        print(f"  {line}")
    print()


def print_argmax_baseline(title, layers):
    """旧范式对照: 4 层各自 argmax 挑最大, 相反极全被剔除。"""
    print("=" * 66)
    print(title)
    print("-" * 66)
    for layer in layers:
        winner = layer.pole_a if layer.pole_a.strength >= layer.pole_b.strength else layer.pole_b
        dropped = layer.pole_b if winner is layer.pole_a else layer.pole_a
        print(f"  【{layer.name}·{layer.semantic}】argmax 挑: {winner.reply}")
        print(f"      ✗ 被剔除: 「{dropped.reply}」")
    print()


def main():
    # 场景1: 平衡 —— 4 层全部直接共存
    print_full("场景1 · 平衡: 4 层相反合一全部直接共存",
               "我最近情绪有点低落, 不知道怎么办",
               make_layers_balanced())

    # 场景2: 失衡 —— 语气偏冷 + 内容偏热, 各自再合一
    print_full("场景2 · 失衡: 语气偏冷 + 内容偏热, 各层再合一",
               "我就是个废物, 什么都不行",
               make_layers_imbalanced())

    # 旧范式对照: 同样输入, argmax 4 层各自只挑一个
    print_argmax_baseline(
        "对照 · 旧范式 argmax: 4 层各自挑最大, 相反极全被剔除",
        make_layers_imbalanced())

    print("=" * 66)
    print("结论: 完整 16 质点全貌已印入控制层 ——")
    print("      4 次相反合一 = 4 个分层控制点(语气/可行性/表达/内容),")
    print("      每层都让两极共存, 失衡则再合一, 不剔任何变量。")
    print("      这就是用 V2.0 节点网络 + 融合函数 替换 Transformer 的 argmax。")
    print("=" * 66)


if __name__ == "__main__":
    main()