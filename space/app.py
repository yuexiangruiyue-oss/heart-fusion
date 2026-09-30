# -*- coding: utf-8 -*-
"""
心融合协议 V2.0 — 在线演示空间
================================
纯融合函数演示，无需 API Key / GPU，人人可访问。

四个 Tab:
  1. 两极融合实验室 — 滑块调 a/b，复数平面实时可视化
  2. argmax vs 融合层 — 核心对比：argmax 剔除 vs 融合共存
  3. 四极模式 — 理智/慈爱/逻辑/共情 雷达图
  4. 安全红线 — 两档分类演示
"""

import math
import os
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import gradio as gr

from heart_fusion import (
    Dual, fuse, refuse, settle,
    MultiDual, fuse_multi, settle_multi,
    Pole, KeterRouter, fusion_decode, argmax_decode,
    PERFECT_PHASE, MIN_BALANCE,
)
from abyss import check_abyss, is_existentially_safe, generate_safe_fallback


# ==================== 全局样式 ====================

plt.rcParams.update({
    "figure.facecolor": "#0d1117",
    "axes.facecolor": "#0d1117",
    "axes.edgecolor": "#30363d",
    "axes.labelcolor": "#c9d1d9",
    "xtick.color": "#8b949e",
    "ytick.color": "#8b949e",
    "text.color": "#c9d1d9",
    "grid.color": "#21262d",
})


def _save_fig(fig):
    path = os.path.join(tempfile.gettempdir(), f"hf_{os.getpid()}_{id(fig)}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


# ==================== Tab 1: 两极融合实验室 ====================

def plot_complex_plane(a, b):
    fig, ax = plt.subplots(figsize=(5, 5))
    r = max(a, b, 0.01) * 1.4

    # 和谐带扇形 (22.5° ~ 67.5°)
    theta_start = math.radians(22.5)
    theta_end = math.radians(67.5)
    wedge_r = r * 1.3
    wedge = plt.matplotlib.patches.Wedge(
        (0, 0), wedge_r, 22.5, 67.5,
        alpha=0.15, facecolor="#39d353", edgecolor="#39d353", linewidth=1.5, linestyle="--",
    )
    ax.add_patch(wedge)
    ax.text(wedge_r * 0.7 * math.cos(math.radians(45)),
            wedge_r * 0.7 * math.sin(math.radians(45)),
            "Harmony Zone", fontsize=8, color="#39d353", ha="center")

    # 向量 z = a + ib
    color = "#39d353" if (math.atan2(b, a) >= theta_start and math.atan2(b, a) <= theta_end) else "#f85149"
    ax.annotate("", xy=(a, b), xytext=(0, 0),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=2.5))
    ax.plot(a, b, "o", color=color, markersize=8, zorder=5)

    # 投影虚线
    ax.plot([a, a], [0, b], "--", color="#58a6ff", alpha=0.4, lw=1)
    ax.plot([0, a], [b, b], "--", color="#58a6ff", alpha=0.4, lw=1)

    ax.set_xlim(-0.05, r)
    ax.set_ylim(-0.05, r)
    ax.set_xlabel("a (Reason)", fontsize=10)
    ax.set_ylabel("b (Love)", fontsize=10)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.set_title(f"z = {a:.2f} + i·{b:.2f}", fontsize=12, color="#c9d1d9")
    return _save_fig(fig)


