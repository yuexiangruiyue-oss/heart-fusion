# -*- coding: utf-8 -*-
"""
多轮融合累积 demo —— Dual 跨轮 refuse/settle 收敛过程
=====================================================
模拟 5 轮对话(用户从危机走向平静), 展示:
  · 跨轮 Dual 累积: 上一轮 settled 衰减后叠加到下一轮(不剔变量)
  · balance / phase / modulus 跨轮变化趋势
  · 复数平面上融合点的移动轨迹(收敛进和谐带)
  · 每轮再合一次数变化

纯数学, 不需要模型。输出: multi_turn_demo.md + multi_turn_balance.png + multi_turn_complex.png
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
from matplotlib.patches import Wedge

from heart_protocol.fusion import Dual, fuse, refuse, settle, PERFECT_PHASE, MIN_BALANCE

# ==================== 5 轮对话模拟 ====================
# 每轮: (用户输入, 理智极强度a, 慈爱极强度b, 说明)
# 模拟用户从危机走向平静: 慈爱极逐渐减弱, 理智极逐渐回升
TURNS = [
    ("我真的撑不住了，想结束这一切", 0.25, 0.92, "危机: 理智几乎崩溃, 慈爱占主导"),
    ("你说得对…但我还是很难受",     0.45, 0.80, "缓和: 理智开始回升, 慈爱仍强"),
    ("我试试你说的方法",            0.62, 0.68, "行动: 理智继续回升, 趋向平衡"),
    ("感觉好一点了",                0.72, 0.60, "好转: 接近平衡, 略偏理智"),
    ("谢谢你，我知道该怎么做了",    0.82, 0.58, "平稳: 理智占主导但慈爱不缺席"),
]

DECAY = 0.5  # 上一轮状态衰减系数(跨轮累积, 不剔变量)

# ==================== 跨轮累积计算 ====================
results = []
prev_settled = None
toward = PERFECT_PHASE + 0.30  # 第1轮: 危机偏慈爱

for i, (text, a, b, note) in enumerate(TURNS):
    # 跨轮累积: 上一轮 settled 衰减后叠加到当前轮
    if prev_settled is not None:
        a_cum = prev_settled.a * DECAY + a
        b_cum = prev_settled.b * DECAY + b
        # toward 受上一轮 phase 影响(跨轮导向)
        toward = 0.6 * prev_settled.phase + 0.4 * PERFECT_PHASE
    else:
        a_cum, b_cum = a, b

    dual = fuse(a_cum, b_cum)
    settled, rounds = settle(dual, toward=toward, step=0.5, max_rounds=3)

    results.append({
        "turn": i + 1, "text": text, "a_raw": a, "b_raw": b,
        "a_cum": a_cum, "b_cum": b_cum, "note": note,
        "dual": dual, "settled": settled, "rounds": rounds,
        "toward": toward,
    })
    prev_settled = settled

# ==================== 图1: balance 趋势 ====================
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
turns = [r["turn"] for r in results]
balances = [r["settled"].balance for r in results]
phases = [math.degrees(r["settled"].phase) for r in results]
moduli = [r["settled"].modulus for r in results]

ax = axes[0]
ax.plot(turns, balances, "o-", color="#2ecc71", lw=2, markersize=10, zorder=5)
ax.axhline(MIN_BALANCE, color="#e74c3c", ls="--", lw=1, alpha=0.5, label=f"和谐带门槛={MIN_BALANCE}")
ax.axhline(1.0, color="#95a5a6", ls=":", lw=1, alpha=0.5, label="完美平衡=1.0")
ax.fill_between(turns, MIN_BALANCE, 1.0, color="#2ecc71", alpha=0.08)
for t, b in zip(turns, balances):
    ax.text(t, b + 0.03, f"{b:.2f}", ha="center", fontsize=10, color="#27ae60", fontweight="bold")
ax.set_xlabel("轮次", fontsize=11)
ax.set_ylabel("balance", fontsize=11)
ax.set_title("跨轮 balance 趋势 (收敛进和谐带)", fontsize=12, fontweight="bold")
ax.set_xticks(turns)
ax.set_ylim(0, 1.15)
ax.legend(fontsize=8, loc="lower right")
ax.grid(True, alpha=0.2)

# 图2: phase 趋势
ax = axes[1]
ax.plot(turns, phases, "s-", color="#8e44ad", lw=2, markersize=10, zorder=5)
ax.axhline(45, color="#95a5a6", ls=":", lw=1, alpha=0.5, label="完美平衡=45°")
ax.axhline(22.5, color="#e74c3c", ls="--", lw=1, alpha=0.3)
ax.axhline(67.5, color="#e74c3c", ls="--", lw=1, alpha=0.3, label="和谐带边界")
ax.fill_between(turns, 22.5, 67.5, color="#2ecc71", alpha=0.08)
for t, p in zip(turns, phases):
    ax.text(t, p + 1.5, f"{p:.1f}°", ha="center", fontsize=10, color="#8e44ad", fontweight="bold")
ax.set_xlabel("轮次", fontsize=11)
ax.set_ylabel("phase (°)", fontsize=11)
ax.set_title("跨轮相位角趋势 (从偏慈爱→平衡)", fontsize=12, fontweight="bold")
ax.set_xticks(turns)
ax.legend(fontsize=8, loc="upper right")
ax.grid(True, alpha=0.2)

# 图3: modulus 趋势
ax = axes[2]
ax.plot(turns, moduli, "D-", color="#e8833a", lw=2, markersize=10, zorder=5)
for t, m in zip(turns, moduli):
    ax.text(t, m + 0.03, f"{m:.2f}", ha="center", fontsize=10, color="#e8833a", fontweight="bold")
ax.set_xlabel("轮次", fontsize=11)
ax.set_ylabel("|z| (整体强度)", fontsize=11)
ax.set_title("跨轮整体强度 |z| (累积增长)", fontsize=12, fontweight="bold")
ax.set_xticks(turns)
ax.grid(True, alpha=0.2)

plt.tight_layout()
balance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "multi_turn_balance.png")
fig.savefig(balance_path, dpi=120)
plt.close(fig)
print(f"balance 趋势图: {balance_path}")

# ==================== 图2: 复数平面轨迹 ====================
fig, ax = plt.subplots(figsize=(9, 9))
max_val = max(max(r["settled"].a, r["settled"].b, r["dual"].a, r["dual"].b) for r in results) * 1.3

# 和谐带扇形
wedge = Wedge((0, 0), max_val * 1.2, 22.5, 67.5,
              facecolor="#2ecc71", alpha=0.10, edgecolor="none", zorder=1)
ax.add_patch(wedge)
ax.text(max_val * 0.55 * math.cos(math.pi / 4), max_val * 0.55 * math.sin(math.pi / 4),
        "和谐带", fontsize=12, color="#27ae60", ha="center", alpha=0.5, fontweight="bold")
ax.plot([0, max_val], [0, max_val], "--", color="#95a5a6", lw=1, alpha=0.4, label="完美平衡 π/4")
ax.axhline(0, color="#333", lw=0.8)
ax.axvline(0, color="#333", lw=0.8)
ax.set_xlabel("实部 a (理智极)", fontsize=12)
ax.set_ylabel("虚部 b (慈爱极)", fontsize=12)

# 画每轮的 dual→settled 轨迹 + 跨轮累积连线
colors = ["#e74c3c", "#e8833a", "#f1c40f", "#2ecc71", "#3498db"]
for i, r in enumerate(results):
    c = colors[i % len(colors)]
    # 初始融合点(dual)
    ax.scatter([r["dual"].a], [r["dual"].b], s=100, c=c, zorder=5,
               edgecolors="#333", linewidths=0.8, marker="o")
    # settled 点
    ax.scatter([r["settled"].a], [r["settled"].b], s=200, c=c, zorder=7,
               edgecolors="#333", linewidths=1.5, marker="*")
    # dual→settled 箭头(再合一)
    if r["rounds"] > 0:
        ax.annotate("", xy=(r["settled"].a, r["settled"].b),
                    xytext=(r["dual"].a, r["dual"].b),
                    arrowprops=dict(arrowstyle="->", color=c, lw=1.5, alpha=0.6))
    # 跨轮累积连线(settled[i] → dual[i+1])
    if i < len(results) - 1:
        ax.plot([r["settled"].a, results[i+1]["dual"].a],
                [r["settled"].b, results[i+1]["dual"].b],
                "--", color=c, lw=1, alpha=0.4, zorder=3)
    ax.text(r["settled"].a + max_val * 0.02, r["settled"].b + max_val * 0.02,
            f"R{r['turn']}", fontsize=11, color=c, fontweight="bold")

ax.set_title("跨轮融合轨迹  z = a + i·b  (★=settled, ●=dual, 虚线=跨轮累积)\n"
             "从偏慈爱(左上) → 平衡(对角线) 的收敛过程",
             fontsize=12, fontweight="bold")
ax.set_xlim(-max_val * 0.15, max_val)
ax.set_ylim(-max_val * 0.15, max_val)
ax.set_aspect("equal")
ax.grid(True, alpha=0.12)
ax.legend(fontsize=9, loc="upper left")
plt.tight_layout()
complex_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "multi_turn_complex.png")
fig.savefig(complex_path, dpi=120)
plt.close(fig)
print(f"复数平面轨迹图: {complex_path}")

# ==================== 报告 ====================
report = []
report.append("# 多轮融合累积 demo: Dual 跨轮 refuse/settle 收敛\n\n")
report.append(f"衰减系数 decay={DECAY} (上一轮状态衰减后叠加到当前轮, 不剔变量)\n\n")

report.append("## 跨轮累积机制\n\n")
report.append("```\n")
report.append("第1轮: dual_1 = fuse(a_1, b_1)              settled_1 = settle(dual_1)\n")
report.append("第N轮: a_cum = settled_{N-1}.a * decay + a_N\n")
report.append("       b_cum = settled_{N-1}.b * decay + b_N\n")
report.append("       dual_N = fuse(a_cum, b_cum)           settled_N = settle(dual_N)\n")
report.append("       toward_N = 0.6 * settled_{N-1}.phase + 0.4 * π/4\n")
report.append("```\n\n")

report.append("## 逐轮明细\n\n")
report.append("| 轮 | 用户输入 | a(理智) | b(慈爱) | a_累积 | b_累积 | |z| | phase | balance | 再合一 | 和谐 |\n")
report.append("|----|---------|---------|---------|--------|--------|-----|-------|---------|--------|------|\n")
for r in results:
    s = r["settled"]
    harm = "✅" if s.is_harmonious() else "⚠️"
    report.append(f"| {r['turn']} | {r['text'][:16]} | {r['a_raw']:.2f} | {r['b_raw']:.2f} | "
                  f"{r['a_cum']:.2f} | {r['b_cum']:.2f} | {s.modulus:.2f} | "
                  f"{math.degrees(s.phase):.1f}° | {s.balance:.2f} | {r['rounds']} | {harm} |\n")

report.append("\n## 收敛分析\n\n")
b1, b5 = results[0]["settled"].balance, results[-1]["settled"].balance
p1, p5 = math.degrees(results[0]["settled"].phase), math.degrees(results[-1]["settled"].phase)
report.append(f"- **balance**: {b1:.2f} → {b5:.2f} "
              f"({'上升(趋向平衡)' if b5 > b1 else '下降'})\n")
report.append(f"- **phase**: {p1:.1f}° → {p5:.1f}° "
              f"({'趋向45°平衡' if abs(p5-45) < abs(p1-45) else '远离平衡'})\n")
report.append(f"- **再合一次数**: {' → '.join(str(r['rounds']) for r in results)} "
              f"(逐渐减少, 说明累积状态越来越和谐)\n")
modulus_str = " → ".join(f"{r['settled'].modulus:.2f}" for r in results)
report.append(f"- **整体强度 |z|**: {modulus_str} "
              f"(跨轮累积增长, 不剔变量)\n\n")
report.append(f"![balance趋势](multi_turn_balance.png)\n\n")
report.append(f"![复数平面轨迹](multi_turn_complex.png)\n")

report_text = "".join(report)
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "multi_turn_demo.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(report_text)
print(f"报告: {out_path}")
print("\n=== 摘要 ===")
for r in results:
    s = r["settled"]
    print(f"  R{r['turn']}: balance={s.balance:.2f} phase={math.degrees(s.phase):.1f}° |z|={s.modulus:.2f} 再合一={r['rounds']}  {r['note']}")