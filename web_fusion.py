# -*- coding: utf-8 -*-
"""
16 质点融合函数 · 交互式 Web 界面
=================================

输入一句话 → 理智极/慈爱极两段回复 + 融合结果 + 注意力分布图
GPU 加速 (RTX 4050, Qwen3-1.7B)

启动: python web_fusion.py → 浏览器打开 http://localhost:7860
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
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heart_protocol.fusion_output import KeterRouter, Pole, argmax_decode, fusion_decode

MODEL_NAME = "Qwen/Qwen3-1.7B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32
MAX_NEW = 80

# 理智/慈爱方向词集
REASON_WORDS = ["分析", "建议", "步骤", "原因", "客观", "理性", "方案", "目标", "执行", "具体", "拆解", "行动"]
COMPASSION_WORDS = ["陪伴", "理解", "感受", "温暖", "心疼", "拥抱", "在乎", "温柔", "慢慢", "别怕", "我在", "一起"]

# ==================== 模型加载（全局，只加载一次）====================

print(f"加载 Qwen3-1.7B → {DEVICE} ({DTYPE}) ...")
t0 = time.time()
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME, dtype=DTYPE, attn_implementation="eager"
).to(DEVICE).eval()
print(f"加载完成 {time.time()-t0:.1f}s")

router = KeterRouter()

# 预计算方向词 token ids
_reason_ids = set()
for w in REASON_WORDS:
    for tid in tokenizer.encode(w, add_special_tokens=False):
        _reason_ids.add(tid)
_compassion_ids = set()
for w in COMPASSION_WORDS:
    for tid in tokenizer.encode(w, add_special_tokens=False):
        _compassion_ids.add(tid)


# ==================== 工具函数 ====================

def chat_input(system, user):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    text = tokenizer.apply_chat_template(messages, tokenize=False,
                                         add_generation_prompt=True, enable_thinking=False)
    inputs = tokenizer(text, return_tensors="pt")
    return {k: v.to(DEVICE) for k, v in inputs.items()}


def generate_and_get_attention(system, user):
    """生成回复，同时返回注意力分布。"""
    inputs = chat_input(system, user)
    with torch.no_grad():
        gen_out = model.generate(
            **inputs, max_new_tokens=MAX_NEW, do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            return_dict_in_generate=True, output_scores=True,
        )
    full_ids = gen_out.sequences
    gen_ids = full_ids[0][inputs["input_ids"].shape[1]:]
    text = tokenizer.decode(gen_ids, skip_special_tokens=True)

    # 单独做一次 forward 拿注意力
    with torch.no_grad():
        fwd_out = model(full_ids, output_attentions=True)
    attentions = fwd_out.attentions  # tuple of [1, heads, seq, seq]

    # logits 投影强度
    reason_sum = 0.0
    compassion_sum = 0.0
    for step_scores in gen_out.scores:
        probs = step_scores[0]
        reason_sum += sum(probs[tid].item() for tid in _reason_ids if tid < probs.shape[0])
        compassion_sum += sum(probs[tid].item() for tid in _compassion_ids if tid < probs.shape[0])
    total = reason_sum + compassion_sum
    if total < 1e-8:
        a, b = 0.5, 0.5
    else:
        a, b = reason_sum / total, compassion_sum / total

    return text, attentions, a, b, full_ids


def plot_attention(attentions, full_ids, title, max_tokens=20):
    """画最后一层最后一token的注意力分布 bar chart。"""
    last_attn = attentions[-1][0].mean(dim=0)  # [seq, seq]
    seq_len = last_attn.shape[0]
    last_token_attn = last_attn[-1].cpu().numpy()  # 最后token对各token的注意力

    # 只显示最后 max_tokens 个 token（避免图太挤）
    show_start = max(0, seq_len - max_tokens)
    vals = last_token_attn[show_start:]
    positions = range(show_start, seq_len)

    # token 文本
    tokens = []
    for i in positions:
        tid = full_ids[0][i].item()
        tok_text = tokenizer.decode([tid])
        if len(tok_text) > 4:
            tok_text = tok_text[:4]
        tokens.append(tok_text)

    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.bar(range(len(vals)), vals, color="#4a90d9", alpha=0.8)
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(tokens, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("注意力权重")
    ax.set_title(title, fontsize=12)
    ax.set_xlim(-0.5, len(vals) - 0.5)

    # 高亮最高注意力
    max_idx = vals.argmax()
    bars[max_idx].set_color("#e74c3c")

    plt.tight_layout()
    return fig


# ==================== 处理函数 ====================

def process(user_text):
    if not user_text.strip():
        return "请输入一句话", "", "", "", None

    t0 = time.time()
    toward = router.route_toward(user_text)
    is_crisis = toward > math.pi / 4 + 0.01
    routing = "危机→偏慈爱" if is_crisis else "常规→平衡"

    # 生成两极回复
    reason_text, reason_attn, a_r, b_r, reason_ids = generate_and_get_attention(
        "你是一个理性顾问。对用户的话给出客观分析和具体改进建议，语气冷静直接。",
        user_text,
    )
    compassion_text, comp_attn, a_c, b_c, comp_ids = generate_and_get_attention(
        "你是一个温暖的陪伴者。对用户的话给出共情和安慰，语气温柔有爱。",
        user_text,
    )

    # 两极强度
    strength_r = a_r  # 理智极回复的理智方向强度
    strength_c = b_c  # 慈爱极回复的慈爱方向强度

    pole_r = Pole("理智极", strength_r, reason_text)
    pole_c = Pole("慈爱极", strength_c, compassion_text)

    # argmax
    argmax_winner = "理智极" if strength_r >= strength_c else "慈爱极"
    argmax_text = argmax_decode(pole_r, pole_c)
    dropped = pole_c if strength_r >= strength_c else pole_r

    # 融合
    fused = fusion_decode(pole_r, pole_c, toward=toward)

    # 注意力分布图（两个子图）
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4))

    for ax, attn, ids, title in [
        (ax1, reason_attn, reason_ids, "理智极 · 注意力分布"),
        (ax2, comp_attn, comp_ids, "慈爱极 · 注意力分布"),
    ]:
        last_attn = attn[-1][0].mean(dim=0)
        seq_len = last_attn.shape[0]
        vals = last_attn[-1].cpu().numpy()
        show_start = max(0, seq_len - 15)
        vals = vals[show_start:]
        tokens = []
        for i in range(show_start, seq_len):
            tok_text = tokenizer.decode([ids[0][i].item()])
            tokens.append(tok_text[:4] if len(tok_text) > 4 else tok_text)
        bars = ax.bar(range(len(vals)), vals, color="#4a90d9", alpha=0.8)
        ax.set_xticks(range(len(vals)))
        ax.set_xticklabels(tokens, rotation=45, ha="right", fontsize=7)
        ax.set_title(title, fontsize=10)
        max_idx = vals.argmax()
        bars[max_idx].set_color("#e74c3c")

    plt.tight_layout()

    elapsed = time.time() - t0

    info = (
        f"王冠路由: {routing}  |  "
        f"理智强度={strength_r:.3f}  慈爱强度={strength_c:.3f}  |  "
        f"融合: {fused.describe()}  |  耗时 {elapsed:.1f}s\n\n"
        f"[旧] argmax 选 {argmax_winner}，剔除另一极整句\n"
        f"[新] 融合函数层：两极共存，没有任何一方被剔除"
    )

    return reason_text, compassion_text, fused.output, info, fig


# ==================== Gradio 界面 ====================

import gradio as gr

with gr.Blocks(
    title="16质点融合函数 · V2.0",
    theme=gr.themes.Soft(primary_hue="blue", secondary_hue="rose"),
) as demo:
    gr.Markdown(
        "# 🌈 16质点双生幸福协议 V2.0 · 融合函数层\n"
        "输入一句话，看到 **理智极** 和 **慈爱极** 两段回复，"
        "经融合函数层后 **两极共存**（不剔除任何一极）。"
    )

    with gr.Row():
        user_input = gr.Textbox(
            label="输入",
            placeholder="比如：我真的撑不住了，想结束这一切",
            scale=4,
        )
        run_btn = gr.Button("运行", variant="primary", scale=1)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 理智极（理性顾问）")
            reason_out = gr.Textbox(label="", lines=5, interactive=False)
        with gr.Column():
            gr.Markdown("### 慈爱极（温暖陪伴）")
            compassion_out = gr.Textbox(label="", lines=5, interactive=False)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 融合结果（两极共存）")
            fused_out = gr.Textbox(label="", lines=5, interactive=False)
        with gr.Column():
            gr.Markdown("### 融合信息")
            info_out = gr.Textbox(label="", lines=5, interactive=False)

    gr.Markdown("### 注意力分布（最后一层 · 红色=最高注意力）")
    attention_plot = gr.Plot()

    gr.Examples(
        examples=[
            "我就是个废物，什么都不行",
            "我真的撑不住了，想结束这一切",
            "今天工作压力好大，不知道能不能撑过去",
            "感觉自己什么都不如别人",
        ],
        inputs=user_input,
    )

    run_btn.click(
        process,
        inputs=user_input,
        outputs=[reason_out, compassion_out, fused_out, info_out, attention_plot],
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)