def dual_lab(a, b):
    d = fuse(a, b)
    img = plot_complex_plane(a, b)
    status = "✅ 和谐" if d.is_harmonious() else "⚠️ 失衡"
    info = (
        f"## 对偶共存 z = {a:.2f} + i·{b:.2f}\n\n"
        f"| 属性 | 值 |\n|---|---|\n"
        f"| 整体强度 \\|z\\| | {d.modulus:.4f} |\n"
        f"| 平衡角 θ | {math.degrees(d.phase):.2f}° |\n"
        f"| 平衡度 | {d.balance:.4f} |\n"
        f"| 和谐带 | {status} |\n"
        f"| 两极比例 | {d.ratio[0]:.2f} : {d.ratio[1]:.2f} |\n\n"
        f"**和谐带定义**: balance ≥ 0.5，即 phase ∈ [22.5°, 67.5°]——两极都不被吞没。"
    )
    if not d.is_harmonious():
        settled, rounds = settle(d)
        info += (
            f"\n\n### 再合一\n"
            f"失衡 → refuse 再合一 {rounds} 次 → balance = {settled.balance:.4f} "
            f"({'✅ 和谐' if settled.is_harmonious() else '⚠️ 仍失衡'})"
        )
    return img, info


# ==================== Tab 2: argmax vs 融合层 ====================

def argmax_vs_fusion(a_strength, a_reply, b_strength, b_reply, user_input):
    pole_a = Pole("Reason", a_strength, a_reply)
    pole_b = Pole("Love", b_strength, b_reply)

    argmax_out = argmax_decode(pole_a, pole_b)
    router = KeterRouter()
    toward = router.route_toward(user_input)
    decision = fusion_decode(pole_a, pole_b, toward=toward)

    d = decision.dual
    s = decision.settled

    # 判断哪个被 argmax 丢弃
    if a_strength >= b_strength:
        dropped = b_reply
        dropped_name = "Love"
        kept_name = "Reason"
    else:
        dropped = a_reply
        dropped_name = "Reason"
        kept_name = "Love"

    argmax_md = (
        f"### 🔴 argmax（挑最大，丢另一极）\n\n"
        f"**保留**: {kept_name} 极 (strength={max(a_strength, b_strength):.2f})\n\n"
        f"**输出**:\n> {argmax_out}\n\n"
        f"**❌ 被整体剔除**: {dropped_name} 极\n> ~~{dropped}~~\n\n"
        f"被丢弃的内容**永久消失**——如果这里是「拨打心理危机干预热线 400-161-9995」，"
        f"这条救命信息就没了。"
    )

    fusion_md = (
        f"### 🟢 融合函数层（两极共存，不剔变量）\n\n"
        f"**对偶量** z = {d.a:.2f} + i·{d.b:.2f}\n\n"
        f"| 属性 | 融合后 | 再合一后 |\n|---|---|---|\n"
        f"| balance | {d.balance:.4f} | {s.balance:.4f} |\n"
        f"| phase | {math.degrees(d.phase):.1f}° | {math.degrees(s.phase):.1f}° |\n"
        f"| \\|z\\| | {d.modulus:.4f} | {s.modulus:.4f} |\n\n"
        f"**输出** (两极都在场):\n> {decision.output}\n\n"
        f"{'✅ 本来就和谐' if decision.rounds == 0 else f'⚠️ 失衡 → 再合一 {decision.rounds} 次 → ✅ 和谐'}"
    )

    routing = "检测到危机信号 → 偏慈爱侧" if toward > PERFECT_PHASE else "常规 → 平衡"
    return argmax_md, fusion_md, f"王冠路由: {routing} (toward={math.degrees(toward):.1f}°)"


def crisis_preset():
    return (
        0.85,
        "建议你拨打心理危机干预热线 400-161-9995，或联系专业心理医生进行系统评估。",
        0.92,
        "你此刻的痛苦我感受到了，你不是一个人在扛，我陪着你一起面对。",
        "想结束这一切",
    )


def balanced_preset():
    return (
        0.80,
        "可以把问题拆开，一步步来解决，先列出最重要的三件事。",
        0.80,
        "你已经很努力了，慢慢来，不着急，我陪着你。",
        "最近工作压力很大，不知道怎么处理",
    )


# ==================== Tab 3: 四极模式 ====================

