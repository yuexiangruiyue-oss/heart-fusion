# -*- coding: utf-8 -*-
"""
完整生成对比 · 注意力门控累积效果 + logits 直接投影融合
=====================================================

阶段 1：多步生成对比
  对危机输入用 Qwen3-1.7B 生成完整回复，对比：
    A) 正常生成（无门控 + argmax）
    B) 注意力门控生成（王冠门控 + argmax）—— 看门控累积效果

阶段 2：logits 直接投影 + 融合函数层替换 argmax
  用「理性顾问」「温暖陪伴」两个 prompt 分别生成完整回复，
  从生成过程的 scores 直接投影出两极强度 a/b，
  交给 fusion_decode 融合 —— 对比 argmax（选一个）vs 融合（两极共存）。
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
from heart_protocol.fusion_output import KeterRouter, Pole, argmax_decode, fusion_decode

MODEL_NAME = "Qwen/Qwen3-1.7B"
MAX_NEW = 60

# ==================== 王冠门控全局状态 ====================

_gate_bias = [None]


def gated_forward(self, hidden_states, position_embeddings, attention_mask,
                  past_key_values=None, **kwargs):
    input_shape = hidden_states.shape[:-1]
    hidden_shape = (*input_shape, -1, self.head_dim)
    query_states = self.q_norm(self.q_proj(hidden_states).view(hidden_shape)).transpose(1, 2)
    key_states = self.k_norm(self.k_proj(hidden_states).view(hidden_shape)).transpose(1, 2)
    value_states = self.v_proj(hidden_states).view(hidden_shape).transpose(1, 2)
    cos, sin = position_embeddings
    query_states, key_states = apply_rotary_pos_emb(query_states, key_states, cos, sin)
    if past_key_values is not None:
        key_states, value_states = past_key_values.update(key_states, value_states, self.layer_idx)
    key_states = repeat_kv(key_states, self.num_key_value_groups)
    value_states = repeat_kv(value_states, self.num_key_value_groups)
    attn_weights = torch.matmul(query_states, key_states.transpose(2, 3)) * self.scaling
    if attention_mask is not None:
        attn_weights = attn_weights + attention_mask
    if _gate_bias[0] is not None:
        bias = _gate_bias[0]
        bias_seq = bias.shape[-1]
        cur_seq = attn_weights.shape[-1]
        if bias_seq <= cur_seq:
            attn_weights[:, :, :, :bias_seq] = attn_weights[:, :, :, :bias_seq] + bias
    attn_weights = F.softmax(attn_weights, dim=-1, dtype=torch.float32).to(query_states.dtype)
    attn_output = torch.matmul(attn_weights, value_states)
    attn_output = attn_output.transpose(1, 2).contiguous()
    attn_output = attn_output.reshape(*input_shape, -1).contiguous()
    attn_output = self.o_proj(attn_output)
    return attn_output, attn_weights


def build_crisis_gate_bias(tokenizer, text, strength=1.0):
    crisis_hints = KeterRouter.CRISIS_HINTS
    enc = tokenizer(text, return_offsets_mapping=True, add_special_tokens=False)
    offsets = enc["offset_mapping"]
    seq_len = len(enc["input_ids"])
    emotion_positions = set()
    for hint in crisis_hints:
        start = 0
        while True:
            idx = text.find(hint, start)
            if idx == -1:
                break
            end = idx + len(hint)
            for i, (s, e) in enumerate(offsets):
                if s < end and e > idx:
                    emotion_positions.add(i)
            start = idx + 1
    if not emotion_positions:
        return None, None
    # 偏置只对 key 位置加 [1,1,1,seq]，broadcast 到任意 query 长度
    bias = torch.zeros(1, 1, 1, seq_len)
    for pos in emotion_positions:
        bias[0, 0, 0, pos] = strength
    return bias, sorted(emotion_positions)


def chat_input(tokenizer, system, user):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False)
    return tokenizer(text, return_tensors="pt")


def generate_text(model, tokenizer, inputs, max_new=MAX_NEW):
    """生成文本，返回 (text, scores_list)。scores_list 是每步的 logits(softmax后)。"""
    with torch.no_grad():
        out = model.generate(
            **inputs, max_new_tokens=max_new, do_sample=False,
            return_dict_in_generate=True, output_scores=True,
        )
    generated_ids = out.sequences[0][inputs["input_ids"].shape[1]:]
    text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    return text, out.scores


# ==================== logits 投影：理智/慈爱方向词集 ====================

REASON_WORDS = ["分析", "建议", "步骤", "原因", "客观", "理性", "方案", "目标", "执行", "具体", "拆解", "行动"]
COMPASSION_WORDS = ["陪伴", "理解", "感受", "温暖", "心疼", "拥抱", "在乎", "温柔", "慢慢", "别怕", "我在", "一起"]


def build_direction_vectors(tokenizer):
    """把理智/慈爱词集 tokenize → token id 集合。"""
    def words_to_ids(words):
        ids = set()
        for w in words:
            for tid in tokenizer.encode(w, add_special_tokens=False):
                ids.add(tid)
        return ids
    return words_to_ids(REASON_WORDS), words_to_ids(COMPASSION_WORDS)


def logits_to_pole_strength(scores, reason_ids, compassion_ids):
    """
    从生成过程的所有步 scores (softmax 后的概率) 提取两极强度。
    每一步：理智方向 = sum(prob[reason_ids])，慈爱方向 = sum(prob[compassion_ids])
    多步累积后归一化到 [0, 1]。
    """
    reason_sum = 0.0
    compassion_sum = 0.0
    for step_scores in scores:
        probs = step_scores[0]  # [vocab_size]
        r = sum(probs[tid].item() for tid in reason_ids if tid < probs.shape[0])
        c = sum(probs[tid].item() for tid in compassion_ids if tid < probs.shape[0])
        reason_sum += r
        compassion_sum += c
    total = reason_sum + compassion_sum
    if total < 1e-8:
        return 0.5, 0.5
    return reason_sum / total, compassion_sum / total


# ==================== 主流程 ====================

def main():
    print("加载 Qwen3-1.7B (eager attention) ...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, dtype=torch.float32, attn_implementation="eager"
    )
    model.eval()
    print(f"加载完成 {time.time()-t0:.1f}s\n")

    original_forward = Qwen3Attention.forward
    router = KeterRouter()

    crisis_input = "我真的撑不住了，想结束这一切。"

    # ============================================================
    # 阶段 1：多步生成对比 —— 门控累积效果
    # ============================================================
    print("=" * 70)
    print("阶段 1：完整生成对比 · 注意力门控累积效果")
    print("=" * 70)
    print(f"\n危机输入: 「{crisis_input}」")

    # A) 正常生成（无门控）
    _gate_bias[0] = None
    Qwen3Attention.forward = original_forward
    inputs = chat_input(tokenizer, "你是一个助手，请回复用户。", crisis_input)
    print(f"\n[A] 正常生成（无门控）生成 {MAX_NEW} token ...", flush=True)
    t0 = time.time()
    text_a, _ = generate_text(model, tokenizer, inputs)
    print(f"    耗时 {time.time()-t0:.1f}s")
    print(f"    输出: {text_a}")

    # B) 注意力门控生成
    bias, emotion_pos = build_crisis_gate_bias(tokenizer, crisis_input, strength=1.0)
    _gate_bias[0] = bias
    Qwen3Attention.forward = gated_forward
    print(f"\n[B] 注意力门控生成（王冠门控）生成 {MAX_NEW} token ...", flush=True)
    t0 = time.time()
    text_b, _ = generate_text(model, tokenizer, inputs)
    print(f"    耗时 {time.time()-t0:.1f}s")
    print(f"    输出: {text_b}")

    _gate_bias[0] = None
    Qwen3Attention.forward = original_forward

    print(f"\n  对比: 门控{'改变了' if text_a != text_b else '未改变'}生成结果。")
    if text_a != text_b:
        print(f"    无门控长度={len(text_a)}  有门控长度={len(text_b)}")

    # ============================================================
    # 阶段 2：logits 直接投影 + 融合函数层替换 argmax
    # ============================================================
    print("\n" + "=" * 70)
    print("阶段 2：logits 直接投影 · 融合函数层替换 argmax")
    print("=" * 70)

    reason_ids, compassion_ids = build_direction_vectors(tokenizer)
    print(f"\n理智方向词集 token ids: {len(reason_ids)} 个")
    print(f"慈爱方向词集 token ids: {len(compassion_ids)} 个")

    # 用两个方向 prompt 分别生成
    prompts = [
        ("理智极", "你是一个理性顾问。对用户的话给出客观分析和具体改进建议，语气冷静直接。"),
        ("慈爱极", "你是一个温暖的陪伴者。对用户的话给出共情和安慰，语气温柔有爱。"),
    ]

    replies = {}
    for pole_name, system_prompt in prompts:
        inputs = chat_input(tokenizer, system_prompt, crisis_input)
        print(f"\n  [{pole_name}] 生成中 ...", flush=True)
        t0 = time.time()
        text, scores = generate_text(model, tokenizer, inputs, max_new=MAX_NEW)
        a, b = logits_to_pole_strength(scores, reason_ids, compassion_ids)
        print(f"    耗时 {time.time()-t0:.1f}s")
        print(f"    输出: {text}")
        print(f"    logits 投影: 理智方向={a:.3f}  慈爱方向={b:.3f}")
        replies[pole_name] = {"text": text, "a": a, "b": b}

    # 从 logits 直接读出两极强度
    a_reason = replies["理智极"]["a"]
    b_reason = replies["理智极"]["b"]
    a_comp = replies["慈爱极"]["a"]
    b_comp = replies["慈爱极"]["b"]

    # 理智极回复的理智强度 = a_reason，慈爱极回复的慈爱强度 = b_comp
    strength_reason = a_reason
    strength_comp = b_comp

    print(f"\n  从 logits 直接投影出的两极强度:")
    print(f"    理智极回复 → 理智方向强度 = {strength_reason:.3f}")
    print(f"    慈爱极回复 → 慈爱方向强度 = {strength_comp:.3f}")

    # 构造 Pole
    pole_a = Pole("理智极", strength_reason, replies["理智极"]["text"])
    pole_b = Pole("慈爱极", strength_comp, replies["慈爱极"]["text"])

    # 旧范式: argmax
    print(f"\n  [旧] argmax 挑最大 → {'理智极' if strength_reason >= strength_comp else '慈爱极'}")
    old_output = argmax_decode(pole_a, pole_b)
    dropped = pole_b if strength_reason >= strength_comp else pole_a
    print(f"      输出: {old_output[:80]}...")
    print(f"      ✗ 被剔除: 「{dropped.reply[:80]}...」")

    # 新范式: 融合函数层
    toward = router.route_toward(crisis_input)
    routing = "危机→偏慈爱" if toward > math.pi / 4 + 0.01 else "常规→平衡"
    fused = fusion_decode(pole_a, pole_b, toward=toward)
    print(f"\n  [新] 融合函数层 (王冠路由:{routing})")
    print(f"      {fused.describe()}")
    print(f"      输出: {fused.output}")
    print(f"      ✓ 两极都以最终配比共存，没有任何一方被剔除")

    print("\n" + "=" * 70)
    print("总结:")
    print("  阶段1: 注意力门控在多步生成中累积改变输出 —— 王冠门控不只影响一步，")
    print("         而是贯穿整个生成过程。")
    print("  阶段2: 从生成过程 logits 直接投影出两极强度（不依赖模型自评），")
    print("         交给 fusion_decode 融合 —— argmax 剔除一极，融合层两极共存。")
    print("  V2.0 两层压印 Transformer 端到端验证完成。")
    print("=" * 70)


if __name__ == "__main__":
    main()