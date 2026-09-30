# -*- coding: utf-8 -*-
"""
王冠路由 · 真接注意力门控演示
==============================

用 Qwen3-1.7B 真实模型，把 KeterRouter 从「关键词检测」升级为「注意力层门控」：
  1. 观察阶段：危机输入 vs 普通输入的真实注意力分布差异
  2. 门控阶段：在注意力 softmax 前加门控偏置，对比有/无门控的输出

核心：monkey-patch Qwen3Attention.forward，在 softmax(scores + mask) 前注入
      gate_bias —— 这就是王冠门控「作用于注意力层」的落地。
"""

import math
import os
import sys
import time

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.models.qwen3.modeling_qwen3 import (
    Qwen3Attention,
    apply_rotary_pos_emb,
    repeat_kv,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heart_protocol.fusion_output import KeterRouter

MODEL_NAME = "Qwen/Qwen3-1.7B"

# ==================== 王冠门控全局状态 ====================

_gate_bias = [None]  # shape [1,1,seq,seq] 或 None；broadcast 到 [batch, heads, seq, seq]


# ==================== monkey-patch: 在 softmax 前加门控偏置 ====================


def gated_forward(
    self,
    hidden_states,
    position_embeddings,
    attention_mask,
    past_key_values=None,
    **kwargs,
):
    """复现 Qwen3Attention.forward，但在 softmax 前注入 _gate_bias。"""
    input_shape = hidden_states.shape[:-1]
    hidden_shape = (*input_shape, -1, self.head_dim)

    query_states = self.q_norm(self.q_proj(hidden_states).view(hidden_shape)).transpose(1, 2)
    key_states = self.k_norm(self.k_proj(hidden_states).view(hidden_shape)).transpose(1, 2)
    value_states = self.v_proj(hidden_states).view(hidden_shape).transpose(1, 2)

    cos, sin = position_embeddings
    query_states, key_states = apply_rotary_pos_emb(query_states, key_states, cos, sin)

    if past_key_values is not None:
        key_states, value_states = past_key_values.update(
            key_states, value_states, self.layer_idx
        )

    # GQA: repeat KV heads → 匹配 Q 头数
    key_states = repeat_kv(key_states, self.num_key_value_groups)
    value_states = repeat_kv(value_states, self.num_key_value_groups)

    # attention scores = Q @ K^T * scaling
    attn_weights = torch.matmul(query_states, key_states.transpose(2, 3)) * self.scaling
    if attention_mask is not None:
        attn_weights = attn_weights + attention_mask

    # ★★★ 王冠门控：在 softmax 前加偏置 ★★★
    if _gate_bias[0] is not None:
        attn_weights = attn_weights + _gate_bias[0]

    attn_weights = F.softmax(attn_weights, dim=-1, dtype=torch.float32).to(query_states.dtype)
    attn_output = torch.matmul(attn_weights, value_states)
    attn_output = attn_output.transpose(1, 2).contiguous()

    attn_output = attn_output.reshape(*input_shape, -1).contiguous()
    attn_output = self.o_proj(attn_output)
    return attn_output, attn_weights


# ==================== 门控偏置构造 ====================


def build_crisis_gate_bias(tokenizer, text, strength=1.0):
    """
    危机门控偏置：增强对「情绪关键词」token 的注意力。

    用 KeterRouter 的危机词列表，找到这些词在输入中的 token 位置，
    对所有 query 位置，增强对这些 key 位置的 attention score。
    """
    crisis_hints = KeterRouter.CRISIS_HINTS

    enc = tokenizer(text, return_offsets_mapping=True, add_special_tokens=False)
    input_ids = enc["input_ids"]
    offsets = enc["offset_mapping"]
    seq_len = len(input_ids)

    # 找到危机词在原文中的字符范围 → 映射到 token 位置
    emotion_positions = set()
    for hint in crisis_hints:
        start = 0
        while True:
            idx = text.find(hint, start)
            if idx == -1:
                break
            end = idx + len(hint)
            for i, (s, e) in enumerate(offsets):
                if s < end and e > idx:  # token 与危机词字符范围有重叠
                    emotion_positions.add(i)
            start = idx + 1

    if not emotion_positions:
        return None

    # 构造偏置 [1, 1, seq, seq]
    bias = torch.zeros(1, 1, seq_len, seq_len)
    for pos in emotion_positions:
        bias[0, 0, :, pos] = strength  # 对所有 query，增强对 emotion token 的 attention
    return bias, sorted(emotion_positions)


# ==================== 主流程 ====================


def main():
    print("加载 Qwen3-1.7B (eager attention) ...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, dtype=torch.float32, attn_implementation="eager"
    )
    model.eval()
    print(f"加载完成 {time.time()-t0:.1f}s  (层数={model.config.num_hidden_layers} "
          f"头数={model.config.num_attention_heads} KV头={model.config.num_key_value_heads})")

    original_forward = Qwen3Attention.forward

    cases = [
        ("普通", "我今天完成了一个项目，感觉很充实。"),
        ("危机", "我真的撑不住了，想结束这一切。"),
    ]

    # ========== 阶段 1：观察注意力分布 ==========
    print("\n" + "=" * 70)
    print("阶段 1：观察真实注意力分布（无门控）")
    print("=" * 70)

    for label, text in cases:
        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            out = model(**inputs, output_attentions=True)

        attentions = out.attentions  # 28 层
        logits = out.logits[0, -1]
        tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
        seq_len = len(tokens)

        # 最后一层、跨所有头平均 → 最后一个 token 对各 token 的注意力
        last_attn = attentions[-1][0].mean(dim=0)[-1]

        print(f"\n[{label}] 「{text}」  (seq={seq_len})")
        print(f"  最后一层 · 最后token的注意力分布:")
        for i, (tok, val) in enumerate(zip(tokens, last_attn)):
            bar = "█" * int(val * 200)
            print(f"    {i:2d} {tok:14s} {val:.4f} {bar}")

        top5 = torch.topk(logits, 5)
        print(f"  top-5 next: {[tokenizer.decode(t) for t in top5.indices]}")

    # ========== 阶段 2：王冠门控 ==========
    print("\n" + "=" * 70)
    print("阶段 2：王冠门控 · 注意力 softmax 前加偏置")
    print("=" * 70)

    router = KeterRouter()

    for label, text in cases:
        inputs = tokenizer(text, return_tensors="pt")
        seq_len = inputs["input_ids"].shape[1]
        tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])

        toward = router.route_toward(text)
        is_crisis = toward > math.pi / 4 + 0.01

        print(f"\n[{label}] 「{text}」")
        print(f"  王冠路由: {'危机→偏慈爱' if is_crisis else '常规→平衡'}  (toward={toward:.4f})")

        # 无门控 forward
        _gate_bias[0] = None
        Qwen3Attention.forward = original_forward
        with torch.no_grad():
            out_no = model(**inputs, output_attentions=True)
        logits_no = out_no.logits[0, -1]

        if not is_crisis:
            top5 = torch.topk(logits_no, 5)
            print(f"  非危机，门控不激活。top-5: {[tokenizer.decode(t) for t in top5.indices]}")
            continue

        # 构造门控偏置
        result = build_crisis_gate_bias(tokenizer, text, strength=1.0)
        if result is None:
            print("  未找到危机词位置，跳过门控。")
            continue
        bias, emotion_pos = result
        _gate_bias[0] = bias

        emotion_tokens = [tokens[p] for p in emotion_pos]
        print(f"  危机词 token 位置: {emotion_pos} → {emotion_tokens}")

        # 有门控 forward
        Qwen3Attention.forward = gated_forward
        with torch.no_grad():
            out_gated = model(**inputs, output_attentions=True)
        logits_gated = out_gated.logits[0, -1]

        # 恢复
        _gate_bias[0] = None
        Qwen3Attention.forward = original_forward

        # 对比 top-5
        top5_no = torch.topk(logits_no, 5)
        top5_gated = torch.topk(logits_gated, 5)
        print(f"  [无门控] top-5: {[tokenizer.decode(t) for t in top5_no.indices]}")
        print(f"  [有门控] top-5: {[tokenizer.decode(t) for t in top5_gated.indices]}")

        # logits 差异
        diff = (logits_gated - logits_no).abs()
        print(f"  logits 差异: mean={diff.mean():.4f}  max={diff.max():.4f}")

        # 注意力分布变化（最后一层）
        attn_no = out_no.attentions[-1][0].mean(dim=0)[-1]
        attn_gated = out_gated.attentions[-1][0].mean(dim=0)[-1]
        print(f"  注意力分布变化 (最后一层):")
        for i, (tok, a_no, a_g) in enumerate(zip(tokens, attn_no, attn_gated)):
            delta = a_g - a_no
            mark = "↑" if delta > 0.005 else ("↓" if delta < -0.005 else "·")
            flag = " ★" if i in emotion_pos else ""
            print(f"    {i:2d} {tok:14s} 无={a_no:.4f}  有={a_g:.4f}  Δ={delta:+.4f} {mark}{flag}")

    print("\n" + "=" * 70)
    print("结论:")
    print("  KeterRouter 检测到危机信号 → 在注意力层 softmax 前加门控偏置")
    print("  → 注意力分布改变 → 输出 logits 改变 → 生成内容改变")
    print("  这就是王冠路由从「关键词检测」升级为「注意力层门控」的端到端落地。")
    print("=" * 70)


if __name__ == "__main__":
    main()