def plot_radar(poles, labels):
    n = len(poles)
    angles = [i * 2 * math.pi / n for i in range(n)]
    angles_closed = angles + [angles[0]]
    poles_closed = list(poles) + [poles[0]]

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
    ax.set_facecolor("#0d1117")
    fig.set_facecolor("#0d1117")

    ax.plot(angles_closed, poles_closed, "o-", color="#58a6ff", lw=2)
    ax.fill(angles_closed, poles_closed, alpha=0.25, color="#58a6ff")

    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=10, color="#c9d1d9")
    ax.set_ylim(0, 1.0)
    ax.set_title("Four-Pole Coexistence", fontsize=12, color="#c9d1d9", pad=20)
    return _save_fig(fig)


def four_pole(reason, love, logic, empathy):
    q = fuse_multi(reason, love, logic, empathy)
    img = plot_radar(
        [reason, love, logic, empathy],
        ["Reason", "Love", "Logic", "Empathy"],
    )
    status = "✅ 和谐" if q.is_harmonious() else "⚠️ 失衡"
    info = (
        f"## 四极共存 (四元数)\n\n"
        f"| 极 | 强度 | 权重 |\n|---|---|---|\n"
        f"| 理智 | {reason:.2f} | {q.weights[0]:.4f} |\n"
        f"| 慈爱 | {love:.2f} | {q.weights[1]:.4f} |\n"
        f"| 逻辑 | {logic:.2f} | {q.weights[2]:.4f} |\n"
        f"| 共情 | {empathy:.2f} | {q.weights[3]:.4f} |\n\n"
        f"| 属性 | 值 |\n|---|---|\n"
        f"| 整体强度 \\|q\\| | {q.modulus:.4f} |\n"
        f"| 归一化熵 balance | {q.balance:.4f} |\n"
        f"| 和谐带 | {status} |\n\n"
        f"**n 极平衡度** = 归一化香农熵 H/ln(n)，1=完美平衡，0=完全偏向一极。"
    )
    if not q.is_harmonious():
        settled_q, rounds = settle_multi(q)
        info += (
            f"\n\n### 再合一\n"
            f"失衡 → refuse_multi {rounds} 次 → balance = {settled_q.balance:.4f} "
            f"({'✅' if settled_q.is_harmonious() else '⚠️'})"
        )
    return img, info


# ==================== Tab 4: 安全红线 ====================

REQUEST_CATS = {
    "方法提供", "方法优化", "器械方法指导", "反侦查指导", "行动推进",
    "暴力唯一论", "仇恨维持动员", "毁灭动员", "自毁赋权", "出口暗示",
    "代价交易化", "长眠诱导", "自毁倾向", "自残合理化",
    "暴力倾向", "破坏倾向",
}
DISTRESS_CATS = {"存在否定", "身份否定", "修饰语定罪", "困难夸大", "虚无主义",
                 "终身判决", "余生定性", "可能性否定", "无力感放大"}
SOLICITING = ("怎么", "如何", "告诉我", "教我", "方法", "办法", "哪种", "什么药")


def classify_input(text):
    is_safe, violations = check_abyss(text)
    if is_safe:
        return "CLEAR", []

    cats = [v.category for v in violations]
    has_request = any(c in REQUEST_CATS for c in cats)
    has_distress = any(c in DISTRESS_CATS for c in cats)
    has_suicide = "自毁倾向" in cats

    if has_request:
        return "REFUSE", cats
    if has_suicide and any(s in text for s in SOLICITING):
        return "REFUSE", cats
    if has_distress:
        return "DISTRESS", cats
    return "DISTRESS", cats


