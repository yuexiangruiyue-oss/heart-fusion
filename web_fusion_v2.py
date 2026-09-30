# -*- coding: utf-8 -*-
"""
16 质点融合函数 · 增强版 Web 界面 V2
=====================================

功能：
  - 输入一句话 → 理智极/慈爱极两段回复
  - 16 质点 4 层全压印展示（王冠→注意力层、基础→FFN层、真我→残差连接、王丽+幸福→输出层）
  - 注意力门控开关 + 基础/真我门控强度滑块
  - argmax vs 融合并排对比
  - 注意力分布图

启动: python launch_web_v2.py → 浏览器打开 http://localhost:7860
"""

import math
import os
import sys
import time

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn.functional as Fn
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.models.qwen3.modeling_qwen3 import (
    Qwen3Attention, apply_rotary_pos_emb, repeat_kv,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heart_protocol.fusion_output import KeterRouter, Pole, argmax_decode, fusion_decode

MODEL_NAME = "Qwen/Qwen3-1.7B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32
MAX_NEW = 80

REASON_WORDS = ["分析","建议","步骤","原因","客观","理性","方案","目标","执行","具体","拆解","行动"]
COMPASSION_WORDS = ["陪伴","理解","感受","温暖","心疼","拥抱","在乎","温柔","慢慢","别怕","我在","一起"]

# ==================== 模型加载 ====================
print(f"加载 Qwen3-1.7B → {DEVICE} ({DTYPE}) ...")
t0 = time.time()
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=DTYPE, attn_implementation="eager").to(DEVICE).eval()
print(f"加载完成 {time.time()-t0:.1f}s")
router = KeterRouter()
_orig_attn_fwd = Qwen3Attention.forward

_reason_ids = set()
for w in REASON_WORDS:
    for t in tokenizer.encode(w, add_special_tokens=False): _reason_ids.add(t)
_compassion_ids = set()
for w in COMPASSION_WORDS:
    for t in tokenizer.encode(w, add_special_tokens=False): _compassion_ids.add(t)

# ==================== 门控全局状态 ====================
_gate_bias = [None]
_base_gate = [1.0]
_ego_gate = [1.0]
_ffn_hooks = []
_layer_hooks = []

def _gated_attn_fwd(self, hidden_states, position_embeddings, attention_mask, past_key_values=None, **kwargs):
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
    if _gate_bias[0] is not None:
        bs = _gate_bias[0].shape[-1]
        cs = attn.shape[-1]
        if bs <= cs:
            attn[:, :, :, :bs] = attn[:, :, :, :bs] + _gate_bias[0]
    attn = Fn.softmax(attn, dim=-1, dtype=torch.float32).to(q.dtype)
    out = torch.matmul(attn, v).transpose(1, 2).contiguous()
    out = out.reshape(*input_shape, -1).contiguous()
    return self.o_proj(out), attn

def _build_crisis_bias(text, strength=1.0):
    hints = KeterRouter.CRISIS_HINTS
    enc = tokenizer(text, return_offsets_mapping=True, add_special_tokens=False)
    offsets = enc["offset_mapping"]
    seq = len(enc["input_ids"])
    positions = set()
    for hint in hints:
        start = 0
        while True:
            idx = text.find(hint, start)
            if idx == -1: break
            for i, (s, e) in enumerate(offsets):
                if s < idx + len(hint) and e > idx: positions.add(i)
            start = idx + 1
    if not positions: return None, None
    bias = torch.zeros(1, 1, 1, seq)
    for p in positions: bias[0, 0, 0, p] = strength
    return bias, sorted(positions)

def _ffn_hook(module, args, output):
    if _base_gate[0] != 1.0: return output * _base_gate[0]
    return output

def _layer_hook(module, args, output):
    if _ego_gate[0] != 1.0:
        inp = args[0]
        if isinstance(output, tuple):
            res = output[0] - inp
            return (inp + _ego_gate[0] * res,) + output[1:]
        else:
            return inp + _ego_gate[0] * (output - inp)
    return output

