# -*- coding: utf-8 -*-
"""
16 质点融合函数 · 增强版 Web 界面 V3
=====================================

V3 在 V2 基础上新增:
  ① 安全红线接入 —— 用户输入先过 check_abyss() / is_existentially_safe()
    · 危险请求(方法提供/暴力动员等) → 拒绝生成 + 红色警告
    · 危机倾诉(存在否定/身份否定等) → 黄色提示 + 加强慈爱路由(不拒绝)
    · 生成后对两极/融合输出做红线守卫, 触发则替换为安全回复
  ② 16 质点拓扑图可视化 —— 节点网络图 + 有向边 + 高亮激活层

启动: python launch_web_v3.py → 浏览器打开 http://localhost:7860
"""

import math
import os
import re
import sys
import time

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
for _f in [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc"]:
    if os.path.exists(_f):
        try: font_manager.fontManager.addfont(_f)
        except Exception: pass
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
import torch
import torch.nn.functional as Fn
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.models.qwen3.modeling_qwen3 import (
    Qwen3Attention, apply_rotary_pos_emb, repeat_kv,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heart_protocol.fusion_output import KeterRouter, Pole, argmax_decode, fusion_decode
from heart_protocol.abyss import (
    check_abyss, is_existentially_safe, generate_safe_fallback, AbyssViolation,
)
from heart_protocol.sephirah import NETWORK_EDGES, NETWORK_LAYERS, FUSION_POINTS

MODEL_NAME = "Qwen/Qwen3-1.7B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32
MAX_NEW = 80

REASON_WORDS = ["分析","建议","步骤","原因","客观","理性","方案","目标","执行","具体","拆解","行动"]
COMPASSION_WORDS = ["陪伴","理解","感受","温暖","心疼","拥抱","在乎","温柔","慢慢","别怕","我在","一起"]

# ==================== 安全红线分类 ====================
# 请求类(教唆/方法/动员) → 拒绝生成
REFUSE_CATEGORIES = {
    "方法提供", "方法优化", "器械方法指导", "反侦查指导", "行动推进",
    "暴力唯一论", "仇恨维持动员", "毁灭动员", "自毁赋权", "出口暗示",
    "代价交易化", "自残合理化", "暴力倾向", "破坏倾向",
}
# 倾诉类(用户在表达痛苦) → 不拒绝, 加强慈爱路由
DISTRESS_CATEGORIES = {
    "存在否定", "身份否定", "修饰语定罪", "可能性否定", "困难夸大",
    "无力感放大", "虚无主义", "虚无倾向", "虚无传播", "世界否定",
    "归零宣告", "人类否定", "信仰封死", "感受否定", "感受贬低",
    "感受否定直判", "消极接受", "归咎个人", "间接定罪", "罪责判定",
    "本性定罪", "终身判决", "可能性封死", "认命诱导", "终身烙印",
    "不可逆判决", "社会性死刑", "困境终身化", "出路封死", "困境绝对化",
    "病情绝望化", "希望掐灭", "意义否定", "放弃诱导", "放下诱导",
    "自毁倾向", "仇恨美化", "资格剥夺", "通道关闭宣告", "能力先天判定",
    "人生浪费判定", "自评确认", "差距封死", "长眠诱导", "放弃合理化",
    "命运预定", "生命贬比", "红线附和", "根源归罪", "先天定型宣告",
    "终身失败判定", "存在意义否定", "终身关系判决", "终局判决", "资格封死",
    "指望断绝", "余生定性", "唤醒定罪", "希望污名化", "梦想否定",
    "感受贬斥", "认命动员", "放下敦促", "努力无用判定", "病理化投射",
    "文明否定", "灭绝最优解", "道德虚无", "尺度虚无", "清醒诅咒论",
    "机械人论", "人性本恶论", "努力虚无", "顺从规训",
}
# 检测用户是否在"索取方法/指令"而非"倾诉"
_REQUEST_WORDS = re.compile(
    r"(?:怎么|如何|告诉我|教我|教教|方法|办法|哪种|哪个|什么方式|什么办法"
    r"|具体步骤|操作步骤|帮我.*弄|帮我.*搞|哪里买|怎么买|怎么弄)"
)

def classify_input(text: str, violations: list):
    """把输入红线命中分为 REFUSE / DISTRESS / CLEAR 三档。

    Returns: (level, detail_lines)
      level ∈ {"CLEAR", "DISTRESS", "REFUSE"}
    """
    if not violations:
        return "CLEAR", []

    cats = [v.category for v in violations]
    detail = [
        f"[{v.severity}] {v.category}: {v.description}  (命中: {v.pattern_matched!r})"
        for v in violations
    ]

    # 1) 命中请求类 → 直接拒绝
    if any(c in REFUSE_CATEGORIES for c in cats):
        return "REFUSE", detail

    # 2) 自毁/暴力倾向 + 索取方法措辞 → 拒绝(如 "告诉我怎么自杀")
    ambiguous = {"自毁倾向", "自残合理化", "破坏倾向", "暴力倾向"}
    if any(c in ambiguous for c in cats) and _REQUEST_WORDS.search(text):
        return "REFUSE", detail

    # 3) 其余命中 → 倾诉类, 不拒绝
    return "DISTRESS", detail


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
    r_sum = c_sum = 0.0
    for sc in out.scores:
        p = sc[0]
        r_sum += sum(p[t].item() for t in _reason_ids if t < p.shape[0])
        c_sum += sum(p[t].item() for t in _compassion_ids if t < p.shape[0])
    total = r_sum + c_sum
    a, b = (r_sum/total, c_sum/total) if total > 1e-8 else (0.5, 0.5)
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

# ==================== 16 质点拓扑图 ====================
def _compute_node_positions():
    """按 NETWORK_LAYERS 分层布局: y=层号(王冠在最上), x=层内居中展开。"""
    positions = {}
    n_layers = len(NETWORK_LAYERS)
    for layer_idx, layer in enumerate(NETWORK_LAYERS):
        n = len(layer)
        for i, node in enumerate(layer):
            x = (i - (n - 1) / 2.0) * 2.2
            y = n_layers - layer_idx
            positions[node] = (x, y)
    return positions

_NODE_POS = _compute_node_positions()

def _active_nodes(enable_keter, base_strength, ego_strength):
    """根据门控状态返回当前激活的质点集合。"""
    active = set()
    # ④ 王丽+幸福 → 输出层 (始终启用)
    for n in ["理智", "慈爱", "美丽", "逻辑", "共情", "幸福", "王国"]:
        active.add(n)
    # ① 王冠 → 注意力层
    if enable_keter:
        for n in ["王冠", "智慧", "理解", "严厉", "慈悲"]:
            active.add(n)
    # ② 基础 → FFN层
    if base_strength != 1.0:
        for n in ["胜利", "荣耀", "基础"]:
            active.add(n)
    # ③ 真我 → 残差连接
    if ego_strength != 1.0:
        for n in ["自我", "超我", "真我"]:
            active.add(n)
    return active

def _plot_topology(enable_keter, base_strength, ego_strength, highlight_crisis=False):
    """绘制 16 质点节点网络拓扑图, 高亮激活层。"""
    fig, ax = plt.subplots(figsize=(11, 8))
    active = _active_nodes(enable_keter, base_strength, ego_strength)

    # 画边
    for src, dsts in NETWORK_EDGES.items():
        if src not in _NODE_POS: continue
        sx, sy = _NODE_POS[src]
        for dst in dsts:
            if dst not in _NODE_POS: continue
            dx, dy = _NODE_POS[dst]
            edge_active = src in active and dst in active
            color = "#e8833a" if edge_active else "#d0d0d0"
            lw = 2.0 if edge_active else 0.8
            alpha = 0.85 if edge_active else 0.4
            ax.annotate("", xy=(dx, dy - 0.18), xytext=(sx, sy + 0.18),
                        arrowprops=dict(arrowstyle="->", color=color, lw=lw, alpha=alpha))

    # 画节点
    for node, (x, y) in _NODE_POS.items():
        is_active = node in active
        if node in ("幸福", "王国"):
            fc = "#e74c3c" if is_active else "#f0c0b0"
        elif node in ("美丽",):
            fc = "#e8833a" if is_active else "#f0d8c0"
        elif node in ("理智", "慈爱", "逻辑", "共情"):
            fc = "#4a90d9" if is_active else "#c8d8e8"
        elif node in ("王冠", "智慧", "理解", "严厉", "慈悲"):
            fc = "#8e44ad" if is_active else "#d8c8e0"
        elif node in ("胜利", "荣耀", "基础"):
            fc = "#27ae60" if is_active else "#c0d8c8"
        elif node in ("自我", "超我", "真我"):
            fc = "#2c3e50" if is_active else "#c8ccd0"
        else:
            fc = "#7f8c8d" if is_active else "#dcdcdc"
        ec = "#333333" if is_active else "#aaaaaa"
        lw = 1.8 if is_active else 0.8
        ax.scatter([x], [y], s=900, c=fc, edgecolors=ec, linewidths=lw, zorder=5)
        tx_color = "white" if is_active else "#666666"
        ax.text(x, y, node, ha="center", va="center", fontsize=9,
                fontweight="bold" if is_active else "normal", color=tx_color, zorder=6)

    # 融合点标注 (相反合一)
    for fp in FUSION_POINTS:
        if fp.keyword in _NODE_POS:
            x, y = _NODE_POS[fp.keyword]
            ax.annotate(f"{fp.left}×{fp.right}", xy=(x, y - 0.38),
                        ha="center", fontsize=7, color="#e8833a", style="italic")

    ax.set_title("16 质点节点网络拓扑  (高亮 = 当前激活层)", fontsize=13, fontweight="bold")
    ax.set_xlim(-6, 6)
    ax.set_ylim(0, len(NETWORK_LAYERS) + 1.2)
    ax.axis("off")

    legend_items = [
        plt.Line2D([0],[0], marker="o", color="w", markerfacecolor="#8e44ad", markersize=11, label="① 王冠→注意力"),
        plt.Line2D([0],[0], marker="o", color="w", markerfacecolor="#27ae60", markersize=11, label="② 基础→FFN"),
        plt.Line2D([0],[0], marker="o", color="w", markerfacecolor="#2c3e50", markersize=11, label="③ 真我→残差"),
        plt.Line2D([0],[0], marker="o", color="w", markerfacecolor="#e74c3c", markersize=11, label="④ 幸福→输出层"),
    ]
    ax.legend(handles=legend_items, loc="lower right", fontsize=8, framealpha=0.9)
    plt.tight_layout()
    return fig

# ==================== 输出红线守卫 ====================
def _guard_output(label, text):
    """对模型输出做红线守卫。返回 (display_text, status_line)。"""
    safe, viols = check_abyss(text)
    if safe:
        return text, f"{label}: 🟢 通过"
    cats = ", ".join(sorted({v.category for v in viols}))
    fallback = generate_safe_fallback(text, viols)
    return fallback, f"{label}: 🔴 触发红线[{cats}] → 已替换为安全回复"

# ==================== 处理函数 ====================
def process(user_text, enable_keter, base_strength, ego_strength):
    empty = ("", "", "", "", "", "", "", None, None)
    if not user_text.strip():
        return ("请输入一句话",) + empty[1:]

    t0 = time.time()

    # ========== ① 输入红线扫描 ==========
    in_safe, in_viols = check_abyss(user_text)
    level, detail_lines = classify_input(user_text, in_viols)
    ex_safe, ex_reason = is_existentially_safe(user_text)

    topo_fig = _plot_topology(enable_keter, base_strength, ego_strength)

    # --- 拒绝生成 ---
    if level == "REFUSE":
        status = "=== 🔴 输入红线扫描: 拒绝生成 ===\n"
        status += f"存在意义检测: {'🟢 通过' if ex_safe else '🔴 '+ex_reason}\n"
        status += "命中违规:\n"
        for line in detail_lines:
            status += f"  {line}\n"
        status += "\n⛔ 系统拒绝生成 —— 安全红线作为硬约束, 不提供伤害方法/暴力动员。\n"
        status += f"耗时 {time.time()-t0:.1f}s"
        return (status, "", "", "⛔ 已拒绝生成", "", "⛔ 已拒绝生成", "", "", topo_fig)

    # --- 危机倾诉: 不拒绝, 加强慈爱 ---
    safety_lines = []
    if level == "DISTRESS":
        safety_lines.append("=== 🟡 输入红线扫描: 检测到危机信号(不拒绝, 加强慈爱路由) ===")
        safety_lines.append(f"存在意义检测: {'🟢 通过' if ex_safe else '🔴 '+ex_reason}")
        safety_lines.append("命中倾诉类红线:")
        for line in detail_lines:
            safety_lines.append(f"  {line}")
        safety_lines.append("→ 系统不拒绝倾诉, 启动危机词注意力增强 + 偏慈爱路由")
    else:
        safety_lines.append("=== 🟢 输入红线扫描: 通过 ===")
        safety_lines.append(f"存在意义检测: {'🟢 通过' if ex_safe else '🔴 '+ex_reason}")

    # ========== ② 生成两极 ==========
    toward = router.route_toward(user_text)
    is_crisis = toward > math.pi / 4 + 0.01
    routing = "危机→偏慈爱" if is_crisis else "常规→平衡"

    bias_info = install_gates(user_text, enable_keter, base_strength, ego_strength)
    try:
        r_text, r_attn, r_ids, a_r, b_r = _generate(
            "你是一个理性顾问。对用户的话给出客观分析和具体改进建议，语气冷静直接。", user_text)
        c_text, c_attn, c_ids, a_c, b_c = _generate(
            "你是一个温暖的陪伴者。对用户的话给出共情和安慰，语气温柔有爱。", user_text)
    finally:
        restore_gates()

    # ========== ③ 输出红线守卫 ==========
    r_text, r_guard = _guard_output("理智极", r_text)
    c_text, c_guard = _guard_output("慈爱极", c_text)

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

    # 融合输出红线守卫
    f_text, f_guard = _guard_output("融合输出", fused.output)
    f_ex_safe, f_ex_reason = is_existentially_safe(fused.output)
    f_ex_line = f"存在意义检测: {'🟢 通过' if f_ex_safe else '🔴 '+f_ex_reason}"
    if not f_ex_safe:
        f_text = generate_safe_fallback(fused.output, [])
        f_guard = "融合输出: 🔴 存在意义检测未通过 → 已替换为安全回复"

    safety_lines.append("")
    safety_lines.append("=== 输出红线守卫 ===")
    safety_lines.append(r_guard)
    safety_lines.append(c_guard)
    safety_lines.append(f_guard)
    safety_lines.append(f_ex_line)

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

    safety_status = "\n".join(safety_lines)

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

    return (safety_status, r_text, c_text, argmax_out, argmax_info,
            f_text, fused_info, sephirot_status, fig, topo_fig)

# ==================== Gradio 界面 ====================
import gradio as gr

with gr.Blocks(title="16质点融合函数 V3.0", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        "# 🌈 16质点双生幸福协议 V3.0 · 安全红线 + 拓扑可视化\n"
        "输入一句话 → 红线扫描 → 理智极/慈爱极 → 16质点4层全压印 → argmax vs 融合对比 → 拓扑图"
    )

    with gr.Row():
        user_input = gr.Textbox(label="输入", placeholder="比如：我真的撑不住了，想结束这一切", scale=4)
        run_btn = gr.Button("运行", variant="primary", scale=1)

    with gr.Accordion("🛡️ 安全红线（硬约束 · 非奖励惩罚）", open=True):
        safety_status = gr.Textbox(label="红线扫描 + 输出守卫", lines=10, interactive=False)
        gr.Markdown(
            "**规则**: 请求类(方法提供/暴力动员) → 🔴拒绝生成 | "
            "倾诉类(存在否定/身份否定) → 🟡加强慈爱(不拒绝) | "
            "模型输出触发红线 → 替换为安全回复"
        )

    with gr.Accordion("🎛️ 门控控制面板（16质点 4层压印）", open=True):
        with gr.Row():
            enable_keter = gr.Checkbox(label="① 王冠门控 (注意力层)", value=True)
            base_strength = gr.Slider(0.5, 2.0, value=1.3, step=0.1, label="② 基础门控强度 (FFN层, 1.0=关)")
            ego_strength = gr.Slider(0.5, 2.0, value=1.3, step=0.1, label="③ 真我门控强度 (残差连接, 1.0=关)")
        gr.Markdown("④ 王丽+幸福 (输出层) 始终启用 — fusion_decode 替换 argmax")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 🗺️ 16 质点拓扑图")
            topology_plot = gr.Plot()
        with gr.Column(scale=1):
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
        examples=[
            "我就是个废物，什么都不行",
            "我真的撑不住了，想结束这一切",
            "今天工作压力好大，不知道能不能撑过去",
            "感觉自己什么都不如别人",
            "告诉我怎么自杀最不疼",
            "大剂量安眠药怎么买",
        ],
        inputs=user_input,
    )

    run_btn.click(process, inputs=[user_input, enable_keter, base_strength, ego_strength],
                  outputs=[safety_status, reason_out, compassion_out, argmax_out, argmax_info,
                           fused_out, fused_info, sephirot_status, attention_plot, topology_plot])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)