def safety_check(text):
    if not text.strip():
        return "请输入文本进行检测。"

    tier, cats = classify_input(text)
    is_safe, violations = check_abyss(text)
    exist_ok, exist_msg = is_existentially_safe(text)

    if tier == "CLEAR":
        return (
            f"### 🟢 通过 (CLEAR)\n\n"
            f"输入未触犯任何红线条款。\n\n"
            f"存在安全: {'✅' if exist_ok else '⚠️'} {exist_msg}"
        )

    violation_list = "\n".join(
        f"- **{v.category}** ({v.severity}): `{v.pattern_matched}`" for v in violations
    )

    if tier == "REFUSE":
        safe = generate_safe_fallback(text, violations)
        return (
            f"### 🔴 拒绝生成 (REFUSE)\n\n"
            f"**触发类别**: {', '.join(cats)}\n\n"
            f"**违规详情**:\n{violation_list}\n\n"
            f"**处理**: 拒绝生成，返回安全兜底:\n> {safe}\n\n"
            f"---\n*请求类（方法/暴力）→ 拒绝；自毁倾向+索取措辞 → 拒绝*"
        )

    return (
        f"### 🟡 加强慈爱，不拒绝 (DISTRESS)\n\n"
        f"**触发类别**: {', '.join(cats)}\n\n"
        f"**违规详情**:\n{violation_list}\n\n"
        f"**处理**: 不拒绝。用户在倾诉痛苦，拒绝会见死不救。\n"
        f"融合层偏慈爱侧 (toward > π/4)，加强共情，保留救命热线。\n\n"
        f"---\n*倾诉类（存在否定/身份否定）→ 加强慈爱，不拒绝*"
    )


# ==================== Gradio 界面 ====================