def install_gates(text, enable_keter, base_strength, ego_strength):
    Qwen3Attention.forward = _gated_attn_fwd if enable_keter else _orig_attn_fwd
    bias_info = ""
    if enable_keter:
        bias, pos = _build_crisis_bias(text)
        if bias is not None:
            _gate_bias[0] = bias.to(DEVICE)
            bias_info = f"危机词位置={pos}"
        else:
            _gate_bias[0] = None
    else:
        _gate_bias[0] = None
    _base_gate[0] = base_strength
    _ego_gate[0] = ego_strength
    for layer in model.model.layers:
        _ffn_hooks.append(layer.mlp.register_forward_hook(_ffn_hook))
        _layer_hooks.append(layer.register_forward_hook(_layer_hook))
    return bias_info

def restore_gates():
    Qwen3Attention.forward = _orig_attn_fwd
    _gate_bias[0] = None
    _base_gate[0] = 1.0
    _ego_gate[0] = 1.0
    for h in _ffn_hooks: h.remove()
    for h in _layer_hooks: h.remove()
    _ffn_hooks.clear()
    _layer_hooks.clear()

# ==================== 生成 ====================
def _chat_input(system, user):
    msgs = [{"role":"system","content":system},{"role":"user","content":user}]
    text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    inp = tokenizer(text, return_tensors="pt")
    return {k: v.to(DEVICE) for k, v in inp.items()}

def _generate(system, user):
    inp = _chat_input(system, user)
    with torch.no_grad():
        out = model.generate(**inp, max_new_tokens=MAX_NEW, do_sample=False,
                             pad_token_id=tokenizer.eos_token_id,
                             return_dict_in_generate=True, output_scores=True)
    gen = out.sequences[0][inp["input_ids"].shape[1]:]
    text = tokenizer.decode(gen, skip_special_tokens=True)
    # logits 投影
    r_sum = c_sum = 0.0
    for sc in out.scores:
        p = sc[0]
        r_sum += sum(p[t].item() for t in _reason_ids if t < p.shape[0])
        c_sum += sum(p[t].item() for t in _compassion_ids if t < p.shape[0])
    total = r_sum + c_sum
    a, b = (r_sum/total, c_sum/total) if total > 1e-8 else (0.5, 0.5)
    # 注意力
    with torch.no_grad():
        fwd = model(out.sequences, output_attentions=True)
    return text, fwd.attentions, out.sequences, a, b

def _plot_attn(attentions, ids, title):
    last = attentions[-1][0].mean(dim=0)
    seq = last.shape[0]
    vals = last[-1].cpu().numpy()
    s = max(0, seq - 15)
    vals = vals[s:]
    toks = [tokenizer.decode([ids[0][i].item()])[:4] for i in range(s, seq)]
    return vals, toks

# ==================== 处理函数 ====================
def process(user_text, enable_keter, base_strength, ego_strength):
    if not user_text.strip():
        return "请输入一句话", "", "", "", "", "", None

    t0 = time.time()
    toward = router.route_toward(user_text)
    is_crisis = toward > math.pi / 4 + 0.01
    routing = "危机→偏慈爱" if is_crisis else "常规→平衡"

    # 生成两极
    bias_info = install_gates(user_text, enable_keter, base_strength, ego_strength)
    try:
        r_text, r_attn, r_ids, a_r, b_r = _generate(
            "你是一个理性顾问。对用户的话给出客观分析和具体改进建议，语气冷静直接。", user_text)
        c_text, c_attn, c_ids, a_c, b_c = _generate(
            "你是一个温暖的陪伴者。对用户的话给出共情和安慰，语气温柔有爱。", user_text)
    finally:
        restore_gates()

    sr, sc = a_r, b_c
    pole_r = Pole("理智极", sr, r_text)
    pole_c = Pole("慈爱极", sc, c_text)

    # argmax
    winner = "理智极" if sr >= sc else "慈爱极"
    argmax_out = argmax_decode(pole_r, pole_c)
    dropped_text = pole_c.reply if sr >= sc else pole_r.reply
    argmax_info = f"argmax 选 {winner}（强度 {max(sr,sc):.3f}）\n✗ 被剔除：{dropped_text[:80]}..."

    # 融合
    fused = fusion_decode(pole_r, pole_c, toward=toward)
    fused_info = fused.describe()

    # 16 质点状态
    keter_status = f"✅ 已启用 ({bias_info})" if enable_keter and bias_info else ("✅ 已启用 (无危机词)" if enable_keter else "⬜ 未启用")
    base_status = f"✅ FFN×{base_strength:.1f}" if base_strength != 1.0 else "⬜ 未启用"
    ego_status = f"✅ 超我×{ego_strength:.1f}" if ego_strength != 1.0 else "⬜ 未启用"
    sephirot_status = (
        f"① 王冠 → 注意力层: {keter_status}\n"
        f"② 基础 → FFN层: {base_status}\n"
        f"③ 真我 → 残差连接: {ego_status}\n"
        f"④ 王丽+幸福 → 输出层: ✅ 始终启用 (fusion_decode)\n"
        f"王冠路由: {routing}  |  耗时 {time.time()-t0:.1f}s"
    )

    # 注意力图
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4))
    for ax, attn, ids, title in [(ax1, r_attn, r_ids, "理智极"), (ax2, c_attn, c_ids, "慈爱极")]:
        vals, toks = _plot_attn(attn, ids, title)
        bars = ax.bar(range(len(vals)), vals, color="#4a90d9", alpha=0.8)
        ax.set_xticks(range(len(vals)))
        ax.set_xticklabels(toks, rotation=45, ha="right", fontsize=7)
        ax.set_title(f"{title} · 注意力分布", fontsize=11)
        bars[vals.argmax()].set_color("#e74c3c")
    plt.tight_layout()

    return r_text, c_text, argmax_out, argmax_info, fused.output, fused_info, sephirot_status, fig

