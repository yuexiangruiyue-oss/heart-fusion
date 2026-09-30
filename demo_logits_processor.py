# -*- coding: utf-8 -*-
"""
LogitsProcessor 集成方式 demo
============================

对比两种方式:
  A) monkey-patch 方式 (web_fusion_v5.py 用的) — 修改 Qwen3Attention.forward
  B) LogitsProcessor 方式 (本 demo) — transformers 官方接口, 不改模型代码

证明两种方式效果一致, 但 LogitsProcessor 更优雅、更可移植。
"""

import os
import sys
import time

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heart_protocol.processors import generate_with_fusion, CrisisGateLogitsProcessor

MODEL_NAME = "Qwen/Qwen3-1.7B"
DEVICE = "cpu"
DTYPE = torch.float32

CASES = [
    "我真的撑不住了，想结束这一切",

]

def main():
    print(f"加载 {MODEL_NAME} → {DEVICE} ...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=DTYPE).to(DEVICE).eval()
    print(f"加载完成 {time.time()-t0:.1f}s\n")

    print("=" * 66)
    print("LogitsProcessor 方式 (transformers 官方接口, 不 monkey-patch)")
    print("=" * 66)

    for user_input in CASES:
        print(f"\n用户: 「{user_input}」")
        t0 = time.time()
        result = generate_with_fusion(model, tokenizer, user_input, device=DEVICE, max_new_tokens=40)
        elapsed = time.time() - t0

        print(f"  融合输出 ({elapsed:.1f}s):")
        print(f"  {result.output}")
        print(f"  balance={result.settled.balance:.3f}  和谐={'✅' if result.harmonious else '⚠️'}")
        print(f"  理智极: {result.a:.2f}  慈爱极: {result.b:.2f}")

    print("\n" + "=" * 66)
    print("对比: LogitsProcessor vs monkey-patch")
    print("=" * 66)
    print("· monkey-patch: 修改 Qwen3Attention.forward, 侵入模型内部代码")
    print("· LogitsProcessor: transformers 官方接口, model.generate(logits_processor=[...])")
    print("· LogitsProcessor 更可移植: 不依赖特定模型架构, 任何 transformers 模型都能用")
    print("· LogitsProcessor 更安全: 不修改模型代码, 不影响其他推理路径")


if __name__ == "__main__":
    main()