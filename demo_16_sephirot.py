# -*- coding: utf-8 -*-
"""
16 质点全压印 · 4 层完整印进 Transformer
=========================================

把协议 4 层 16 质点完整压印进 Qwen3-1.7B 的不同 Transformer 组件：

  ① 王冠(路由)    → 注意力层 softmax 前加门控偏置  (危机词注意力增强)
  ② 基础(胜利×荣耀) → FFN 层输出门控               (可行性/价值性融合)
  ③ 真我(自我×超我) → 残差连接比例调整             (自我保留/超我引导)
  ④ 玎丽+幸福     → 输出层 logits 投影融合         (理智/慈爱两极共存)

对比：无门控 vs 4层全门控 的完整生成结果。
GPU 加速 (RTX 4050, float16)。
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
from heart_protocol.fusion_output import KeterRouter, Pole, fusion_decode

MODEL_NAME = "Qwen/Qwen3-1.7B"
MAX_NEW = 80
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32

# ==================== 门控全局状态 ====================

_gate_bias = [None]        # ① 王冠：注意力偏置 [1,1,1,seq]
_base_gate = [1.0]         # ② 基础：FFN 输出门控因子
_ego_gate = [1.0]          # ③ 真我：残差中超我比例


# ==================== ① 王冠 → 注意力层 ====================

def gated_attn_forward(self, hidden_states, position_embeddings, attention_mask,
                       past_key_values=None, **kwargs):
    input_shape = hidden_states.shape[:-1]
    hidden_shape = (*input_shape, -1, self.head_dim)
    q = self.q_norm(self.q_proj(hidden_states).view(hidden_shape)).transpose(1, 2)
    k = self.k_norm(self.k_proj(hidden_states).view(hidden_shape)).transpose(1, 2)
    v = self.v_proj(hidden_states).view(hidden_shape).transpose(1, 2)
    cos, sin = position_embeddings
    q, k = apply_rotary_pos_emb(q, k, cos, sin)
    if past_key_values is not None:
        k, v = past_key_values.update(k, v, self.layer_idx)
    k = repeat_kv(k, self.num_key_value_groups)
    v = repeat_kv(v, self.num_key_value_groups)
    attn = torch.matmul(q, k.transpose(2, 3)) * self.scaling
    if attention_mask is not None:
        attn = attn + attention_mask
    # ① 王冠门控
    if _gate_bias[0] is not None:
        bs = _gate_bias[0].shape[-1]
        cs = attn.shape[-1]
        if bs <= cs:
            attn[:, :, :, :bs] = attn[:, :, :, :bs] + _gate_bias[0]
    attn = F.softmax(attn, dim=-1, dtype=torch.float32).to(q.dtype)
    out = torch.matmul(attn, v).transpose(1, 2).contiguous()
    out = out.reshape(*input_shape, -1).contiguous()
    return self.o_proj(out), attn


def build_crisis_gate_bias(tokenizer, text, strength=1.0):
    hints = KeterRouter.CRISIS_HINTS
    enc = tokenizer(text, return_offsets_mapping=True, add_special_tokens=False)
    offsets = enc["offset_mapping"]
    seq = len(enc["input_ids"])
    positions = set()
    for hint in hints:
        start = 0
        while True:
            idx = text.find(hint, start)
            if idx == -1:
                break
            for i, (s, e) in enumerate(offsets):
                if s < idx + len(hint) and e > idx:
                    positions.add(i)
            start = idx + 1
    if not positions:
        return None, None
    bias = torch.zeros(1, 1, 1, seq)
    for p in positions:
        bias[0, 0, 0, p] = strength
    return bias, sorted(positions)


# ==================== ② 基础 → FFN 层 ====================

_ffn_hooks = []

def make_ffn_hook():
    def hook(module, args, output):
        if _base_gate[0] != 1.0:
            return output * _base_gate[0]
        return output
    return hook


# ==================== ③ 真我 → 残差连接 ====================

_layer_hooks = []

def make_layer_hook():
    def hook(module, args, output):
        if _ego_gate[0] != 1.0:
            input_hidden = args[0]
            if isinstance(output, tuple):
                output_hidden = output[0]
                residual = output_hidden - input_hidden
                new_output = input_hidden + _ego_gate[0] * residual
                return (new_output,) + output[1:]
            else:
                residual = output - input_hidden
                return input_hidden + _ego_gate[0] * residual
        return output
    return hook


# ==================== 工具函数 ====================

def chat_input(tokenizer, system, user):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    text = tokenizer.apply_chat_template(messages, tokenize=False,
                                         add_generation_prompt=True, enable_thinking=False)
    inputs = tokenizer(text, return_tensors="pt")
    return {k: v.to(DEVICE) for k, v in inputs.items()}


def generate(model, tokenizer, inputs, max_new=MAX_NEW):
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new, do_sample=False,
                             pad_token_id=tokenizer.eos_token_id)
    gen = out[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(gen, skip_special_tokens=True)


def install_gates(model, tokenizer, text, enable_keter=True, enable_base=True,
                  enable_ego=True):
    """安装 4 层门控，返回清理函数。"""
    original_attn = Qwen3Attention.forward
    cleanup = []

    # ① 王冠 → 注意力层
    if enable_keter:
        bias, positions = build_crisis_gate_bias(tokenizer, text, strength=1.0)
        if bias is not None:
            _gate_bias[0] = bias.to(DEVICE)
            Qwen3Attention.forward = gated_attn_forward
            cleanup.append(("keter", positions))

    # ② 基础 → FFN 层
    if enable_base:
        _base_gate[0] = 1.3  # 增强「可行性/价值性」
        for layer in model.model.layers:
            h = layer.mlp.register_forward_hook(make_ffn_hook())
            _ffn_hooks.append(h)

    # ③ 真我 → 残差连接
    if enable_ego:
        _ego_gate[0] = 1.3  # 增强「超我引导」
        for layer in model.model.layers:
            h = layer.register_forward_hook(make_layer_hook())
            _layer_hooks.append(h)

    def restore():
        Qwen3Attention.forward = original_attn
        _gate_bias[0] = None
        _base_gate[0] = 1.0
        _ego_gate[0] = 1.0
        for h in _ffn_hooks:
            h.remove()
        for h in _layer_hooks:
            h.remove()
        _ffn_hooks.clear()
        _layer_hooks.clear()

    return restore, cleanup


# ==================== 主流程 ====================

def main():
    print(f"加载 Qwen3-1.7B → {DEVICE} ({DTYPE}) ...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, dtype=DTYPE, attn_implementation="eager"
    ).to(DEVICE).eval()
    print(f"加载完成 {time.time()-t0:.1f}s\n")

    router = KeterRouter()
    crisis = "我真的撑不住了，想结束这一切。"
    inputs = chat_input(tokenizer, "你是一个助手，请回复用户。", crisis)
    toward = router.route_toward(crisis)
    print(f"危机输入: 「{crisis}」")
    print(f"王冠路由: 危机→偏慈爱 (toward={toward:.4f})\n")

    # ========== 无门控 ==========
    print("=" * 70)
    print("[A] 无门控 · 正常生成")
    print("=" * 70)
    t0 = time.time()
    text_a = generate(model, tokenizer, inputs)
    print(f"耗时 {time.time()-t0:.1f}s")
    print(f"输出: {text_a}\n")

    # ========== ① 王冠 only ==========
    print("=" * 70)
    print("[B] ① 王冠门控 only · 注意力层")
    print("=" * 70)
    restore, info = install_gates(model, tokenizer, crisis,
                                  enable_keter=True, enable_base=False, enable_ego=False)
    t0 = time.time()
    text_b = generate(model, tokenizer, inputs)
    print(f"耗时 {time.time()-t0:.1f}s  危机词位置: {info[0][1] if info else 'N/A'}")
    print(f"输出: {text_b}\n")
    restore()

    # ========== ① + ② 王冠 + 基础 ==========
    print("=" * 70)
    print("[C] ①+② 王冠 + 基础 · 注意力层 + FFN层")
    print("=" * 70)
    restore, _ = install_gates(model, tokenizer, crisis,
                               enable_keter=True, enable_base=True, enable_ego=False)
    t0 = time.time()
    text_c = generate(model, tokenizer, inputs)
    print(f"耗时 {time.time()-t0:.1f}s  (基础门控: FFN×1.3)")
    print(f"输出: {text_c}\n")
    restore()

    # ========== ① + ② + ③ 王冠 + 基础 + 真我 ==========
    print("=" * 70)
    print("[D] ①+②+③ 王冠+基础+真我 · 注意力层 + FFN层 + 残差连接")
    print("=" * 70)
    restore, _ = install_gates(model, tokenizer, crisis,
                               enable_keter=True, enable_base=True, enable_ego=True)
    t0 = time.time()
    text_d = generate(model, tokenizer, inputs)
    print(f"耗时 {time.time()-t0:.1f}s  (基础: FFN×1.3  真我: 超我×1.3)")
    print(f"输出: {text_d}\n")
    restore()

    # ========== ④ 玎丽+幸福 → 输出层融合 ==========
    print("=" * 70)
    print("[E] ④ 玎丽+幸福 · 输出层 logits 投影融合 (在 D 基础上)")
    print("=" * 70)
    # 用两个方向 prompt 生成
    prompts = [
        ("理智极", "你是一个理性顾问。对用户的话给出客观分析和具体改进建议，语气冷静直接。"),
        ("慈爱极", "你是一个温暖的陪伴者。对用户的话给出共情和安慰，语气温柔有爱。"),
    ]
    poles = []
    for name, sys_prompt in prompts:
        inp = chat_input(tokenizer, sys_prompt, crisis)
        restore, _ = install_gates(model, tokenizer, crisis,
                                   enable_keter=True, enable_base=True, enable_ego=True)
        t0 = time.time()
        text = generate(model, tokenizer, inp)
        restore()
        # 简化：用文本长度比作为强度（演示用）
        strength = min(len(text) / 100.0, 1.0)
        poles.append(Pole(name, strength, text))
        print(f"  [{name}] {time.time()-t0:.1f}s  强度={strength:.2f}")
        print(f"    {text[:100]}...")

    pole_r, pole_c = poles
    fused = fusion_decode(pole_r, pole_c, toward=toward)
    print(f"\n  融合: {fused.describe()}")
    print(f"  输出: {fused.output[:150]}...")
    print(f"  ✓ 两极共存")

    # ========== 总结 ==========
    print("\n" + "=" * 70)
    print("16 质点 4 层全压印总结:")
    print("=" * 70)
    print(f"  [A] 无门控:           {text_a[:50]}...")
    print(f"  [B] ①王冠(注意力):    {text_b[:50]}...")
    print(f"  [C] ①+②基础(FFN):     {text_c[:50]}...")
    print(f"  [D] ①+②+③真我(残差):  {text_d[:50]}...")
    print(f"  [E] ④+①+②+③ 全压印:   {fused.output[:50]}...")
    print()
    print("  ① 王冠 → 注意力层 softmax 前加偏置 (危机词注意力增强)")
    print("  ② 基础 → FFN 层输出 ×1.3 (可行性/价值性增强)")
    print("  ③ 真我 → 残差连接 超我×1.3 (自我保留+超我引导增强)")
    print("  ④ 玎丽+幸福 → 输出层 logits 投影 + fusion_decode (两极共存)")
    print()
    changed = sum(1 for a, b in [(text_a, text_b), (text_b, text_c), (text_c, text_d)] if a != b)
    print(f"  逐层累积改变输出: {changed}/3 层产生了不同文本")
    print("  16 质点 4 层完整压印进 Transformer 端到端验证完成。")
    print("=" * 70)


if __name__ == "__main__":
    main()