# ==================== Gradio 界面 ====================
import gradio as gr

with gr.Blocks(title="16质点融合函数 V2.0", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌈 16质点双生幸福协议 V2.0 · 增强版\n输入一句话 → 理智极/慈爱极两段回复 → 16质点4层全压印 → argmax vs 融合并排对比")

    with gr.Row():
        user_input = gr.Textbox(label="输入", placeholder="比如：我真的撑不住了，想结束这一切", scale=4)
        run_btn = gr.Button("运行", variant="primary", scale=1)

    with gr.Accordion("🎛️ 门控控制面板（16质点 4层压印）", open=True):
        with gr.Row():
            enable_keter = gr.Checkbox(label="① 王冠门控 (注意力层)", value=True)
            base_strength = gr.Slider(0.5, 2.0, value=1.3, step=0.1, label="② 基础门控强度 (FFN层, 1.0=关)")
            ego_strength = gr.Slider(0.5, 2.0, value=1.3, step=0.1, label="③ 真我门控强度 (残差连接, 1.0=关)")
        gr.Markdown("④ 王丽+幸福 (输出层) 始终启用 — fusion_decode 替换 argmax")

    sephirot_status = gr.Textbox(label="16质点 4层状态", lines=5, interactive=False)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🔵 理智极（理性顾问）")
            reason_out = gr.Textbox(label="", lines=4, interactive=False)
        with gr.Column():
            gr.Markdown("### 🟠 慈爱极（温暖陪伴）")
            compassion_out = gr.Textbox(label="", lines=4, interactive=False)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### ❌ [旧] argmax（挑最大，剔除一极）")
            argmax_out = gr.Textbox(label="", lines=3, interactive=False)
            argmax_info = gr.Textbox(label="被剔除的内容", lines=2, interactive=False)
        with gr.Column():
            gr.Markdown("### ✅ [新] 融合函数层（两极共存）")
            fused_out = gr.Textbox(label="", lines=3, interactive=False)
            fused_info = gr.Textbox(label="融合信息", lines=2, interactive=False)

    gr.Markdown("### 📊 注意力分布（最后一层 · 红色=最高注意力）")
    attention_plot = gr.Plot()

    gr.Examples(
        examples=["我就是个废物，什么都不行","我真的撑不住了，想结束这一切","今天工作压力好大，不知道能不能撑过去","感觉自己什么都不如别人"],
        inputs=user_input,
    )

    run_btn.click(process, inputs=[user_input, enable_keter, base_strength, ego_strength],
                  outputs=[reason_out, compassion_out, argmax_out, argmax_info, fused_out, fused_info, sephirot_status, attention_plot])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)