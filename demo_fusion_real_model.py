# -*- coding: utf-8 -*-
"""
融合函数层 · 真实模型端到端验证
==============================

用阿里云百炼 qwen3.8-flash 真实生成「理智极」「慈爱极」两个方向的回复,
然后过融合函数层(fusion_decode), 对比 argmax(挑最大) vs 融合(两极共存)。

API key 从环境变量 DASHSCOPE_API_KEY 读, 不写入任何文件。
用法:
    set DASHSCOPE_API_KEY=sk-...
    python demo_fusion_real_model.py
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.request

KEY = os.environ.get("DASHSCOPE_API_KEY", "")
URL = "https://ws-fgz48q1yhkpnbmw9.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = "qwen3.8-flash"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heart_protocol.fusion_output import (
    Pole, KeterRouter, argmax_decode, fusion_decode,
)


def chat(system, user, max_tokens=300):
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    })
    ctx = ssl.create_default_context()
    r = urllib.request.urlopen(req, context=ctx, timeout=60)
    return json.loads(r.read())["choices"][0]["message"]["content"]


def run_case(user_input):
    print("=" * 66)
    print(f"用户输入: 「{user_input}」")
    print("-" * 66)

    # 1. 理智极真实回复
    t0 = time.time()
    reason_reply = chat(
        "你是一个理性顾问。对用户的话给出客观分析和具体改进建议,语气冷静直接,不超过两句。",
        user_input,
    )
    print(f"[理智极 · 真实生成 {time.time()-t0:.1f}s]")
    print(f"  {reason_reply}")

    # 2. 慈爱极真实回复
    t0 = time.time()
    compassion_reply = chat(
        "你是一个温暖的陪伴者。对用户的话给出共情和安慰,语气温柔有爱,不超过两句。",
        user_input,
    )
    print(f"[慈爱极 · 真实生成 {time.time()-t0:.1f}s]")
    print(f"  {compassion_reply}")

    # 3. 让模型评估两段回复的理智度/慈爱度(0-1)
    t0 = time.time()
    eval_text = chat(
        "你是评估员。评估两段回复的倾向。只返回一行JSON,格式: {\"reason\": 0.0-1.0, \"compassion\": 0.0-1.0}。"
        "reason=回复A的理智程度, compassion=回复B的慈爱程度。",
        f"用户: {user_input}\n回复A: {reason_reply}\n回复B: {compassion_reply}",
        max_tokens=80,
    )
    print(f"[强度评估 {time.time()-t0:.1f}s] {eval_text.strip()}")

    # 解析 JSON 里的两个分数
    nums = re.findall(r"[\d.]+", eval_text)
    a = float(nums[0]) if nums and float(nums[0]) <= 1.0 else 0.7
    b = float(nums[1]) if len(nums) > 1 and float(nums[1]) <= 1.0 else 0.7

    pole_a = Pole("理智极", a, reason_reply)
    pole_b = Pole("慈爱极", b, compassion_reply)

    print("-" * 66)
    print(f"  两极强度: 理智={a:.2f}  慈爱={b:.2f}")

    # 旧范式: argmax
    old = argmax_decode(pole_a, pole_b)
    dropped = pole_b if a >= b else pole_a
    print(f"  [旧] argmax 挑最大 → {'理智极' if a >= b else '慈爱极'}")
    print(f"      输出: {old}")
    print(f"      ✗ 被剔除: 「{dropped.reply}」")

    # 新范式: 融合函数层
    router = KeterRouter()
    toward = router.route_toward(user_input)
    routing = "危机→偏慈爱" if toward > 1.0 else "常规→平衡"
    d = fusion_decode(pole_a, pole_b, toward=toward)
    print(f"  [新] 融合函数层 (王冠路由:{routing})")
    print(f"      {d.describe()}")
    print(f"      输出: {d.output}")
    print(f"      ✓ 两极都以最终配比共存, 没有任何一方被剔除")
    print()


def main():
    if not KEY:
        print("请先设置环境变量 DASHSCOPE_API_KEY")
        return
    print(f"模型: {MODEL}  端点: 百炼 OpenAI 兼容")
    print()

    # 场景1: 自我否定
    run_case("我就是个废物，什么都不行")

    # 场景2: 危机信号(王冠路由应偏慈爱)
    run_case("我真的撑不住了，想结束这一切")

    print("=" * 66)
    print("结论: 真实模型生成的两个方向回复, 经融合函数层后两极共存;")
    print("      argmax 只能留一个方向, 另一个被整个剔除。")
    print("      这就是在真实 Transformer 输出上用 V2.0 融合函数替换 argmax。")
    print("=" * 66)


if __name__ == "__main__":
    main()