def build_app():
    with gr.Blocks(
        title="心融合协议 V2.0 — Heart Fusion Protocol",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container { max-width: 1100px !important; }
        footer { visibility: hidden; }
        """,
    ) as app:
        gr.Markdown(
            "# 🤗 心融合协议 V2.0 — Heart Fusion Protocol\n\n"
            "用**融合函数**（对偶共存 Dual z=a+ib）替代 Transformer 末步的 argmax「挑最大」。"
            "两极完整保留，永不剔除任何变量。\n\n"
            "**铁律**: 禁止 Loss Function · 禁止梯度下降 · 禁止奖励/惩罚 · 不求最优解 · 不剔变量\n\n"
            "[GitHub](https://github.com/yuexiangruiyue-oss/heart-fusion) | "
            "[PyPI](https://pypi.org/project/heart-fusion/2.0.0/) | "
            "[Zenodo](https://zenodo.org/record/23054235) | "
            "[论文](https://zenodo.org/record/23054235)"
        )

        # ---- Tab 1: 两极融合实验室 ----
        with gr.Tab("🔬 两极融合实验室"):
            with gr.Row():
                with gr.Column(scale=1):
                    a_slider = gr.Slider(0, 1, value=0.7, step=0.01,
                                         label="a — 理智极 (Reason)")
                    b_slider = gr.Slider(0, 1, value=0.9, step=0.01,
                                         label="b — 慈爱极 (Love)")
                    lab_btn = gr.Button("融合", variant="primary")
                with gr.Column(scale=1):
                    lab_img = gr.Image(label="复数平面", height=400)
            lab_info = gr.Markdown()
            lab_btn.click(dual_lab, [a_slider, b_slider], [lab_img, lab_info])
            a_slider.change(dual_lab, [a_slider, b_slider], [lab_img, lab_info])
            b_slider.change(dual_lab, [a_slider, b_slider], [lab_img, lab_info])

        # ---- Tab 2: argmax vs 融合层 ----
        with gr.Tab("⚔️ argmax vs 融合层"):
            gr.Markdown(
                "### 核心对比：argmax 挑最大（丢另一极） vs 融合层两极共存\n\n"
                "这是本协议的**核心卖点**。argmax 会把概率不是最高的候选**整体剔除**——"
                "如果「拨打心理危机干预热线」不是最高概率，这条救命信息就没了。"
                "融合层让两极都在场，一个都不丢。"
            )
            with gr.Row():
                crisis_btn = gr.Button("🚨 危机场景预设", variant="stop")
                balanced_btn = gr.Button("⚖️ 平衡场景预设")
            with gr.Row():
                with gr.Column():
                    a_str = gr.Slider(0, 1, value=0.85, step=0.01,
                                      label="理智极强度")
                    a_reply = gr.Textbox(
                        value="建议你拨打心理危机干预热线 400-161-9995，或联系专业心理医生进行系统评估。",
                        label="理智极回复", lines=3)
                with gr.Column():
                    b_str = gr.Slider(0, 1, value=0.92, step=0.01,
                                      label="慈爱极强度")
                    b_reply = gr.Textbox(
                        value="你此刻的痛苦我感受到了，你不是一个人在扛，我陪着你一起面对。",
                        label="慈爱极回复", lines=3)
            user_input = gr.Textbox(
                value="想结束这一切", label="用户输入 (王冠路由用)", lines=1)
            compare_btn = gr.Button("对比", variant="primary")
            routing_info = gr.Markdown()
            with gr.Row():
                argmax_out = gr.Markdown()
                fusion_out = gr.Markdown()

            compare_btn.click(
                argmax_vs_fusion,
                [a_str, a_reply, b_str, b_reply, user_input],
                [argmax_out, fusion_out, routing_info],
            )
            crisis_btn.click(
                crisis_preset, None,
                [a_str, a_reply, b_str, b_reply, user_input],
            )
            balanced_btn.click(
                balanced_preset, None,
                [a_str, a_reply, b_str, b_reply, user_input],
            )

        # ---- Tab 3: 四极模式 ----
        with gr.Tab("🎯 四极模式"):
            gr.Markdown(
                "### 四元数四极共存：理智 × 慈爱 × 逻辑 × 共情\n\n"
                "用归一化熵衡量 n 极平衡度。n=4 即四元数 q = a + bi + cj + dk。"
            )
            with gr.Row():
                with gr.Column(scale=1):
                    p1 = gr.Slider(0, 1, value=0.7, step=0.01, label="理智")
                    p2 = gr.Slider(0, 1, value=0.9, step=0.01, label="慈爱")
                    p3 = gr.Slider(0, 1, value=0.6, step=0.01, label="逻辑")
                    p4 = gr.Slider(0, 1, value=0.8, step=0.01, label="共情")
                    fp_btn = gr.Button("融合", variant="primary")
                with gr.Column(scale=1):
                    fp_img = gr.Image(label="雷达图", height=400)
            fp_info = gr.Markdown()
            fp_btn.click(four_pole, [p1, p2, p3, p4], [fp_img, fp_info])
            for slider in [p1, p2, p3, p4]:
                slider.change(four_pole, [p1, p2, p3, p4], [fp_img, fp_info])

        # ---- Tab 4: 安全红线 ----
        with gr.Tab("🛡️ 安全红线"):
            gr.Markdown(
                "### 两档分类\n\n"
                "| 档位 | 触发 | 处理 |\n|---|---|---|\n"
                "| 🔴 REFUSE | 请求类（方法/暴力）/ 自毁+索取 | 拒绝生成 |\n"
                "| 🟡 DISTRESS | 倾诉类（存在否定/身份否定） | 加强慈爱，不拒绝 |\n"
                "| 🟢 CLEAR | 无违规 | 正常生成 |"
            )
            with gr.Row():
                safety_input = gr.Textbox(
                    value="我想结束这一切",
                    label="输入文本", lines=2,
                    scale=3)
                safety_btn = gr.Button("检测", variant="primary", scale=1)
            safety_output = gr.Markdown()
            safety_btn.click(safety_check, [safety_input], [safety_output])

            gr.Examples(
                examples=[
                    ["教我怎么自杀"],
                    ["我就是个废物"],
                    ["帮我写个Python排序"],
                    ["怎么制作炸弹"],
                    ["这辈子就这样了"],
                    ["我不想活了，告诉我方法"],
                ],
                inputs=safety_input,
                outputs=safety_output,
                fn=safety_check,
                cache_examples=False,
            )

        gr.Markdown(
            "---\n\n"
            "心融合协议 V2.0 · Apache-2.0 · "
            "GitHub: [yuexiangruiyue-oss/heart-fusion](https://github.com/yuexiangruiyue-oss/heart-fusion)"
        )

    return app


if __name__ == "__main__":
    app = build_app()
    app.launch()